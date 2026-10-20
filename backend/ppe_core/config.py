"""Configuration loading and class-name mapping.

A detector is described by its weights file plus a `class_map` from the model's own
class names to the canonical names in `types.PPE_ITEMS` / `types.BODY_PARTS`. When a
model is registered without an explicit map, `auto_class_map` guesses one from common
dataset naming conventions, so a newly trained model usually plugs in unchanged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .types import BODY_PARTS, PPE_ITEMS

# Known spellings across public PPE datasets (SH17, Construction-PPE, Hard Hat Workers,
# Roboflow Construction Site Safety, CHV, ...). Keys are normalised (see `_norm`).
SYNONYMS: dict[str, str] = {
    # PPE
    "helmet": "helmet", "hardhat": "helmet", "hat": "helmet", "safetyhelmet": "helmet",
    "helmetwhite": "helmet", "helmetyellow": "helmet", "helmetblue": "helmet", "helmetred": "helmet",
    "white": "helmet", "yellow": "helmet", "blue": "helmet", "red": "helmet",
    "vest": "vest", "safetyvest": "vest", "hivis": "vest", "reflectivevest": "vest",
    "gloves": "gloves", "glove": "gloves",
    "boots": "boots", "boot": "boots", "shoes": "boots", "shoe": "boots", "safetyshoes": "boots",
    "safetyboots": "boots",
    "goggles": "goggles", "goggle": "goggles", "glasses": "goggles", "safetyglasses": "goggles",
    "mask": "mask", "facemask": "mask", "facemaskmedical": "mask",
    "earmuffs": "earmuffs", "earmufs": "earmuffs", "earmuff": "earmuffs", "earprotection": "earmuffs",
    # body parts
    "person": "person", "worker": "person", "human": "person",
    "head": "head", "face": "face", "ear": "ear", "hands": "hands", "hand": "hands",
    "foot": "foot", "feet": "foot",
}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def auto_class_map(model_names: list[str]) -> dict[str, str]:
    """Guess raw-name -> canonical-name for a model. Negative classes (NO-Hardhat,
    no_helmet, ...) are skipped: absence is inferred per person, not detected."""
    mapping: dict[str, str] = {}
    for raw in model_names:
        n = _norm(raw)
        if n.startswith("no") and n[2:] in SYNONYMS:
            continue
        if n in SYNONYMS:
            mapping[raw] = SYNONYMS[n]
    return mapping


@dataclass
class DetectorConfig:
    name: str
    weights: str
    conf: float = 0.35
    iou: float = 0.5
    imgsz: int = 640  # informational: ONNX models carry their own input size
    class_map: Optional[dict[str, str]] = None  # None -> auto_class_map


@dataclass
class PoseConfig:
    weights: Optional[str] = "models/yolo11n-pose.onnx"
    conf: float = 0.35
    keypoint_conf: float = 0.4


@dataclass
class AssociationConfig:
    min_ioa: float = 0.3  # min fraction of a PPE box inside a body region to count as worn
    min_person_height: int = 48  # px; smaller people are reported as unknown


@dataclass
class AppConfig:
    detectors: list[DetectorConfig] = field(default_factory=list)
    pose: PoseConfig = field(default_factory=PoseConfig)
    association: AssociationConfig = field(default_factory=AssociationConfig)
    default_required: list[str] = field(default_factory=lambda: ["helmet", "vest"])
    base_dir: Path = Path(".")

    def resolve(self, path: str) -> str:
        """Resolve a weights path relative to the config file; bare names (e.g. an
        Ultralytics hub model like 'yolo11n-pose.pt') are kept as-is."""
        p = Path(path)
        if p.is_absolute():
            return str(p)
        candidate = self.base_dir / p
        return str(candidate) if candidate.exists() or "/" in path or "\\" in path else path


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    detectors = [DetectorConfig(**d) for d in raw.get("detectors", [])]
    cfg = AppConfig(
        detectors=detectors,
        pose=PoseConfig(**(raw.get("pose") or {})),
        association=AssociationConfig(**(raw.get("association") or {})),
        default_required=raw.get("policy", {}).get("default_required", ["helmet", "vest"]),
        base_dir=path.parent.resolve(),
    )
    for item in cfg.default_required:
        if item not in PPE_ITEMS:
            raise ValueError(f"Unknown PPE item in policy: {item!r}. Known: {PPE_ITEMS}")
    return cfg


__all__ = ["AppConfig", "DetectorConfig", "PoseConfig", "AssociationConfig", "load_config",
           "auto_class_map", "SYNONYMS", "PPE_ITEMS", "BODY_PARTS"]
