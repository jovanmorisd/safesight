"""Person-level PPE association: from "a helmet is in the image" to "worker 2 is wearing one".

Each worker's body regions (head, face, torso, hands, feet) come from pose keypoints, plus
head/face/hands/foot boxes when the detector provides them; workers without keypoints fall back
to fixed bands of their person box. A PPE box counts as worn only when it sits on the matching
region of that specific worker (one helmet per head, via Hungarian assignment). Regions that are
not visible give "unknown" instead of a false "absent", and a helmet next to a wrist is reported
as carried, not worn.

Every item ends in one of: worn | absent | unknown | not_checked (model cannot detect it).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

from .types import PPE_ITEMS, Box, Detection, ItemAssessment, Person, PersonAssessment

# COCO-17 keypoint indices
NOSE, LEYE, REYE, LEAR, REAR = 0, 1, 2, 3, 4
LSHO, RSHO, LELB, RELB, LWRI, RWRI = 5, 6, 7, 8, 9, 10
LHIP, RHIP, LKNE, RKNE, LANK, RANK = 11, 12, 13, 14, 15, 16

# Which body region each PPE item must sit on.
ITEM_REGION: dict[str, str] = {
    "helmet": "head", "earmuffs": "head",
    "goggles": "face", "mask": "face",
    "vest": "torso",
    "gloves": "hands",
    "boots": "feet",
}
# Items that come in pairs: several boxes may belong to one person.
PAIRED = {"gloves", "boots"}
# Detector body-part classes that can stand in for a missing keypoint region.
PART_FOR_REGION = {"head": "head", "face": "face", "hands": "hands", "feet": "foot"}


@dataclass
class Region:
    boxes: list[Box]
    visible: bool
    visibility: float = 1.0
    why: str = ""  # explanation when not visible


def overlap(det: Box, region: Box) -> float:
    """Intersection over the smaller of the two areas.

    Works both for a small helmet inside a generous head region and for a large vest that
    covers a narrow (side-view) torso region."""
    inter = det.intersection(region)
    denom = min(det.area, region.area)
    return inter / denom if denom > 0 else 0.0


# ----------------------------------------------------------------------------- regions

def regions_from_box(p: Person, img_w: int, img_h: int) -> dict[str, Region]:
    """Fixed bands of the person box, for workers without keypoints. Only crude visibility checks."""
    b = p.box
    w, h = b.w, b.h
    r = {
        "head": Region([Box(b.x1, b.y1 - 0.06 * h, b.x2, b.y1 + 0.22 * h)], True),
        "face": Region([Box(b.x1 + 0.1 * w, b.y1 + 0.03 * h, b.x2 - 0.1 * w, b.y1 + 0.2 * h)], True),
        "torso": Region([Box(b.x1, b.y1 + 0.18 * h, b.x2, b.y1 + 0.62 * h)], True),
        "hands": Region([Box(b.x1 - 0.05 * w, b.y1 + 0.3 * h, b.x2 + 0.05 * w, b.y1 + 0.75 * h)], True),
        "feet": Region([Box(b.x1, b.y1 + 0.82 * h, b.x2, b.y2 + 0.04 * h)], True),
    }
    if b.y2 >= img_h - 3 or (w > 0 and h / w < 1.3):
        r["feet"] = Region(r["feet"].boxes, False, 0.0, "lower body cut off or not upright")
    if b.y1 <= 2:
        r["head"] = Region(r["head"].boxes, False, 0.0, "head cut off by image border")
        r["face"] = Region(r["face"].boxes, False, 0.0, "head cut off by image border")
    return r


def _kp(kps: np.ndarray, i: int, thr: float) -> Optional[np.ndarray]:
    return kps[i, :2] if kps[i, 2] >= thr else None


def _square(c: np.ndarray, r: float) -> Box:
    return Box(float(c[0] - r), float(c[1] - r), float(c[0] + r), float(c[1] + r))


def regions_from_pose(p: Person, kp_thr: float, parts: dict[str, list[Box]],
                      img_w: int, img_h: int) -> dict[str, Region]:
    """Regions from keypoints, with detector body-part boxes as extra evidence."""
    if p.keypoints is None:
        return regions_from_box(p, img_w, img_h)
    k = p.keypoints
    b = p.box
    lsho, rsho = _kp(k, LSHO, kp_thr), _kp(k, RSHO, kp_thr)
    s = float(np.linalg.norm(lsho - rsho)) if lsho is not None and rsho is not None else 0.0
    if s < 0.08 * b.h:  # side view or missing shoulder: fall back to a body-height scale
        s = max(s, 0.22 * b.h)

    regions: dict[str, Region] = {}

    # Head & face ------------------------------------------------------------------
    head_pts = [k[i, :2] for i in (NOSE, LEYE, REYE, LEAR, REAR) if k[i, 2] >= kp_thr]
    face_pts = [k[i, :2] for i in (NOSE, LEYE, REYE) if k[i, 2] >= kp_thr]
    if head_pts:
        pts = np.array(head_pts)
        c = pts.mean(axis=0)
        spread = float(np.ptp(pts, axis=0).max()) if len(pts) > 1 else 0.0
        hs = max(spread * 1.6, 0.55 * s, 0.1 * b.h)
        vis = float(np.mean([k[i, 2] for i in (NOSE, LEYE, REYE, LEAR, REAR) if k[i, 2] >= kp_thr]))
        regions["head"] = Region([Box(c[0] - 0.75 * hs, c[1] - 1.3 * hs, c[0] + 0.75 * hs, c[1] + 0.5 * hs)], True, vis)
        if face_pts:
            fc = np.array(face_pts).mean(axis=0)
            regions["face"] = Region([Box(fc[0] - 0.6 * hs, fc[1] - 0.5 * hs, fc[0] + 0.6 * hs, fc[1] + 0.8 * hs)], True, vis)
        else:
            regions["face"] = Region([], False, 0.0, "face turned away")
    else:
        regions["head"] = Region([], False, 0.0, "head keypoints not visible")
        regions["face"] = Region([], False, 0.0, "head keypoints not visible")

    # Torso ------------------------------------------------------------------------
    torso_idx = [i for i in (LSHO, RSHO, LHIP, RHIP) if k[i, 2] >= kp_thr]
    if any(i in torso_idx for i in (LSHO, RSHO)) and len(torso_idx) >= 2:
        pts = k[torso_idx, :2]
        x1, y1 = pts.min(axis=0)
        x2, y2 = pts.max(axis=0)
        if not any(i in torso_idx for i in (LHIP, RHIP)):
            y2 = y1 + 1.4 * s  # hips hidden: extend down from the shoulders
        pad = 0.15 * s
        vis = float(np.mean(k[torso_idx, 2]))
        regions["torso"] = Region([Box(x1 - pad, y1 - 0.1 * s, x2 + pad, y2 + 0.1 * s)], True, vis)
    else:
        regions["torso"] = Region([], False, 0.0, "shoulders/hips not visible")

    # Hands & feet (one sub-region per visible limb end) ---------------------------
    def limb_ends(ends: Iterable[tuple[int, int]], push: float, radius: float) -> list[Box]:
        out = []
        for end, joint in ends:
            e = _kp(k, end, kp_thr)
            if e is None:
                continue
            j = _kp(k, joint, kp_thr)
            c = e + push * (e - j) if j is not None else e
            out.append(_square(c, radius * s))
        return out

    hand_boxes = limb_ends(((LWRI, LELB), (RWRI, RELB)), 0.3, 0.32)
    foot_boxes = limb_ends(((LANK, LKNE), (RANK, RKNE)), 0.25, 0.32)
    regions["hands"] = Region(hand_boxes, bool(hand_boxes), 1.0 if hand_boxes else 0.0,
                              "" if hand_boxes else "wrists not visible")
    regions["feet"] = Region(foot_boxes, bool(foot_boxes), 1.0 if foot_boxes else 0.0,
                             "" if foot_boxes else "ankles not visible")

    # Detector body-part boxes can reveal a region that the keypoints missed ----------
    coarse = regions_from_box(p, img_w, img_h)
    for region, part in PART_FOR_REGION.items():
        found = [pb for pb in parts.get(part, []) if pb.ioa(coarse[region].boxes[0]) >= 0.5]
        if not found:
            continue
        if region == "head":  # head boxes exclude most of the helmet; extend upwards
            found = [Box(pb.x1 - 0.15 * pb.w, pb.y1 - 0.5 * pb.h, pb.x2 + 0.15 * pb.w, pb.y2) for pb in found]
        if region in ("hands", "feet"):
            regions[region] = Region(regions[region].boxes + found, True, max(regions[region].visibility, 0.8))
        elif not regions[region].visible:
            regions[region] = Region(found[:1], True, 0.8)
    return regions


# ----------------------------------------------------------------------------- matching

def linear_sum_assignment(cost: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Minimum-cost assignment (Hungarian algorithm, O(n^3)); same contract as scipy's version.
    Kept here so the app does not need scipy (~100 MB) for a few people x a few helmets."""
    cost = np.asarray(cost, dtype=float)
    transposed = cost.shape[0] > cost.shape[1]
    if transposed:
        cost = cost.T
    n, m = cost.shape
    if n == 0:
        return np.zeros(0, int), np.zeros(0, int)
    INF = float("inf")
    u, v = np.zeros(n + 1), np.zeros(m + 1)
    p, way = np.zeros(m + 1, int), np.zeros(m + 1, int)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = np.full(m + 1, INF), np.zeros(m + 1, bool)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1, j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    rows = np.array([p[j] - 1 for j in range(1, m + 1) if p[j]], int)
    cols = np.array([j - 1 for j in range(1, m + 1) if p[j]], int)
    if transposed:
        rows, cols = cols, rows
    order = np.argsort(rows)
    return rows[order], cols[order]


