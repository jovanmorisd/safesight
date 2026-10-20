"""Convert Ultralytics .pt weights to ONNX for the app (run once, on a machine with ultralytics).

    python scripts/export_onnx.py models/yolo8s.pt models/construction-safety-yolov8n.pt yolo11n-pose.pt

The app itself only needs onnxruntime. The exported file keeps the class names in its metadata.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def export(weights: str, out_dir: Path, imgsz: int = 640) -> Path:
    from ultralytics import YOLO

    model = YOLO(weights)
    path = Path(model.export(format="onnx", imgsz=imgsz, opset=17, simplify=True, dynamic=False))
    dest = out_dir / path.name
    if path.resolve() != dest.resolve():
        shutil.move(str(path), dest)
    print(f"{weights} -> {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "models"
    for w in sys.argv[1:] or ["models/yolo8s.pt", "models/construction-safety-yolov8n.pt", "yolo11n-pose.pt"]:
        export(w, out)
