"""Model registry, sites/policies and app metadata."""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from ppe_core.pipeline import file_sha256
from ppe_core.types import PPE_ITEMS

from .. import engine as eng
from ..auth import admin_user, current_user
from ..db import BACKEND_DIR, DB_KIND, RETENTION_DAYS, Inspection, ModelVersion, Site, User, get_session, iso
from ..storage import storage

router = APIRouter(prefix="/api", tags=["admin"])


def model_out(m: ModelVersion) -> dict:
    return {"id": m.id, "name": m.name, "weights_path": m.weights_path, "sha256": (m.sha256 or "")[:12],
            "conf": m.conf, "imgsz": m.imgsz, "class_map": m.class_map, "classes": m.classes,
            "supported": m.supported, "is_active": m.is_active, "notes": m.notes,
            "created_at": iso(m.created_at)}


@router.get("/meta")
def meta(_: User = Depends(current_user)):
    pipe = eng.pipeline()
    return {"ppe_items": list(PPE_ITEMS), "pipeline": pipe.describe(),
            "database": DB_KIND, "storage": storage.name, "retention_days": RETENTION_DAYS}


# ----------------------------------------------------------------------------- models

@router.get("/models")
def list_models(session: Session = Depends(get_session), _: User = Depends(admin_user)):
    rows = session.exec(select(ModelVersion).order_by(ModelVersion.created_at)).all()
    return [model_out(m) for m in rows]


NAME_RE = re.compile(r"[A-Za-z0-9._-]{2,64}")


def _upload_key(name: str) -> str:
    return f"models/uploads/{name}.onnx"


def _check_new_name(session: Session, name: str) -> str:
    name = name.strip()
    if not NAME_RE.fullmatch(name):
        raise HTTPException(400, "name: 2-64 chars of letters, digits, . _ -")
    if session.exec(select(ModelVersion).where(ModelVersion.name == name)).first():
        raise HTTPException(409, "a model with this name already exists")
    return name


class UploadUrlIn(BaseModel):
    name: str


@router.post("/models/upload-url")
def model_upload_url(body: UploadUrlIn, session: Session = Depends(get_session), _: User = Depends(admin_user)):
    """Step 1 of registering a model: where the browser should PUT the .onnx file. With Supabase this is
    a one-time signed URL straight into Storage, so large files never pass through the app server."""
    name = _check_new_name(session, body.name)
    key = _upload_key(name)
    url = storage.upload_url(key) if storage.remote else f"/api/models/upload-local?key={key}"
    return {"key": key, "url": url, "method": "PUT"}


@router.put("/models/upload-local", include_in_schema=False)
async def model_upload_local(key: str, request: Request, _: User = Depends(admin_user)):
    """Local-storage stand-in for the signed Supabase upload URL (development only)."""
    if storage.remote or not re.fullmatch(r"models/uploads/[A-Za-z0-9._-]{2,64}\.onnx", key):
        raise HTTPException(404)
    storage.save(key, await request.body(), "application/octet-stream")
    return {"ok": True}


class RegisterIn(BaseModel):
    name: str
    key: str
    conf: float = 0.35
    class_map: Optional[dict] = None
    notes: str = ""


@router.post("/models")
def register_model(body: RegisterIn, session: Session = Depends(get_session), _: User = Depends(admin_user)):
    """Step 2: validate the uploaded ONNX file (load it, read its class names) and register it."""
    name = _check_new_name(session, body.name)
    if body.key != _upload_key(name):
        raise HTTPException(400, "upload key does not match the model name")
    if not 0.01 <= body.conf <= 0.99:
        raise HTTPException(400, "conf must be between 0.01 and 0.99")
    try:
        det = eng.inspect_weights(body.key, body.class_map, body.conf, 640, name)
    except FileNotFoundError:
        raise HTTPException(400, "the file was not uploaded (or the upload failed); please try again")
    except Exception as e:
        storage.delete([body.key])
        eng.forget_cached(body.key)
        raise HTTPException(400, f"could not load the model: {e}. Export it with model.export(format='onnx').")
    m = ModelVersion(name=name, weights_path=body.key, sha256=file_sha256(eng.local_weights(body.key)),
                     conf=body.conf, imgsz=det.model.size[0], class_map=body.class_map or None,
                     classes=list(det.raw_names.values()), supported=sorted(det.supported), notes=body.notes)
    session.add(m)
    session.commit()
    session.refresh(m)
    return model_out(m)


