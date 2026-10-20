"""End-to-end inference: detectors + pose -> association -> policy -> annotation."""
from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .annotate import annotate
from .associate import assess
from .config import AppConfig, DetectorConfig
from .models import Detector, PoseModel, merge_detections
from .policy import judge
from .types import PPE_ITEMS, Detection, Person, PersonAssessment


@dataclass
class PipelineResult:
    detections: list[Detection]
    assessments: list[PersonAssessment]
    annotated: np.ndarray
    required: list[str]
    supported: list[str]
    timings_ms: dict[str, float] = field(default_factory=dict)


def file_sha256(path: str) -> Optional[str]:
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Pipeline:
    def __init__(self, cfg: AppConfig, detector_cfgs: Optional[list[DetectorConfig]] = None):
        self.cfg = cfg
        self.detectors = [Detector(d, cfg.resolve(d.weights)) for d in (detector_cfgs or cfg.detectors)]
        if not self.detectors:
            raise ValueError("At least one detector must be configured")
        self.pose = PoseModel(cfg.pose, cfg.resolve(cfg.pose.weights)) if cfg.pose.weights else None
        self._lock = threading.Lock()

    @property
    def supported(self) -> list[str]:
        s: set[str] = set()
        for d in self.detectors:
            s |= d.supported
        return [i for i in PPE_ITEMS if i in s]

    def describe(self) -> dict:
        return {
            "device": "cpu",
            "runtime": "ONNX Runtime",
            "pose": Path(self.cfg.pose.weights).name if self.cfg.pose.weights else None,
            "supported": self.supported,
            "detectors": [{"name": d.name, "weights": Path(d.cfg.weights).name, "classes": list(d.raw_names.values()),
                           "class_map": d.class_map} for d in self.detectors],
        }

    def run(self, image: np.ndarray, required: Optional[list[str]] = None) -> PipelineResult:
        required = list(required if required is not None else self.cfg.default_required)
        a = self.cfg.association
        t: dict[str, float] = {}
        with self._lock:
            t0 = time.perf_counter()
            dets: list[Detection] = []
            for det in self.detectors:
                dets.extend(det(image))
            dets = merge_detections(dets) if len(self.detectors) > 1 else dets
            t["detect"] = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            persons = self.pose(image) if self.pose else []
            t["pose"] = (time.perf_counter() - t0) * 1000

        persons = self._add_detector_persons(persons, dets)
        h, w = image.shape[:2]
        t0 = time.perf_counter()
        assessments = assess(persons, dets, set(self.supported), w, h, min_ioa=a.min_ioa,
                             kp_thr=self.cfg.pose.keypoint_conf, min_person_height=a.min_person_height)
        for pa in assessments:
            judge(pa, required)
        t["associate"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        annotated = annotate(image, assessments, dets, kp_thr=self.cfg.pose.keypoint_conf)
        t["annotate"] = (time.perf_counter() - t0) * 1000
        t["total"] = sum(t.values())
        return PipelineResult(dets, assessments, annotated, required, self.supported, t)

    @staticmethod
    def _add_detector_persons(persons: list[Person], dets: list[Detection]) -> list[Person]:
        """People the detector found but the pose model missed still get assessed (with
        box-based regions, since they have no keypoints)."""
        out = list(persons)
        for d in sorted((d for d in dets if d.cls == "person"), key=lambda d: d.box.area, reverse=True):
            # skip duplicates and partial boxes (e.g. upper/lower body) of someone already found
            if all(p.box.iou(d.box) < 0.5 and d.box.ioa(p.box) < 0.6 for p in out):
                out.append(Person(len(out), d.box, d.conf, None))
        return out