def _match_single(persons: list[Person], regions: list[dict[str, Region]], dets: list[Detection],
                  region_name: str, min_score: float) -> dict[int, Detection]:
    """One item per person (helmet, vest, ...): Hungarian assignment on overlap score."""
    if not persons or not dets:
        return {}
    score = np.zeros((len(persons), len(dets)))
    for pi, reg in enumerate(regions):
        r = reg[region_name]
        if not r.visible:
            continue
        for di, d in enumerate(dets):
            s = max((overlap(d.box, rb) for rb in r.boxes), default=0.0)
            if region_name == "head":  # reject boxes far too large/small to be on this head
                rw = r.boxes[0].w if r.boxes else 0
                if rw and not (0.15 * rw <= d.box.w <= 1.8 * rw):
                    s = 0.0
            score[pi, di] = s
    rows, cols = linear_sum_assignment(-score)
    return {persons[r].idx: dets[c] for r, c in zip(rows, cols) if score[r, c] >= min_score}


def _match_paired(persons: list[Person], regions: list[dict[str, Region]], dets: list[Detection],
                  region_name: str, min_score: float) -> dict[int, dict[int, Detection]]:
    """Gloves/boots: each detection goes to the best (person, limb) slot; one per slot."""
    slots: list[tuple[float, int, int, int]] = []  # (score, person_idx, slot_idx, det_idx)
    for p, reg in zip(persons, regions):
        r = reg[region_name]
        if not r.visible:
            continue
        for si, rb in enumerate(r.boxes):
            for di, d in enumerate(dets):
                s = overlap(d.box, rb)
                if s >= min_score:
                    slots.append((s, p.idx, si, di))
    slots.sort(reverse=True)
    used_dets: set[int] = set()
    used_slots: set[tuple[int, int]] = set()
    out: dict[int, dict[int, Detection]] = {}
    for s, pidx, si, di in slots:
        if di in used_dets or (pidx, si) in used_slots:
            continue
        used_dets.add(di)
        used_slots.add((pidx, si))
        out.setdefault(pidx, {})[si] = dets[di]
    return out


