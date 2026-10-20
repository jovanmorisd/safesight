"""Draw per-person verdicts and PPE boxes onto an image (Pillow; RGB uint8 arrays in and out)."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .types import Box, Detection, PersonAssessment

# RGB
STATUS_COLOR = {"compliant": (13, 148, 136), "violation": (239, 68, 68), "unknown": (245, 158, 11)}
ITEM_COLOR = {
    "helmet": (45, 212, 191), "vest": (34, 197, 94), "gloves": (59, 130, 246), "boots": (168, 85, 247),
    "goggles": (236, 72, 153), "mask": (6, 182, 212), "earmuffs": (236, 72, 182),
}
SKELETON = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12),
            (11, 13), (13, 15), (12, 14), (14, 16), (0, 1), (0, 2), (1, 3), (2, 4)]


@lru_cache(maxsize=16)
def _font(size: int) -> ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _label(draw: ImageDraw.ImageDraw, text: str, x: float, y: float, color, size: int) -> None:
    font = _font(size)
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    w, h = r - l, b - t
    pad = max(2, size // 4)
    y = max(y, h + 2 * pad)
    draw.rectangle([x, y - h - 2 * pad, x + w + 2 * pad, y], fill=color)
    draw.text((x + pad - l, y - h - pad - t), text, fill=(255, 255, 255), font=font)


def annotate(image: np.ndarray, assessments: list[PersonAssessment], detections: list[Detection],
             kp_thr: float = 0.4, draw_pose: bool = True) -> np.ndarray:
    img = Image.fromarray(image)
    draw = ImageDraw.Draw(img)
    h, w = image.shape[:2]
    base = max(11, min(28, int(max(h, w) / 55)))
    th = max(2, int(round(max(h, w) / 500)))

    for d in detections:
        if d.cls in ITEM_COLOR:
            b = d.box
            draw.rectangle([b.x1, b.y1, b.x2, b.y2], outline=ITEM_COLOR[d.cls], width=max(1, th - 1))
            _label(draw, f"{d.cls} {d.conf:.2f}", b.x1, b.y1, ITEM_COLOR[d.cls], int(base * 0.75))

    for pa in assessments:
        p = pa.person
        color = STATUS_COLOR[pa.overall]
        if draw_pose and p.keypoints is not None:
            k = p.keypoints
            for a, c in SKELETON:
                if k[a, 2] >= kp_thr and k[c, 2] >= kp_thr:
                    draw.line([(float(k[a, 0]), float(k[a, 1])), (float(k[c, 0]), float(k[c, 1]))],
                              fill=(230, 230, 230), width=max(1, th - 1))
        b = p.box
        draw.rectangle([b.x1, b.y1, b.x2, b.y2], outline=color, width=th + 1)
        if pa.overall == "violation":
            text = f"#{p.idx + 1} no " + ", ".join(pa.missing)
        elif pa.overall == "unknown":
            text = f"#{p.idx + 1} check " + ", ".join(pa.uncertain) if pa.uncertain else f"#{p.idx + 1} unknown"
        else:
            text = f"#{p.idx + 1} OK"
        _label(draw, text, b.x1, b.y1, color, base)
    return np.asarray(img)


def crop(image: np.ndarray, b: Box, pad: float = 0.08) -> np.ndarray:
    h, w = image.shape[:2]
    px, py = b.w * pad, b.h * pad
    x1, y1 = int(max(0, b.x1 - px)), int(max(0, b.y1 - py))
    x2, y2 = int(min(w, b.x2 + px)), int(min(h, b.y2 + py))
    return image[y1:y2, x1:x2].copy()
