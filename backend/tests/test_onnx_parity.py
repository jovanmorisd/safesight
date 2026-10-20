"""The ONNX runner must reproduce Ultralytics' own predictions (skipped where ultralytics/.pt are absent)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageOps

BACKEND = Path(__file__).resolve().parent.parent
SAMPLES = sorted((BACKEND.parent / "samples").glob("*.jp*g"))[:6]
PAIRS = [("models/construction-safety-yolov8n.pt", "models/construction-safety-yolov8n.onnx", 0.35),
         ("models/yolo8s.pt", "models/yolo8s.onnx", 0.35),
         ("yolo11n-pose.pt", "models/yolo11n-pose.onnx", 0.35)]

ultralytics = pytest.importorskip("ultralytics")


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0


def _match_rate(ref, got):
    """Share of reference boxes found again (same class, IoU >= 0.85)."""
    if not ref:
        return 1.0
    used, hit = set(), 0
    for rb, rc in ref:
        for j, (gb, gc) in enumerate(got):
            if j not in used and gc == rc and _iou(rb, gb) >= 0.85:
                used.add(j)
                hit += 1
                break
    return hit / len(ref)


@pytest.mark.parametrize("pt,onnx,conf", PAIRS)
def test_onnx_matches_ultralytics(pt, onnx, conf):
    from ultralytics import YOLO

    from ppe_core.models import OnnxYolo

    if not (BACKEND / pt).exists() and "/" in pt or not (BACKEND / onnx).exists() or not SAMPLES:
        pytest.skip("weights or samples missing")
    ref_model = YOLO(str(BACKEND / pt) if "/" in pt else pt)
    ours = OnnxYolo(str(BACKEND / onnx))
    rates, ref_total = [], 0
    for path in SAMPLES:
        img = np.asarray(ImageOps.exif_transpose(Image.open(path)).convert("RGB"))
        r = ref_model.predict(img[..., ::-1].copy(), conf=conf, iou=0.7 if "pose" in onnx else 0.5,
                              device="cpu", verbose=False)[0]  # ultralytics expects BGR arrays
        ref = [(b.tolist(), int(c)) for b, c in zip(r.boxes.xyxy.numpy(), r.boxes.cls.numpy())]
        boxes, _, cls, _ = ours.predict(img, conf, 0.7 if "pose" in onnx else 0.5)
        got = [(b.tolist(), int(c)) for b, c in zip(boxes, cls)]
        ref_total += len(ref)
        rates.append((_match_rate(ref, got), _match_rate(got, ref)))
    recall = np.mean([a for a, _ in rates])
    precision = np.mean([b for _, b in rates])
    print(f"{onnx}: {ref_total} reference boxes, recall {recall:.3f}, precision {precision:.3f}")
    assert recall >= 0.9 and precision >= 0.9
