"""Owns the live inference pipeline and keeps it in sync with the model registry."""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional

import numpy as np
from sqlmodel import Session, select

from ppe_core.config import AppConfig, DetectorConfig, load_config
from ppe_core.models import Detector
from ppe_core.pipeline import Pipeline, file_sha256

from .db import BACKEND_DIR, CONFIG_PATH, ModelVersion, Site, engine
from .storage import storage

log = logging.getLogger("ppe.engine")

# Where weights fetched from storage are cached. Serverless hosts (Vercel) only allow writing to /tmp.
CACHE_DIR = Path(os.environ.get("MODEL_CACHE_DIR") or ("/tmp/ppe-models" if os.environ.get("VERCEL") else BACKEND_DIR))

_cfg: Optional[AppConfig] = None
_pipeline: Optional[Pipeline] = None
_active: list[ModelVersion] = []
_lock = threading.Lock()


def config() -> AppConfig:
    global _cfg
    if _cfg is None:
        _cfg = load_config(CONFIG_PATH)
    return _cfg


def local_weights(path: str) -> str:
    """Local file for a registered weights path.

    Bundled models (models/*.onnx) ship with the code. Models uploaded through the UI live in
    storage under the same key (models/uploads/<name>.onnx) and are downloaded once per server
    instance into CACHE_DIR."""
    p = Path(path)
    if p.is_absolute():
        return str(p)
    bundled = BACKEND_DIR / p
    if bundled.exists():
        return str(bundled)
    cached = CACHE_DIR / p
    if not cached.exists():
        data = storage.read(p.as_posix())
        if data is None:
            raise FileNotFoundError(f"weights not found: {path}")
        cached.parent.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(cached.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(cached)
        log.info("downloaded %s from %s storage (%.1f MB)", path, storage.name, len(data) / 1e6)
    return str(cached)


def forget_cached(path: str) -> None:
    (CACHE_DIR / path).unlink(missing_ok=True)


def detector_cfg(mv: ModelVersion) -> DetectorConfig:
    return DetectorConfig(name=mv.name, weights=local_weights(mv.weights_path), conf=mv.conf, imgsz=mv.imgsz,
                          class_map=mv.class_map or None)


def inspect_weights(weights_path: str, class_map: Optional[dict], conf: float = 0.35,
                    imgsz: int = 640, name: str = "probe") -> Detector:
    """Load a weights file once to validate it and read its classes."""
    local = local_weights(weights_path)
    return Detector(DetectorConfig(name=name, weights=local, conf=conf, imgsz=imgsz, class_map=class_map or None), local)


def seed(session: Session) -> None:
    """Start-up: register the models from config.yaml (first run), migrate PyTorch-era rows to the
    bundled ONNX files, and make sure a default site exists."""
    cfg = config()
    rows = session.exec(select(ModelVersion)).all()
    if not rows:
        for d in cfg.detectors:
            det = inspect_weights(d.weights, d.class_map, d.conf, d.imgsz, d.name)
            session.add(ModelVersion(name=d.name, weights_path=d.weights, sha256=file_sha256(local_weights(d.weights)),
                                     conf=d.conf, imgsz=d.imgsz, class_map=d.class_map,
                                     classes=list(det.raw_names.values()),
                                     supported=sorted(det.supported), is_active=True,
                                     notes="registered from config.yaml"))
    for mv in rows:
        if mv.weights_path.endswith(".pt"):
            onnx = Path(mv.weights_path).with_suffix(".onnx")
            if (BACKEND_DIR / onnx).exists():
                mv.weights_path = onnx.as_posix()
                mv.sha256 = file_sha256(str(BACKEND_DIR / onnx))
            else:
                mv.is_active = False
                mv.notes = "PyTorch .pt models are no longer supported: export to ONNX and register it again."
            session.add(mv)
    session.flush()
    if rows and not any(m.is_active for m in session.exec(select(ModelVersion)).all()):
        for mv in session.exec(select(ModelVersion)).all():
            if (BACKEND_DIR / mv.weights_path).exists():
                mv.is_active = True
                session.add(mv)
    if not session.exec(select(Site)).first():
        session.add(Site(name="Main Site", location="Default", required_ppe=list(cfg.default_required)))
    session.commit()


def reload() -> Pipeline:
    """Rebuild the pipeline from the currently active model versions."""
    global _pipeline, _active
    with _lock:
        with Session(engine) as s:
            active = list(s.exec(select(ModelVersion).where(ModelVersion.is_active == True)))  # noqa: E712
            if not active:
                raise RuntimeError("No active model. Activate one on the Models page.")
            for mv in active:
                s.expunge(mv)
        log.info("loading pipeline with models: %s", [m.name for m in active])
        pipe = Pipeline(config(), [detector_cfg(m) for m in active])
        pipe.run(np.zeros((320, 320, 3), np.uint8))  # warm-up: first-call overhead in onnxruntime
        _pipeline, _active = pipe, active
        return _pipeline


def pipeline() -> Pipeline:
    return _pipeline if _pipeline is not None else reload()


def active_models() -> list[ModelVersion]:
    pipeline()
    return list(_active)
