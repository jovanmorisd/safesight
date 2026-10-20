from __future__ import annotations

import csv
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlmodel import Session, select

from ppe_core.types import PPE_ITEMS

from ..auth import current_user, is_admin, scope
from ..db import Incident, Inspection, PersonRow, User, as_utc, get_session
from ..services import site_names
from ..storage import storage

router = APIRouter(prefix="/api/reports", tags=["reports"])
TEAL = colors.HexColor("#0D9488")


def _window(start: Optional[date], end: Optional[date]) -> tuple[datetime, datetime]:
    end_dt = datetime.combine(end or date.today(), datetime.min.time(), timezone.utc) + timedelta(days=1)
    start_dt = datetime.combine(start, datetime.min.time(), timezone.utc) if start else end_dt - timedelta(days=30)
    if start_dt >= end_dt:
        raise HTTPException(400, "start must be before end")
    return start_dt, end_dt


def _load(session: Session, start: datetime, end: datetime, site_id: Optional[int], user: User):
    q = scope(select(Inspection), Inspection, user).where(Inspection.created_at >= start, Inspection.created_at < end)
    if site_id:
        q = q.where(Inspection.site_id == site_id)
    insps = session.exec(q.order_by(Inspection.created_at)).all()
    ids = [i.id for i in insps]
    persons = session.exec(select(PersonRow).where(PersonRow.inspection_id.in_(ids))).all() if ids else []
    incs = session.exec(select(Incident).where(Incident.inspection_id.in_(ids))).all() if ids else []
    return insps, persons, incs


@router.get("/incidents.csv")
def incidents_csv(start: Optional[date] = None, end: Optional[date] = None, site_id: Optional[int] = None,
                  session: Session = Depends(get_session), user: User = Depends(current_user)):
    s, e = _window(start, end)
    insps, persons, incs = _load(session, s, e, site_id, user)
    by_insp = {i.id: i for i in insps}
    by_person = {p.id: p for p in persons}
    names = site_names(session)
    rows = []
    for x in incs:
        i, p = by_insp.get(x.inspection_id), by_person.get(x.person_id)
        rows.append({
            "incident_id": x.id, "created_at_utc": as_utc(x.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            "site": names.get(x.site_id or -1, "-"), "inspection_id": x.inspection_id,
            "image": i.filename if i else "", "person": (p.idx + 1) if p else "", "kind": x.kind,
            "items": ", ".join(x.items), "severity": x.severity, "status": x.status,
            "reviewer": x.reviewer, "notes": x.notes,
            "model": i.model_label if i else "",
            "reasons": "; ".join(f"{k}: {p.items[k]['reason']}" for k in x.items if p and k in p.items),
        })
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["incident_id", "created_at_utc", "site", "inspection_id", "image", "person",
                                             "kind", "items", "severity", "status", "reviewer", "notes", "model",
                                             "reasons"])
    writer.writeheader()
    writer.writerows(rows)
    fname = f"ppe_incidents_{s:%Y%m%d}_{(e - timedelta(days=1)):%Y%m%d}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/summary.pdf")
