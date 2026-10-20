from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlmodel import Session, func, select

from ..auth import can_access, current_user, scope
from ..db import Inspection, Site, User, get_session
from ..services import (BadImage, decode_image, delete_inspection, inspection_detail, inspection_summary,
                        process_image, site_names, user_names)

router = APIRouter(prefix="/api/inspections", tags=["inspections"])


def _owned(session: Session, inspection_id: int, user: User) -> Inspection:
    i = session.get(Inspection, inspection_id)
    if not i or not can_access(user, i.user_id):
        raise HTTPException(404, "inspection not found")
    return i


@router.post("")
def create_inspections(files: list[UploadFile] = File(...), site_id: Optional[int] = Form(None),
                       session: Session = Depends(get_session), user: User = Depends(current_user)):
    site = session.get(Site, site_id) if site_id else session.exec(select(Site)).first()
    if site_id and site is None:
        raise HTTPException(404, "site not found")
    created, errors = [], []
    for f in files:
        try:
            img = decode_image(f.file.read(), f.filename or "upload.jpg")
            created.append(process_image(session, img, f.filename or "upload.jpg", site, user))
        except BadImage as e:
            errors.append(str(e))
    if not created and errors:
        raise HTTPException(400, "; ".join(errors))
    names, owners = site_names(session), user_names(session)
    return {"inspections": [inspection_summary(i, names, owners) for i in created], "errors": errors}


@router.get("")
def list_inspections(site_id: Optional[int] = None, status: Optional[str] = None, q: Optional[str] = None,
                     limit: int = Query(30, le=200), offset: int = 0, session: Session = Depends(get_session),
                     user: User = Depends(current_user)):
    conds = []
    if site_id:
        conds.append(Inspection.site_id == site_id)
    if status:
        conds.append(Inspection.status == status)
    if q:
        conds.append(Inspection.id == int(q) if q.isdigit() else Inspection.filename.contains(q))
    query = scope(select(Inspection).where(*conds), Inspection, user)
    cq = scope(select(func.count()).select_from(Inspection).where(*conds), Inspection, user)
    rows = session.exec(query.order_by(Inspection.created_at.desc()).offset(offset).limit(limit)).all()
    names, owners = site_names(session), user_names(session)
    return {"total": session.exec(cq).one(), "items": [inspection_summary(i, names, owners) for i in rows]}


@router.get("/{inspection_id}")
def get_inspection(inspection_id: int, session: Session = Depends(get_session), user: User = Depends(current_user)):
    return inspection_detail(session, _owned(session, inspection_id, user))


@router.delete("/{inspection_id}")
def remove_inspection(inspection_id: int, session: Session = Depends(get_session),
                      user: User = Depends(current_user)):
    delete_inspection(session, _owned(session, inspection_id, user))
    return {"deleted": inspection_id}
