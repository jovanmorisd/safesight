"""Command line: `python -m ppe_core info` or `python -m ppe_core predict img.jpg [...]`."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .config import load_config
from .pipeline import Pipeline

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def main() -> None:
    ap = argparse.ArgumentParser(prog="ppe_core")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info", help="show model classes, class map and supported PPE")
    pr = sub.add_parser("predict", help="run the pipeline on images")
    pr.add_argument("images", nargs="+")
    pr.add_argument("--required", nargs="*", default=None)
    pr.add_argument("--out", default="outputs")
    args = ap.parse_args()

    pipe = Pipeline(load_config(args.config))
    if args.cmd == "info":
        print(json.dumps(pipe.describe(), indent=2))
        return

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for path in args.images:
        try:
            img = np.asarray(ImageOps.exif_transpose(Image.open(path)).convert("RGB"))
        except Exception:
            print(f"skip {path}: not an image")
            continue
        res = pipe.run(img, args.required)
        Image.fromarray(res.annotated).save(out / f"{Path(path).stem}_annotated.jpg", quality=90)
        summary = [{"person": pa.person.idx + 1, "overall": pa.overall, "missing": pa.missing,
                    "items": {k: v.state for k, v in pa.items.items()}} for pa in res.assessments]
        print(json.dumps({"image": path, "ms": round(res.timings_ms["total"]), "persons": summary}, indent=1))


if __name__ == "__main__":
    main()
