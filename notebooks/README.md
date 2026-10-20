# Training notebooks (phase 2)

The app currently runs two **pretrained** detectors as an ensemble (a construction-site YOLOv8n for
helmet/vest/mask + SH17 YOLOv8s for gloves/shoes/glasses/ear-muffs and body parts). The plan is to
train our own detector here (Colab / Kaggle GPU) and attach it to the app without changing any code.
The pretrained models' weak spots (see the main README) are the baseline to beat.

## What a notebook must produce

1. An **ONNX** file: after training run `model.export(format="onnx")` → `best.onnx` (keep it ≤ 50 MB: YOLO n/s, or `half=True`).
2. Class names that say what they are. The app maps names automatically
   (`helmet`/`hardhat` → helmet, `safety-vest`/`vest` → vest, `shoes`/`boots` → boots,
   `glasses`/`goggles` → goggles, `gloves`, `mask`, `earmuffs`, `person`, `head`, `hands`, `foot`).
   Negative classes such as `NO-Hardhat` / `no_helmet` are ignored on purpose: absence is decided
   per worker by the association logic, not detected.
   If your names are unusual, pass an explicit class map when registering, e.g.
   `{"Hardhat": "helmet", "Safety Vest": "vest", "Person": "person"}`.
3. A short note (dataset, epochs, image size, test mAP) to paste into the model's *Notes*.

The model does **not** need person/head/hand labels: body regions come from the separate pose model.

## Attaching the trained model

1. Open the app → **Models** → *Register a trained model* → upload `best.onnx`, give it a name.
2. Check the *Detects* chips (which PPE items it supports).
3. Click **Activate** (replace) or **Add to ensemble** (run together with the current model).
4. New inspections record the model name, so the dashboard and reports can compare versions.

## Suggested notebooks

- `train.ipynb` – unify class names across datasets, remove duplicate images, freeze splits,
  fine-tune YOLO11s / YOLO26s, export `best.pt`.
- `eval.ipynb` – compare pretrained vs. fine-tuned on the same frozen test split: mAP@0.5,
  mAP@0.5:0.95 and per-class AP, plus person-level compliance accuracy.

Local data already downloaded for experiments: `datasets/construction-ppe/` (Ultralytics
Construction-PPE, AGPL-3.0; classes helmet, gloves, vest, boots, goggles, none, Person, no_helmet,
no_goggle, no_gloves, no_boots).