class ModelUpdate(BaseModel):
    is_active: Optional[bool] = None
    exclusive: bool = True  # activating one model deactivates the others
    conf: Optional[float] = None
    class_map: Optional[dict] = None
    notes: Optional[str] = None


@router.patch("/models/{model_id}")
def update_model(model_id: int, body: ModelUpdate, session: Session = Depends(get_session),
                 _: User = Depends(admin_user)):
    m = session.get(ModelVersion, model_id)
    if not m:
        raise HTTPException(404, "model not found")
    previous = {x.id: x.is_active for x in session.exec(select(ModelVersion))}
    if body.class_map is not None:
        det = eng.inspect_weights(m.weights_path, body.class_map or None, m.conf, m.imgsz, m.name)
        m.class_map = body.class_map or None
        m.supported = sorted(det.supported)
    if body.conf is not None:
        if not 0.01 <= body.conf <= 0.99:
            raise HTTPException(400, "conf must be between 0.01 and 0.99")
        m.conf = body.conf
    if body.notes is not None:
        m.notes = body.notes
    if body.is_active is not None:
        if body.is_active and body.exclusive:
            for other in session.exec(select(ModelVersion).where(ModelVersion.id != m.id)):
                other.is_active = False
                session.add(other)
        m.is_active = body.is_active
        session.add(m)
        session.flush()
        if not session.exec(select(ModelVersion).where(ModelVersion.is_active == True)).first():  # noqa: E712
            session.rollback()
            raise HTTPException(400, "at least one model must stay active")
    session.add(m)
    session.commit()
    try:
        eng.reload()
    except Exception as e:  # restore the previous working set
        for x in session.exec(select(ModelVersion)):
            x.is_active = previous.get(x.id, False)
            session.add(x)
        session.commit()
        eng.reload()
        raise HTTPException(400, f"model could not be loaded, reverted: {e}")
    session.refresh(m)
    return model_out(m)


@router.delete("/models/{model_id}")
def delete_model(model_id: int, session: Session = Depends(get_session), _: User = Depends(admin_user)):
    m = session.get(ModelVersion, model_id)
    if not m:
        raise HTTPException(404, "model not found")
    if m.is_active:
        raise HTTPException(400, "deactivate the model before deleting it")
    key = m.weights_path
    session.delete(m)
    session.commit()
    if key.startswith("models/uploads/"):
        storage.delete([key])
        eng.forget_cached(key)
        (BACKEND_DIR / key).unlink(missing_ok=True)
    return {"deleted": model_id}


# ----------------------------------------------------------------------------- sites

class SiteIn(BaseModel):
    name: str
    location: str = ""
    required_ppe: list[str] = ["helmet", "vest"]


def _check_items(items: list[str]) -> list[str]:
    bad = [i for i in items if i not in PPE_ITEMS]
    if bad:
        raise HTTPException(400, f"unknown PPE items: {bad}")
    return [i for i in PPE_ITEMS if i in items]


def site_out(s: Site, session: Session) -> dict:
    count = len(session.exec(select(Inspection.id).where(Inspection.site_id == s.id)).all())
    return {"id": s.id, "name": s.name, "location": s.location, "required_ppe": s.required_ppe,
            "inspections": count, "created_at": iso(s.created_at)}


@router.get("/sites")
def list_sites(session: Session = Depends(get_session), _: User = Depends(current_user)):
    return [site_out(s, session) for s in session.exec(select(Site).order_by(Site.id))]


@router.post("/sites")
def create_site(body: SiteIn, session: Session = Depends(get_session), _: User = Depends(admin_user)):
    if not body.name.strip():
        raise HTTPException(400, "name is required")
    if session.exec(select(Site).where(Site.name == body.name.strip())).first():
        raise HTTPException(409, "site already exists")
    s = Site(name=body.name.strip(), location=body.location, required_ppe=_check_items(body.required_ppe))
    session.add(s)
    session.commit()
    session.refresh(s)
    return site_out(s, session)


@router.put("/sites/{site_id}")
def update_site(site_id: int, body: SiteIn, session: Session = Depends(get_session), _: User = Depends(admin_user)):
    s = session.get(Site, site_id)
    if not s:
        raise HTTPException(404, "site not found")
    s.name, s.location, s.required_ppe = body.name.strip(), body.location, _check_items(body.required_ppe)
    session.add(s)
    session.commit()
    session.refresh(s)
    return site_out(s, session)
