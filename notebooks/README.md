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

## Notebooks

| Notebook | What it is | Result |
|---|---|---|
| `results/checksafetycv.ipynb` | v1 ("notebook C"): YOLO11s fine-tuned on Construction Site Safety (person, helmet, vest, mask), 60 epochs, run on Kaggle on 21 Oct 2026 | **Worse than the current app.** CSS test: mAP50 0.881 / mAP50-95 0.638 vs. 0.897 / 0.684. Construction-PPE (never seen): 0.610 / 0.236 vs. 0.733 / 0.312. Don't attach it. |
| `results/safesight-v2-train.ipynb` | v2 with **YOLO11s**: Construction-PPE + SH17 + Hard Hat Workers (+ CSS for training only), 8 classes, teacher pseudo-labels for the classes a dataset doesn't annotate, frozen test sets, per-worker accuracy with the app's own pipeline | **Better than the current app.** Construction-PPE test: mAP50 0.907 / mAP50-95 0.731 vs. 0.793 / 0.536. SH17 test: 0.671 / 0.448 vs. 0.577 / 0.362. Helmet+vest verdict accuracy per worker: 0.903 vs. 0.775. Register `safesight_v2_yolo11s.onnx` with confidence 0.30 and **Activate** (replace). Its Hard Hat Workers score isn't comparable because only v2 trained on that dataset. Kaggle `jeswintobias/safesight-v2-train`, 9 Nov 2026 |
| *(pending)* | The same v2 notebook with `MODEL = "yolo26s.pt"` (**YOLO26s**) | Running on Kaggle; the executed notebook goes in `results/` when it finishes |

All notebooks in `results/` are the executed Kaggle versions, outputs included.

**Attaching v2:** upload `safesight_v2_yolo11s.onnx` through **Models → Register**. Like any registered model, it's stored
in Supabase, so it doesn't need to go in `backend/models/`. Set the confidence to 0.30, then **Activate**. Replacing the current
detectors also makes the app lighter. Measured on a laptop CPU:

| Active detectors | Peak RAM | Time per photo |
|---|---|---|
| v2 + pose | ~470 MB | ~74 ms |
| Current two detectors + pose | ~535 MB | ~107 ms |
| v2 added to the ensemble | ~785 MB | ~154 ms |

Why v1 fell short: CSS is a Roboflow export of mosaics (four photos per image, black cut-outs), so the model
learned collages, and the same photos ended up in both train and test. Its only test on unseen photos
(Construction-PPE) shows the gap. Its per-worker check never ran.

### What each variant changes

| | v1 (friend) | v2 · YOLO11s | v2 · YOLO26s |
|---|---|---|---|
| Training data | CSS only (2,801 mosaics) | Construction-PPE + SH17 + Hard Hat Workers + CSS (16,900 images, near-duplicates removed) | same as v2 · YOLO11s |
| Classes | 4 (person, helmet, vest, mask) | 8 (+ gloves, boots, goggles, earmuffs) | 8 |
| Architecture | YOLO11s | YOLO11s | **YOLO26s**: no DFL in the box head, small-object label assignment (STAL) |
| Missing labels | not handled | teacher pseudo-labels (conf ≥ 0.5) | same, with a YOLO26s teacher |
| Training | 60 epochs, one T4 | teacher ≤ 1.5 h + final model ≤ 5 h, both T4s, early stopping after 20 / 30 epochs without progress | same |
| Test set | its own CSS split (shares photos with training) + Construction-PPE | frozen: Construction-PPE val, SH17 val, 15% of Hard Hat Workers | same frozen sets |
| App-level check | skipped | per-worker accuracy with `ppe_core`; confidence threshold chosen on val | same + a check that the app's ONNX runner reproduces the model |
| Output | `safesight_css_yolo11s.onnx` | `safesight_v2_yolo11s.onnx` | `safesight_v2_yolo26s.onnx` |

What the comparisons answer:
- **v1 → v2 · YOLO11s:** what better data and training bring, with the same architecture.
- **v2 · YOLO11s → v2 · YOLO26s:** what the newer architecture brings, with the same data, rules and test sets.

## Running v2 on Kaggle

1. **The `safesight-app` input** already exists as the Kaggle dataset `jeswintobias/safesight-app`. It holds
   `backend/ppe_core/*.py` and `backend/models/*.onnx`. When either changes, make a new dataset version from
   those two folders (e.g. `kaggle datasets version -p <folder> -m "..." --dir-mode zip`).
2. New notebook → *File → Import Notebook* → `results/safesight-v2-train.ipynb`. For the YOLO26s variant, set
   `MODEL = "yolo26s.pt"` in the configuration cell. The YOLO11s run is the private Kaggle notebook `jeswintobias/safesight-v2-train`.
3. Settings: Accelerator *GPU T4 x2* (`machine_shape: NvidiaTeslaT4`), Internet *On*.
4. *Add Input*: `jeswintobias/construction-ppe-2026-11` (frozen copy of Construction-PPE, so the test set never
   changes), `mugheesahmad/sh17-dataset-for-ppe-detection`, `andrewmvd/hard-hat-detection`,
   `snehilsanyal/construction-site-safety-image-dataset-roboflow`, `jeswintobias/safesight-app`, and the output of
   `jeswintobias/checksafetycv` (adds v1 to the comparison).
5. **Dry run:** set `SMOKE = True` in the configuration cell and *Run All* (~10 min, CPU is fine). It stops early
   if an input is missing.
6. **Real run:** set `SMOKE = False`, then *Save Version → Save & Run All (Commit)*. It trains on both T4s, stops
   each stage early when validation mAP50-95 stops improving (20 / 30 epochs of patience), and caps the stages at
   `TEACHER_HOURS = 1.5` and `STUDENT_HOURS = 5`. The whole run takes about 7 h and always ends before Kaggle's 12 h limit.
7. From the Output tab, download `safesight_v2_<model>.onnx` and `results/`. `results/summary.json` says whether to
   **Activate** it, **Add to ensemble**, or keep the current models, and gives the confidence threshold to register
   it with (chosen on the validation images); `results/model_notes.txt` is the text for the model's *Notes*.

Test sets (frozen, so later runs stay comparable): Construction-PPE's official val split (the headline; the
current zip has no test split), SH17's `val_files.txt`, and a fixed 15% of Hard Hat Workers. The exact file
list is saved as `results/frozen_splits.csv`.

Construction-PPE (Ultralytics, CC BY 4.0) changed in November 2026: it now has 1,000 images (800 train, 200 val),
no test split, and 12 classes: helmet, gloves, vest, boots, goggles, Person, no_helmet, no_goggle, no_gloves,
no_boots, forklift, no_vest. The `samples/` images come from the earlier version's test split.
