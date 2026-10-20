from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, func, select

from ..auth import can_access, current_user, scope
from ..db import Incident, PersonRow, User, get_session, utcnow
from ..services import incident_out, site_names

router = APIRouter(prefix="/api/incidents", tags=["incidents"])
STATUSES = {"open", "confirmed", "false_positive", "resolved"}


class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_incidents(status: Optional[str] = None, kind: Optional[str] = None, site_id: Optional[int] = None,
                   limit: int = Query(50, le=500), offset: int = 0, session: Session = Depends(get_session),
                   user: User = Depends(current_user)):
    q = scope(select(Incident), Incident, user)
    cq = scope(select(func.count()).select_from(Incident), Incident, user)
    for col, val in ((Incident.status, status), (Incident.kind, kind), (Incident.site_id, site_id)):
        if val:
            q, cq = q.where(col == val), cq.where(col == val)
    rows = session.exec(q.order_by(Incident.created_at.desc()).offset(offset).limit(limit)).all()
    persons = {p.id: p for p in session.exec(select(PersonRow).where(PersonRow.id.in_([r.person_id for r in rows])))}
    names = site_names(session)
    counts = dict(session.exec(scope(select(Incident.status, func.count()), Incident, user).group_by(Incident.status)).all())
    return {"total": session.exec(cq).one(), "counts": counts,
            "items": [incident_out(r, persons.get(r.person_id), names) for r in rows]}


@router.patch("/{incident_id}")
def update_incident(incident_id: int, body: IncidentUpdate, session: Session = Depends(get_session),
                    user: User = Depends(current_user)):
    x = session.get(Incident, incident_id)
    if not x or not can_access(user, x.user_id):
        raise HTTPException(404, "incident not found")
    if body.status is not None:
        if body.status not in STATUSES:
            raise HTTPException(400, f"status must be one of {sorted(STATUSES)}")
        x.status = body.status
        x.reviewed_at = utcnow() if body.status != "open" else None
        x.reviewer = (user.name or user.email) if body.status != "open" else ""
    if body.notes is not None:
        x.notes = body.notes
    session.add(x)
    session.commit()
    session.refresh(x)
    return incident_out(x, session.get(PersonRow, x.person_id), site_names(session))
