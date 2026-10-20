from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from ppe_core.types import PPE_ITEMS

from ..auth import current_user, scope
from ..db import Incident, Inspection, PersonRow, User, as_utc, get_session, utcnow
from ..services import inspection_summary, site_names, user_names

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _rate(compliant: int, violation: int) -> Optional[float]:
    total = compliant + violation
    return round(100 * compliant / total, 1) if total else None


def _period(session: Session, start: datetime, end: datetime, site_id: Optional[int], user: User):
    q = scope(select(Inspection), Inspection, user).where(Inspection.created_at >= start, Inspection.created_at < end)
    if site_id:
        q = q.where(Inspection.site_id == site_id)
    return session.exec(q).all()


@router.get("")
def stats(days: int = Query(30, ge=1, le=365), site_id: Optional[int] = None,
          session: Session = Depends(get_session), user: User = Depends(current_user)):
    now = utcnow()
    start, prev_start = now - timedelta(days=days), now - timedelta(days=2 * days)
    cur = _period(session, start, now + timedelta(seconds=1), site_id, user)
    prev = _period(session, prev_start, start, site_id, user)

    def agg(rows):
        c = sum(i.num_compliant for i in rows)
        v = sum(i.num_violations for i in rows)
        u = sum(i.num_unknown for i in rows)
        return c, v, u, c + v + u

    c, v, u, n = agg(cur)
    pc, pv, pu, pn = agg(prev)
    rate, prev_rate = _rate(c, v), _rate(pc, pv)
    unknown_rate = round(100 * u / n, 1) if n else None
    prev_unknown = round(100 * pu / pn, 1) if pn else None

    iq = scope(select(Incident), Incident, user)
    if site_id:
        iq = iq.where(Incident.site_id == site_id)
    incidents = session.exec(iq).all()
    open_now = sum(1 for x in incidents if x.status == "open")
    opened_cur = sum(1 for x in incidents if as_utc(x.created_at) >= start)
    opened_prev = sum(1 for x in incidents if prev_start <= as_utc(x.created_at) < start)
    confirmed = sum(1 for x in incidents if x.kind == "violation" and x.status in ("confirmed", "resolved"))
    false_pos = sum(1 for x in incidents if x.kind == "violation" and x.status == "false_positive")

    # Per-item states for people in the current period, counting only items their site required
    required = {i.id: set(i.required or []) for i in cur}
    persons = session.exec(select(PersonRow).where(PersonRow.inspection_id.in_(list(required)))).all() if cur else []
    per_item: dict[str, Counter] = {it: Counter() for it in PPE_ITEMS}
    for p in persons:
        for it, info in (p.items or {}).items():
            if it in per_item and it in required.get(p.inspection_id, ()):
                per_item[it][info.get("state", "unknown")] += 1

    # Time series: daily for the window, monthly for the last 12 months
    daily: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for i in cur:
        d = daily[as_utc(i.created_at).strftime("%Y-%m-%d")]
        d[0] += i.num_violations; d[1] += i.num_compliant; d[2] += i.num_unknown  # noqa: E702
    daily_series = []
    for k in range(days - 1, -1, -1):
        key = (now - timedelta(days=k)).strftime("%Y-%m-%d")
        vv, cc, uu = daily.get(key, [0, 0, 0])
        daily_series.append({"key": key, "violations": vv, "compliant": cc, "unknown": uu,
                             "rate": _rate(cc, vv)})

    year = _period(session, now - timedelta(days=366), now + timedelta(seconds=1), site_id, user)
    monthly: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for i in year:
        m = monthly[as_utc(i.created_at).strftime("%Y-%m")]
        m[0] += i.num_violations; m[1] += i.num_compliant; m[2] += i.num_unknown  # noqa: E702
    monthly_series = []
    y, mo = now.year, now.month
    for _ in range(12):
        key = f"{y:04d}-{mo:02d}"
        vv, cc, uu = monthly.get(key, [0, 0, 0])
        monthly_series.append({"key": key, "violations": vv, "compliant": cc, "unknown": uu, "rate": _rate(cc, vv)})
        mo -= 1
        if mo == 0:
            y, mo = y - 1, 12
    monthly_series.reverse()

    by_model: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for i in cur:
        bm = by_model[i.model_label or "-"]
        bm[0] += i.num_compliant; bm[1] += i.num_violations; bm[2] += 1  # noqa: E702

    names = site_names(session)
    latest_q = scope(select(Inspection), Inspection, user).order_by(Inspection.created_at.desc())
    if site_id:
        latest_q = latest_q.where(Inspection.site_id == site_id)
    latest = session.exec(latest_q.where(Inspection.num_persons > 0)).first() or session.exec(latest_q).first()

    def delta(a, b):
        return None if a is None or b is None else round(a - b, 1)

    return {
        "days": days,
        "kpis": {
            "compliance_rate": rate, "compliance_delta": delta(rate, prev_rate),
            "open_incidents": open_now, "incidents_opened": opened_cur,
            "incidents_delta": opened_cur - opened_prev,
            "unknown_rate": unknown_rate, "unknown_delta": delta(unknown_rate, prev_unknown),
            "inspections": len(cur), "persons": n, "violations": v, "compliant": c, "unknown": u,
            "review_precision": round(100 * confirmed / (confirmed + false_pos), 1) if confirmed + false_pos else None,
            "reviewed": confirmed + false_pos,
            "avg_latency_ms": round(sum(i.latency_ms for i in cur) / len(cur), 1) if cur else None,
        },
        "per_item": {it: {"worn": per_item[it]["worn"], "absent": per_item[it]["absent"],
                          "unknown": per_item[it]["unknown"], "not_checked": per_item[it]["not_checked"]}
                     for it in PPE_ITEMS},
        "daily": daily_series,
        "monthly": monthly_series,
        "by_model": [{"model": k, "compliance_rate": _rate(vals[0], vals[1]), "inspections": vals[2]}
                     for k, vals in by_model.items()],
        "latest": inspection_summary(latest, names, user_names(session)) if latest else None,
    }
