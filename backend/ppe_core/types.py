"""Plain data types shared by every stage of the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np

# Canonical PPE items the app reasons about. Models are mapped onto these names.
PPE_ITEMS: tuple[str, ...] = ("helmet", "vest", "gloves", "boots", "goggles", "mask", "earmuffs")
# Body parts a detector may also provide (SH17 does); used as extra evidence for body regions.
BODY_PARTS: tuple[str, ...] = ("person", "head", "face", "ear", "hands", "foot")

ItemState = Literal["worn", "absent", "unknown", "not_checked"]
Overall = Literal["compliant", "violation", "unknown"]


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def w(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def h(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.w * self.h

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    def as_list(self) -> list[float]:
        return [round(self.x1, 1), round(self.y1, 1), round(self.x2, 1), round(self.y2, 1)]

    def intersection(self, other: "Box") -> float:
        iw = min(self.x2, other.x2) - max(self.x1, other.x1)
        ih = min(self.y2, other.y2) - max(self.y1, other.y1)
        return max(0.0, iw) * max(0.0, ih)

    def ioa(self, region: "Box") -> float:
        """Fraction of *this* box that lies inside `region` (intersection over own area)."""
        return self.intersection(region) / self.area if self.area > 0 else 0.0

    def iou(self, other: "Box") -> float:
        inter = self.intersection(other)
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0

    def clip(self, width: float, height: float) -> "Box":
        return Box(max(0.0, self.x1), max(0.0, self.y1), min(width, self.x2), min(height, self.y2))


@dataclass
class Detection:
    cls: str  # canonical name (e.g. "helmet")
    raw_cls: str  # name as the model reports it (e.g. "safety-vest")
    conf: float
    box: Box
    source: str = ""  # which detector produced it


@dataclass
class Person:
    idx: int
    box: Box
    conf: float
    # COCO-17 keypoints as (17, 3) array of x, y, confidence; None when no pose model ran.
    keypoints: Optional[np.ndarray] = None


@dataclass
class ItemAssessment:
    item: str
    state: ItemState
    conf: Optional[float] = None
    reason: str = ""
    evidence: Optional[Box] = None

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "conf": None if self.conf is None else round(float(self.conf), 3),
            "reason": self.reason,
            "evidence": None if self.evidence is None else self.evidence.as_list(),
        }


@dataclass
class PersonAssessment:
    person: Person
    items: dict[str, ItemAssessment] = field(default_factory=dict)
    overall: Overall = "unknown"
    missing: list[str] = field(default_factory=list)  # required items judged absent
    uncertain: list[str] = field(default_factory=list)  # required items judged unknown
