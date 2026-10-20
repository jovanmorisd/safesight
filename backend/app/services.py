"""Inspection processing and response shaping."""
from __future__ import annotations

import io
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete as sa_delete
from sqlmodel import Session, select

from ppe_core.annotate import crop
from ppe_core.policy import severity

from . import engine as eng
from .db import DetectionRow, Incident, Inspection, PersonRow, Site, User, iso, utcnow
from .storage import storage

log = logging.getLogger("ppe.services")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MAX_BYTES = 20 * 1024 * 1024
MAX_SIDE = 2560  # larger images are downscaled before storage/inference


class BadImage(ValueError):
    pass


def media_url(rel: str) -> str:
    return f"/media/{rel}" if rel else ""


def decode_image(data: bytes, filename: str) -> np.ndarray:
    if len(data) > MAX_BYTES:
        raise BadImage(f"{filename}: larger than {MAX_BYTES // (1024 * 1024)} MB")
    if Path(filename).suffix.lower() not in ALLOWED_EXT:
        raise BadImage(f"{filename}: unsupported file type (use jpg, png, bmp or webp)")
    try:
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im).convert("RGB")  # phone photos: apply the EXIF rotation
    except (UnidentifiedImageError, OSError, ValueError):
        raise BadImage(f"{filename}: could not be decoded as an image")
    if max(im.size) > MAX_SIDE:
        s = MAX_SIDE / max(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    return np.asarray(im)


def _jpeg(img: np.ndarray, quality: int) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _upload_all(files: dict[str, bytes]) -> None:
    """Store all files of one inspection; in parallel because remote storage is one request each."""
    if not storage.remote:
        for k, data in files.items():
            storage.save(k, data)
        return
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda kv: storage.save(*kv), files.items()))


def read_image(key: str) -> Optional[np.ndarray]:
    data = storage.read(key)
    return None if data is None else np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))


def process_image(session: Session, img: np.ndarray, filename: str, site: Optional[Site], user: User) -> Inspection:
    pipe = eng.pipeline()
    models = eng.active_models()
    required = list(site.required_ppe) if site else list(eng.config().default_required)
    res = pipe.run(img, required)

    # Every file lives under its owner's folder: users/<id>/originals|annotated|crops/...
    key = uuid.uuid4().hex[:12]
    base = f"users/{user.id}"
    files = {f"{base}/originals/{key}.jpg": _jpeg(img, 92), f"{base}/annotated/{key}.jpg": _jpeg(res.annotated, 88)}
    for pa in res.assessments:
        files[f"{base}/crops/{key}_{pa.person.idx}.jpg"] = _jpeg(crop(img, pa.person.box), 88)
    _upload_all(files)  # before the DB commit, so a failed upload leaves no half-saved inspection

    h, w = img.shape[:2]
    statuses = [pa.overall for pa in res.assessments]
    status = ("violation" if "violation" in statuses else "unknown" if "unknown" in statuses
              else "compliant" if statuses else "empty")
    insp = Inspection(
        user_id=user.id, site_id=site.id if site else None, filename=filename,
        image_path=f"{base}/originals/{key}.jpg",
        annotated_path=f"{base}/annotated/{key}.jpg",
        width=w, height=h, required=res.required, supported=res.supported,
        model_label=" + ".join(m.name for m in models), model_ids=[m.id for m in models],
        status=status, num_persons=len(statuses), num_violations=statuses.count("violation"),
        num_unknown=statuses.count("unknown"), num_compliant=statuses.count("compliant"),
        latency_ms=round(res.timings_ms.get("total", 0.0), 1),
        timings={k: round(v, 1) for k, v in res.timings_ms.items()},
    )
    session.add(insp)
    session.flush()

    for d in res.detections:
        session.add(DetectionRow(inspection_id=insp.id, label=d.cls, raw_label=d.raw_cls, conf=round(d.conf, 4),
                                 box=d.box.as_list(), source=d.source))
    for pa in res.assessments:
        p = pa.person
        crop_rel = f"{base}/crops/{key}_{p.idx}.jpg"
        row = PersonRow(inspection_id=insp.id, idx=p.idx, box=p.box.as_list(), conf=round(p.conf, 4),
                        has_pose=p.keypoints is not None, overall=pa.overall, missing=pa.missing,
                        uncertain=pa.uncertain, items={k: v.to_dict() for k, v in pa.items.items()},
                        crop_path=crop_rel)
        session.add(row)
        session.flush()
        if pa.overall == "violation":
            session.add(Incident(user_id=user.id, inspection_id=insp.id, person_id=row.id, site_id=insp.site_id,
                                 kind="violation", items=pa.missing, severity=severity(pa.missing)))
        elif pa.overall == "unknown" and pa.uncertain:
            session.add(Incident(user_id=user.id, inspection_id=insp.id, person_id=row.id, site_id=insp.site_id,
                                 kind="review", items=pa.uncertain, severity="low"))
    session.commit()
    session.refresh(insp)
    return insp