def summary_pdf(start: Optional[date] = None, end: Optional[date] = None, site_id: Optional[int] = None,
                session: Session = Depends(get_session), user: User = Depends(current_user)):
    s, e = _window(start, end)
    insps, persons, incs = _load(session, s, e, site_id, user)
    names = site_names(session)
    last_day = e - timedelta(days=1)

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=TEAL, alignment=0, fontSize=20)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=colors.HexColor("#0F172A"))
    body = styles["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#475569"))

    def table(data, widths, header_bg=TEAL):
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), header_bg), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    c = sum(i.num_compliant for i in insps)
    v = sum(i.num_violations for i in insps)
    u = sum(i.num_unknown for i in insps)
    rate = f"{100 * c / (c + v):.1f}%" if c + v else "n/a"
    viol = [x for x in incs if x.kind == "violation"]
    confirmed = sum(1 for x in viol if x.status in ("confirmed", "resolved"))
    fp = sum(1 for x in viol if x.status == "false_positive")

    story = [
        Paragraph("PPE Compliance Report", h1),
        Paragraph(f"Period: {s:%d %b %Y} – {last_day:%d %b %Y} &nbsp;·&nbsp; Site: "
                  f"{names.get(site_id, 'All sites') if site_id else 'All sites'} &nbsp;·&nbsp; "
                  f"{'All users' if is_admin(user) else (user.name or user.email)} &nbsp;·&nbsp; "
                  f"Generated {datetime.now():%d %b %Y %H:%M}", small),
        Spacer(1, 6 * mm),
        Paragraph("Summary", h2),
        table([["Inspections", "Workers assessed", "Compliant", "Violations", "Unknown", "Compliance rate*"],
               [len(insps), c + v + u, c, v, u, rate]], [28 * mm] * 6),
        Paragraph("*Compliance rate = compliant / (compliant + violation); workers whose required PPE could not "
                  "be assessed (unknown) are excluded and listed separately.", small),
        Spacer(1, 4 * mm),
        table([["Violation incidents", "Open", "Confirmed", "False positive", "Review precision"],
               [len(viol), sum(1 for x in viol if x.status == "open"), confirmed, fp,
                f"{100 * confirmed / (confirmed + fp):.1f}%" if confirmed + fp else "n/a"]], [34 * mm] * 5),
        Spacer(1, 4 * mm),
        Paragraph("PPE status by item", h2),
        Paragraph("Counted only for workers whose site required the item.", small),
        Spacer(1, 2 * mm),
    ]
    required = {i.id: set(i.required or []) for i in insps}
    item_rows = [["Item", "Worn", "Absent", "Unknown", "Not checked"]]
    for it in PPE_ITEMS:
        cnt = {"worn": 0, "absent": 0, "unknown": 0, "not_checked": 0}
        for p in persons:
            st = (p.items or {}).get(it, {}).get("state")
            if st in cnt and it in required.get(p.inspection_id, ()):
                cnt[st] += 1
        if sum(cnt.values()):
            item_rows.append([it.capitalize(), cnt["worn"], cnt["absent"], cnt["unknown"], cnt["not_checked"]])
    story.append(table(item_rows, [40 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm]))

    story += [Spacer(1, 4 * mm), Paragraph("Violation incidents", h2)]
    by_person = {p.id: p for p in persons}
    by_insp = {i.id: i for i in insps}
    if viol:
        rows = [["#", "Date (UTC)", "Site", "Image", "Missing", "Severity", "Status", "Evidence"]]
        recent = sorted(viol, key=lambda x: as_utc(x.created_at), reverse=True)[:40]
        keys = [by_person[x.person_id].crop_path for x in recent if x.person_id in by_person]
        with ThreadPoolExecutor(max_workers=8) as pool:  # remote storage: fetch crops in parallel
            crops = dict(zip(keys, pool.map(storage.read, keys)))
        for x in recent:
            p, i = by_person.get(x.person_id), by_insp.get(x.inspection_id)
            img = ""
            data = crops.get(p.crop_path) if p else None
            if data:
                img = Image(io.BytesIO(data))
                ratio = img.imageHeight / max(1, img.imageWidth)
                img.drawWidth, img.drawHeight = (14 * mm / ratio, 14 * mm) if ratio >= 1 else (18 * mm, 18 * mm * ratio)
            rows.append([x.id, f"{as_utc(x.created_at):%d %b %H:%M}", names.get(x.site_id or -1, "-"),
                         Paragraph((i.filename if i else "")[:28], small), Paragraph(", ".join(x.items), small), x.severity,
                         x.status.replace("_", " "), img])
        story.append(table(rows, [10 * mm, 24 * mm, 24 * mm, 34 * mm, 26 * mm, 17 * mm, 20 * mm, 22 * mm]))
        if len(viol) > 40:
            story.append(Paragraph(f"Showing the 40 most recent of {len(viol)} incidents; export CSV for all.", small))
    else:
        story.append(Paragraph("No violations recorded in this period.", body))

    models = sorted({i.model_label for i in insps if i.model_label})
    story += [Spacer(1, 6 * mm), Paragraph("Method & limitations", h2), Paragraph(
        f"Models: {', '.join(models) or 'n/a'}. Each worker is assessed per PPE item as worn, absent, unknown "
        "(body region not visible) or not checked (the active model cannot detect the item). A violation is raised "
        "only when a required item is judged absent. Results are automated decision support and must be reviewed "
        "by a person; detections can fail for small, occluded or unusually dressed workers.", small)]

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm,
                      bottomMargin=14 * mm, title="PPE Compliance Report").build(story)
    buf.seek(0)
    fname = f"ppe_report_{s:%Y%m%d}_{last_day:%Y%m%d}.pdf"
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})