# ----------------------------------------------------------------------------- public API

def assess(persons: list[Person], detections: list[Detection], supported: set[str],
           img_w: int, img_h: int, min_ioa: float = 0.3,
           kp_thr: float = 0.4, min_person_height: int = 48) -> list[PersonAssessment]:
    """Return one PersonAssessment per person with a state for every PPE item."""
    by_cls: dict[str, list[Detection]] = {}
    for d in detections:
        by_cls.setdefault(d.cls, []).append(d)
    results = [PersonAssessment(person=p) for p in persons]

    parts = {part: [d.box for d in by_cls.get(part, [])] for part in ("head", "face", "hands", "foot")}
    regions = [regions_from_pose(p, kp_thr, parts, img_w, img_h) for p in persons]

    tiny = {p.idx for p in persons if p.box.h < min_person_height}

    for item in PPE_ITEMS:
        region_name = ITEM_REGION[item]
        dets = by_cls.get(item, [])
        if item in PAIRED:
            matches_p = _match_paired(persons, regions, dets, region_name, min_ioa)
        else:
            matches_s = _match_single(persons, regions, dets, region_name, min_ioa)

        for pa, reg in zip(results, regions):
            p = pa.person
            r = reg[region_name]
            if item not in supported:
                pa.items[item] = ItemAssessment(item, "not_checked", reason="model cannot detect this item")
            elif p.idx in tiny:
                pa.items[item] = ItemAssessment(item, "unknown", reason=f"person too small ({int(p.box.h)}px)")
            elif not r.visible:
                pa.items[item] = ItemAssessment(item, "unknown", reason=r.why or f"{region_name} not visible")
            elif item in PAIRED:
                got = matches_p.get(p.idx, {})
                n_vis, n_got = len(r.boxes), len(got)
                if n_got and n_got >= min(n_vis, 2):
                    best = max(got.values(), key=lambda d: d.conf)
                    pa.items[item] = ItemAssessment(item, "worn", best.conf, f"on {n_got} of {n_vis} visible {region_name}", best.box)
                elif n_got:
                    best = max(got.values(), key=lambda d: d.conf)
                    pa.items[item] = ItemAssessment(item, "absent", best.conf, f"only {n_got} of {n_vis} visible {region_name} covered", best.box)
                else:
                    pa.items[item] = ItemAssessment(item, "absent", r.visibility, f"no {item} on visible {region_name}")
            else:
                d = matches_s.get(p.idx)
                if d is not None:
                    pa.items[item] = ItemAssessment(item, "worn", d.conf, f"{item} on {region_name}", d.box)
                else:
                    pa.items[item] = ItemAssessment(item, "absent", r.visibility, f"no {item} on visible {region_name}")

        # A helmet that matched no head but sits at someone's hand is being carried.
        if item == "helmet" and item in supported:
            claimed = {id(d) for d in matches_s.values()}
            for d in dets:
                if id(d) in claimed:
                    continue
                for pa, reg in zip(results, regions):
                    ia = pa.items[item]
                    if ia.state == "absent" and reg["hands"].visible and any(
                            overlap(d.box, hb) >= min_ioa and d.box.w <= 3 * hb.w for hb in reg["hands"].boxes):
                        pa.items[item] = ItemAssessment(item, "absent", d.conf, "helmet is carried in hand, not worn", d.box)
                        break
    return results
