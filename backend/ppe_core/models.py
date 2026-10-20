"""YOLO models exported to ONNX, run with onnxruntime (no PyTorch / Ultralytics needed).

Any Ultralytics YOLO model exported with `model.export(format="onnx")` works. Class names, input
size and task come from the file's metadata. Two output layouts are handled:

* classic (YOLOv8/v9/v11): detect (1, 4 + classes, N), pose (1, 5 + 3*K, N); boxes are centre xywh
  and need non-maximum suppression;
* end-to-end / NMS-free (YOLOv10, YOLO26): (1, max_det, 6 [+ 3*K]) as x1, y1, x2, y2, score, class.

Images are RGB uint8 arrays (H, W, 3).
"""
from __future__ import annotations

import ast
from typing import Optional

import numpy as np

from .config import DetectorConfig, PoseConfig, auto_class_map
from .types import PPE_ITEMS, Box, Detection, Person

MAX_DET = 300


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thr: float) -> np.ndarray:
    """Greedy non-maximum suppression on xyxy boxes; returns kept indices (highest score first)."""
    order = scores.argsort()[::-1]
    areas = (boxes[:, 2] - boxes[:, 0]).clip(0) * (boxes[:, 3] - boxes[:, 1]).clip(0)
    keep = []
    while order.size:
        i = order[0]
        keep.append(i)
        if len(keep) >= MAX_DET:
            break
        xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
        yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
        xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
        yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
        inter = (xx2 - xx1).clip(0) * (yy2 - yy1).clip(0)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][iou <= iou_thr]
    return np.array(keep, dtype=int)


def _xywh2xyxy(b: np.ndarray) -> np.ndarray:
    out = np.empty_like(b)
    out[:, 0] = b[:, 0] - b[:, 2] / 2
    out[:, 1] = b[:, 1] - b[:, 3] / 2
    out[:, 2] = b[:, 0] + b[:, 2] / 2
    out[:, 3] = b[:, 1] + b[:, 3] / 2
    return out


def resize_bilinear(img: np.ndarray, nw: int, nh: int) -> np.ndarray:
    """Plain bilinear resize with half-pixel centres and no anti-aliasing, i.e. what OpenCV's
    INTER_LINEAR (used by Ultralytics during training and export) does, so inputs match closely."""
    h, w = img.shape[:2]
    xs = np.clip((np.arange(nw) + 0.5) * (w / nw) - 0.5, 0, w - 1)
    ys = np.clip((np.arange(nh) + 0.5) * (h / nh) - 0.5, 0, h - 1)
    x0, y0 = np.floor(xs).astype(int), np.floor(ys).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    wx, wy = (xs - x0)[None, :, None], (ys - y0)[:, None, None]
    f = img.astype(np.float32)
    top = f[y0][:, x0] * (1 - wx) + f[y0][:, x1] * wx
    bot = f[y1][:, x0] * (1 - wx) + f[y1][:, x1] * wx
    return np.clip(top * (1 - wy) + bot * wy + 0.5, 0, 255).astype(np.uint8)