def delete_inspection(session: Session, i: Inspection) -> None:
    persons = session.exec(select(PersonRow).where(PersonRow.inspection_id == i.id)).all()
    keys = [i.image_path, i.annotated_path] + [p.crop_path for p in persons]
    # Children first, in foreign-key order (Postgres enforces it; SQLite would not notice).
    for model in (Incident, DetectionRow, PersonRow):
        session.exec(sa_delete(model).where(model.inspection_id == i.id))
    session.exec(sa_delete(Inspection).where(Inspection.id == i.id))
    session.commit()
    session.expire_all()
    storage.delete(keys)


def purge_older_than(session: Session, days: int) -> int:
    """Retention: delete inspections (rows + images) older than `days`. Returns how many."""
    if days <= 0:
        return 0
    cutoff = utcnow() - timedelta(days=days)
    old = session.exec(select(Inspection).where(Inspection.created_at < cutoff)).all()
    for i in old:
        delete_inspection(session, i)
    if old:
        log.info("retention: deleted %d inspections older than %d days", len(old), days)
    return len(old)


# ----------------------------------------------------------------------------- serializers

def site_names(session: Session) -> dict[int, str]:
    return {s.id: s.name for s in session.exec(select(Site))}


def user_names(session: Session) -> dict[int, str]:
    return {u.id: u.name or u.email for u in session.exec(select(User))}


def inspection_summary(i: Inspection, names: dict[int, str], owners: Optional[dict[int, str]] = None) -> dict:
    return {
        "id": i.id, "filename": i.filename, "site_id": i.site_id, "site": names.get(i.site_id or -1, "-"),
        "owner": (owners or {}).get(i.user_id or -1), "created_at": iso(i.created_at), "status": i.status,
        "num_persons": i.num_persons, "num_violations": i.num_violations, "num_unknown": i.num_unknown,
        "num_compliant": i.num_compliant, "latency_ms": i.latency_ms, "model_label": i.model_label,
        "image_url": media_url(i.image_path), "annotated_url": media_url(i.annotated_path),
        "width": i.width, "height": i.height,
    }


def person_out(p: PersonRow) -> dict:
    return {"id": p.id, "idx": p.idx, "box": p.box, "conf": p.conf, "has_pose": p.has_pose,
            "overall": p.overall, "missing": p.missing, "uncertain": p.uncertain, "items": p.items,
            "crop_url": media_url(p.crop_path)}


def inspection_detail(session: Session, i: Inspection) -> dict:
    names = site_names(session)
    owners = user_names(session)
    persons = session.exec(select(PersonRow).where(PersonRow.inspection_id == i.id).order_by(PersonRow.idx)).all()
    dets = session.exec(select(DetectionRow).where(DetectionRow.inspection_id == i.id)).all()
    incs = session.exec(select(Incident).where(Incident.inspection_id == i.id)).all()
    return {
        **inspection_summary(i, names, owners),
        "required": i.required, "supported": i.supported, "timings": i.timings,
        "persons": [person_out(p) for p in persons],
        "detections": [{"cls": d.label, "raw_cls": d.raw_label, "conf": d.conf, "box": d.box, "source": d.source}
                       for d in dets],
        "incidents": [incident_out(x, None, names) for x in incs],
    }


def incident_out(x: Incident, person: Optional[PersonRow], names: dict[int, str]) -> dict:
    return {
        "id": x.id, "inspection_id": x.inspection_id, "person_id": x.person_id, "site_id": x.site_id,
        "site": names.get(x.site_id or -1, "-"), "kind": x.kind, "items": x.items, "severity": x.severity,
        "status": x.status, "reviewer": x.reviewer, "notes": x.notes,
        "created_at": iso(x.created_at),
        "reviewed_at": iso(x.reviewed_at),
        "person": person_out(person) if person else None,
    }
