# PPE Compliance Monitor: Build the App on Pretrained Weights

## Context
The folder is empty. This phase is **only the application**, running on pretrained weights, so you can check that the whole pipeline works end to end. Later the team will train a model in a separate notebook on their own chosen dataset and **drop the new weights in**, with no code changes. The model must therefore be a pluggable component behind a config file.

## Pretrained weights (for now)
- **PPE detector: SH17 `yolo8s.pt`** (21.5 MB, CPU-friendly). Download from https://github.com/ahmadmughees/SH17dataset/releases/download/v1/yolo8s.pt to `models/`.
  - It detects multiple PPE types (helmet, safety-vest, gloves, shoes, glasses, face-mask, face-guard, earmuffs, safety-suit), not just helmets.
  - It also detects body parts (person, head, face, ear, hands, foot).
  - Use `yolo8n.pt` instead if speed matters.
  - It's a temporary placeholder (non-commercial license; trained on stock photos).
- **Pose: `yolo11n-pose.pt`** (auto-downloads through Ultralytics). Gives person boxes and keypoints for matching PPE to each person.

## Model plug-in contract (how the notebook-trained model attaches later)
`config.yaml`:
```yaml
detector:
  weights: models/yolo8s.pt        # swap to models/our_finetuned.pt later
  conf: 0.35
  class_map:                       # model class name -> canonical name used by the app
    helmet: helmet
    safety-vest: vest
    gloves: gloves
    shoes: boots
    glasses: goggles
    face-mask-medical: mask
    person: person
    head: head
    hands: hands
    foot: foot
pose:
  weights: yolo11n-pose.pt
policy:                            # required PPE per site
  default: [helmet, vest]
```
- The notebook's only obligation is to export an Ultralytics `.pt` file. If its class names differ, edit `class_map`. Classes the model lacks are reported as `not_checked`, so the app never crashes.
- Every inspection stores the model name and weights hash (`model_versions` table). Results from the pretrained model and the trained model stay distinguishable on the dashboard.
- Add an `/admin/models` page to register or activate weights without restarting.

## Compliance logic (app side, works with any detector)
Three selectable levels:
- **L1:** PPE present anywhere in the image.
- **L2:** PPE matched to person-box regions (head, torso, hands, feet) with Hungarian matching.
- **L3:** PPE matched to pose keypoints, or to SH17 body-part boxes when the model provides them.

Each person gets a state per PPE item: `worn | absent | unknown`. The site policy defines which items are required. A violation is raised only for a required item that is `absent`; `unknown` items go to the review queue.

## Stack
FastAPI · SQLite (SQLModel) · Jinja2 + HTMX · Chart.js · Ultralytics · `supervision` (annotation) · pandas (CSV) · ReportLab (PDF) · pytest · Dockerfile.

## Build order
1. `ppe_core/`: `detector.py` (loads weights and `class_map` from config), `pose.py`, `associate.py` (L1/L2/L3), `policy.py`, `annotate.py`. Add a CLI `python -m ppe_core predict img.jpg` for a quick check.
2. `app/`:
   - `POST /inspections`: upload an image, store the original and annotated images, detections, per-person states and incidents.
   - `GET/PATCH /incidents`: review an incident as confirmed or false positive.
   - `/stats`, `/reports.csv`, `/reports.pdf`, `/admin/models`.
3. UI pages: Upload, Result (overlay plus per-person cards with a reason), Review queue, Dashboard (violations by PPE type and over time, confirmed vs. false positive, active model), Reports.
4. `tests/test_associate.py` with synthetic boxes:
   - helmet in hand → carried
   - 2 people and 1 helmet → 1 violation
   - head not visible → unknown
   - a required class the model lacks → `not_checked`, never a violation
5. `notebooks/` placeholder plus a README section titled "Attaching a trained model" (export a `.pt` file, update `class_map`, activate it in `/admin/models`).

## If the training dataset lacks some classes (or no good dataset is found)
**App side (built now, so nothing breaks later):**
- **Capability-driven.** At startup the app reads `model.names` and maps it through `class_map` to get the set of PPE items the active model supports.
  - A required item that the model can't detect gets the state `not_checked`, shown in the UI as "not checked by this model".
  - It never becomes a violation. The policy enforces only the supported ∩ required items.
- **Body parts do NOT come from the dataset.** Head, hands, feet and torso come from the **pose model** (COCO keypoints, always available). The PPE dataset only needs the PPE classes, not person/head/hands labels, and it doesn't need `no_helmet`-style classes either, because absence is inferred per person.
- **Multiple detectors.** `config.yaml` accepts a list of detectors. Their detections are merged (class-wise NMS) before association. One model can cover helmet and vest while another covers gloves and boots.

**Training side (notebook), in fallback order:**
1. Train on a dataset that has all the needed classes. SH17 itself has every class (8k images), and Construction-PPE has helmet, vest, gloves, boots and goggles.
2. Merging datasets that label different classes creates a missing-label problem: unlabeled gloves get treated as background. Two fixes:
   - (a) **Pseudo-label** the missing classes with the SH17 model or a zero-shot detector (Grounding DINO/OWLv2), keeping only high-confidence boxes. This is automatic, with no manual annotation.
   - (b) Train **separate specialist models** per dataset and use the multi-detector config.
3. If no construction dataset is good enough, fine-tune the SH17 weights on whatever small construction set exists, or keep SH17 as the final model. The CV contribution then shifts to the compliance logic plus the evaluation (L1/L2/L3, cross-domain tests, failure analysis), which stays valid with any model.

## Roadmap after the app works
1. **Phase 1 (this plan):** the app running on pretrained SH17 weights. We only use these weights; we don't train anything in this phase.
2. **Phase 2, training notebook** (`notebooks/train.ipynb`, Colab/Kaggle GPU):
   - Pick a construction-site, multi-PPE dataset (e.g., Ultralytics Construction-PPE + Roboflow Construction Site Safety).
   - Unify the class names, remove duplicate images, freeze train/val/test splits.
   - Fine-tune YOLO11s/YOLO26s, starting from COCO or SH17 weights.
   - Export `best.pt`.
3. **Phase 3, evaluation notebook** (`notebooks/eval.ipynb`): compare the pretrained and fine-tuned models on the same frozen test set.
   - mAP@0.5 and mAP@0.5:0.95, per-class AP, confusion matrix.
   - Person-level compliance F1 for L1/L2/L3.
   - Cross-dataset test and a failure gallery.
   - Write up the limitations.
4. **Phase 4, attach:**
   - Copy `best.pt` to `models/`, update `class_map`, activate it in `/admin/models`.
   - The dashboard shows results per model version.
   - Incidents that reviewers mark as false positives are exported as hard examples for the next training round.
5. **Phase 5:** Docker deployment, report, demo video.

## Verification
- `pytest` passes.
- `uvicorn app.main:app`: upload 3–5 construction images. Check the annotated output, the per-person PPE states and that incidents appear. Confirm one incident and check that the dashboard updates and the CSV and PDF download.
- Swap test: point `weights` at a different `.pt` file (e.g., `yolo8n.pt`) and check that the app runs and the new model version is recorded.