class OnnxYolo:
    """One exported YOLO model plus its letterbox pre-processing."""

    def __init__(self, path: str):
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])
        meta = self.session.get_modelmeta().custom_metadata_map
        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        h, w = inp.shape[2], inp.shape[3]
        if not isinstance(h, int) or not isinstance(w, int):  # dynamic export: fall back to metadata
            h, w = ast.literal_eval(meta.get("imgsz", "[640, 640]"))
        self.size = (int(h), int(w))
        self.names: dict[int, str] = {int(k): str(v) for k, v in ast.literal_eval(meta.get("names", "{}")).items()}
        self.task = meta.get("task", "detect")
        self.end2end = meta.get("end2end", "False") == "True"
        kpt = meta.get("kpt_shape")
        self.kpt_shape = tuple(ast.literal_eval(kpt)) if kpt else None
        out_shape = self.session.get_outputs()[0].shape
        if not self.end2end and len(out_shape) == 3 and isinstance(out_shape[2], int) and out_shape[2] in (6, 57) \
                and isinstance(out_shape[1], int) and out_shape[1] <= MAX_DET:
            self.end2end = True  # older exports without the metadata flag
        if not self.names:
            raise ValueError("ONNX file has no class names; export it with Ultralytics (model.export(format='onnx'))")

    def _letterbox(self, img: np.ndarray) -> tuple[np.ndarray, float, int, int]:
        H, W = self.size
        h, w = img.shape[:2]
        r = min(H / h, W / w)
        nw, nh = int(round(w * r)), int(round(h * r))
        left, top = int(round((W - nw) / 2 - 0.1)), int(round((H - nh) / 2 - 0.1))
        canvas = np.full((H, W, 3), 114, np.uint8)
        resized = img if (nw, nh) == (w, h) else resize_bilinear(img, nw, nh)
        canvas[top:top + nh, left:left + nw] = resized
        x = canvas.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        return x, r, left, top

    def predict(self, img: np.ndarray, conf: float, iou: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray]]:
        """Returns boxes (n, 4) xyxy in image pixels, scores (n,), class ids (n,), keypoints (n, K, 3) or None."""
        x, r, left, top = self._letterbox(img)
        out = self.session.run(None, {self.input_name: x})[0][0]
        k = self.kpt_shape[0] * self.kpt_shape[1] if self.kpt_shape else 0

        if self.end2end:  # (max_det, 6 + k): x1 y1 x2 y2 score cls [kpts]
            out = out[out[:, 4] >= conf]
            boxes, scores, cls = out[:, :4], out[:, 4], out[:, 5].astype(int)
            kpts = out[:, 6:6 + k] if k else None
        else:  # (4 + nc [+ k], N)
            out = out.T
            nc = out.shape[1] - 4 - k
            cls_scores = out[:, 4:4 + nc]
            cls = cls_scores.argmax(1)
            scores = cls_scores[np.arange(len(cls)), cls]
            m = scores >= conf
            boxes, scores, cls = _xywh2xyxy(out[m, :4]), scores[m], cls[m]
            kpts = out[m, 4 + nc:] if k else None
            # class-aware NMS: offset boxes per class so different classes never suppress each other
            keep = nms(boxes + cls[:, None] * 7680.0, scores, iou)
            boxes, scores, cls = boxes[keep], scores[keep], cls[keep]
            kpts = kpts[keep] if kpts is not None else None

        h, w = img.shape[:2]
        boxes = boxes.copy()
        boxes[:, [0, 2]] = ((boxes[:, [0, 2]] - left) / r).clip(0, w)
        boxes[:, [1, 3]] = ((boxes[:, [1, 3]] - top) / r).clip(0, h)
        if kpts is not None:
            kpts = kpts.reshape(len(kpts), *self.kpt_shape).copy()
            kpts[..., 0] = (kpts[..., 0] - left) / r
            kpts[..., 1] = (kpts[..., 1] - top) / r
        return boxes, scores, cls, kpts


class Detector:
    """A PPE detector (ONNX) plus its class-name mapping."""

    def __init__(self, cfg: DetectorConfig, weights_path: str):
        self.cfg = cfg
        self.name = cfg.name
        self.model = OnnxYolo(weights_path)
        if self.model.task != "detect":
            raise ValueError(f"{cfg.name}: expected a detection model, got task '{self.model.task}'")
        self.raw_names: dict[int, str] = self.model.names
        self.class_map: dict[str, str] = cfg.class_map or auto_class_map(list(self.raw_names.values()))
        self.supported: set[str] = {v for v in self.class_map.values() if v in PPE_ITEMS}

    def __call__(self, image: np.ndarray) -> list[Detection]:
        boxes, scores, cls, _ = self.model.predict(image, self.cfg.conf, self.cfg.iou)
        out: list[Detection] = []
        for (x1, y1, x2, y2), c, k in zip(boxes, scores, cls):
            raw = self.raw_names.get(int(k), str(k))
            canon = self.class_map.get(raw)
            if canon is not None:
                out.append(Detection(canon, raw, float(c), Box(float(x1), float(y1), float(x2), float(y2)), self.name))
        return out


class PoseModel:
    """Pose model (ONNX): person boxes + COCO-17 keypoints."""

    def __init__(self, cfg: PoseConfig, weights_path: str):
        self.cfg = cfg
        self.model = OnnxYolo(weights_path)
        if self.model.task != "pose" or not self.model.kpt_shape:
            raise ValueError("pose weights must be an Ultralytics pose model exported to ONNX")

    def __call__(self, image: np.ndarray) -> list[Person]:
        boxes, scores, _, kpts = self.model.predict(image, self.cfg.conf, 0.7)
        return [Person(i, Box(*map(float, b)), float(s), None if kpts is None else kpts[i])
                for i, (b, s) in enumerate(zip(boxes, scores))]


def merge_detections(dets: list[Detection], iou_thr: float = 0.6) -> list[Detection]:
    """Class-wise NMS across detectors, so overlapping models don't double count."""
    kept: list[Detection] = []
    for d in sorted(dets, key=lambda d: d.conf, reverse=True):
        if all(k.cls != d.cls or k.box.iou(d.box) < iou_thr for k in kept):
            kept.append(d)
    return kept
