# SafeSight: PPE Compliance Monitoring

A computer-vision system that checks **each worker** in a construction-site photo for the PPE their site requires (helmet, hi-vis vest, gloves, boots, goggles, mask, ear protection). It records incidents, lets a safety officer review them, and produces dashboards and PDF/CSV reports.

> **Phase 1 (this code):** the full application, running on two **pretrained** detectors used together (see [Current models](#current-models-and-their-limitations)).
> **Phase 2:** train our own detector in a notebook and attach it from the *Models* page (see [notebooks/README.md](notebooks/README.md)).

## What makes it more than "run YOLO on an image"

| | Detecting PPE | Deciding that a worker *wears* it |
|---|---|---|
| Question | Is there a helmet in the image? | Is worker #2 wearing a helmet? |
| Failure cases | A helmet in someone's hand, 3 helmets but 4 workers, a worker seen from the back | Handled by association + an *unknown* state |

Every worker gets a state for every PPE item: **worn**, **absent**, **unknown** (the body part is not visible or the person is too small) or **not checked** (the active model cannot detect that item). A *violation* is raised only when a **required** item is **absent**. *Unknown* goes to a review queue and never counts as a violation.

How a PPE box is matched to a worker:

- **Body regions** (head, face, torso, hands, feet) come from 17 COCO keypoints (YOLO11-pose), plus head/hands/foot boxes when the detector provides them. Workers without keypoints fall back to fixed bands of their person box.
- A PPE box counts as **worn** only when it sits on the matching region of *that* worker. One helmet per head, matched with the Hungarian algorithm.
- Regions that aren't visible give *unknown*.
- A helmet next to a wrist is reported as *carried, not worn*.
- Gloves and boots must cover every visible hand or foot.
  - Gloves and boots must cover every visible hand or foot.

## Architecture

```
React + Vite + Tailwind  ──/api──►  FastAPI  ──►  ppe_core (pure Python, no web code)
 (dashboard, review,                  │            ├─ Detector(s)   Ultralytics YOLO, class-name mapping
  reports, models, sites)             │            ├─ PoseModel     YOLO11n-pose, persons + keypoints
                                      │            ├─ associate     PPE → worker body regions
                                      │            ├─ policy        site-required PPE → verdict
                                      │            └─ annotate      OpenCV drawing
                                      ▼
              Database: Supabase Postgres (hosted) or SQLite file (local)
                        sites, model versions, inspections, detections, person assessments, incidents
              Images:   Supabase Storage, private bucket (hosted) or data/media/ (local)
                        originals, annotated, worker crops, uploaded model weights
```

- `backend/ppe_core/`: the CV logic. It is also usable from the CLI and notebooks, so the code we evaluate is the code we deploy.
- `backend/app/`: the API, database, model registry, reports (ReportLab PDF, pandas CSV).
- `frontend/`: the web UI (teal theme, light/dark).

Models are **pluggable**:
- Weights are registered in the database (Models page or `config.yaml`).
- Class names are mapped to canonical PPE names automatically, or with an explicit `class_map`.
- Several detectors can run as an ensemble.
- Each inspection stores the model that produced it.

## Run it (Windows, from the project root)

Requirements: Python 3.10+, Node 18+. A GPU is optional (CPU works, just slower).

```powershell
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126   # or /whl/cpu
.venv\Scripts\python -m pip install -r requirements.txt
curl -L -o models/yolo8s.pt https://github.com/ahmadmughees/SH17dataset/releases/download/v1/yolo8s.pt
curl -L -o models/construction-safety-yolov8n.pt https://github.com/snehilsanyal/Construction-Site-Safety-PPE-Detection/raw/main/models/best.pt
.venv\Scripts\python -m uvicorn app.main:app --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api to :8000)
```

**Single-process mode:** run `npm run build` in `frontend/`, then start only uvicorn and open http://localhost:8000. FastAPI serves the built UI.

**Docker:** `docker compose up --build`, then open http://localhost:8000. This builds CPU-only. It uses Supabase if `backend/.env` is set, otherwise data is kept in a Docker volume.

The pose model `yolo11n-pose.pt` downloads automatically on first start.

### Use it on your phone (same Wi-Fi)

1. Start the server with `--host 0.0.0.0`:
   ```
   .venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   Allow Python through the Windows firewall when asked.
2. Find the laptop's IP with `ipconfig` (Wi-Fi → IPv4 address, e.g. `192.168.1.23`).
3. On the phone, open `http://192.168.1.23:8000`.

The bottom bar's camera button opens **Take a photo**, which goes straight to the phone camera.

## Accounts and privacy

- **Sign up / log in** with email and password. Accounts are stored in the app database (Supabase Postgres when hosted), and passwords are hashed with scrypt. A login is a signed, http-only cookie that lasts 7 days.
- **Everything a user uploads belongs to them.** Inspections, incidents and images are stored under `users/<user id>/…`. Users only see their own dashboard, inspections, review queue and reports, and **cannot open other users' images, even with the link**.
- **The first account becomes admin.** The admin sees everyone's data (with the owner's name shown) and is the only one who can manage **Models** and **Sites & Policies**.
- Settings in `backend/.env`:
  - `SECRET_KEY` signs the login cookies. Set it when hosting.
  - `ALLOW_SIGNUP=false` blocks new sign-ups after the admin exists.

## Database, image storage and hosting

| | Local (default, no setup) | Hosted (Supabase) |
|---|---|---|
| Database | SQLite file `backend/data/ppe.db` | Supabase **Postgres** (`DATABASE_URL`) |
| Images and uploaded model weights | `backend/data/media/` | Supabase **Storage**, private bucket `ppe-media`. The browser only gets short-lived signed links. |
| Auto-delete | Inspections older than `RETENTION_DAYS` (default **30**) are deleted, rows and images, checked every 6 h | same |

Switching to Supabase needs no code change, only settings:

1. Create a project at supabase.com and note the **database password**.
2. Copy `backend/.env.example` to `backend/.env` and fill in:
   - `DATABASE_URL`: *Project Settings → Database → Connection string → Session pooler*, with your password inserted;
   - `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`: *Project Settings → API*, the **service_role** key.

   This key is secret and stays on the server. `.env` is git- and docker-ignored.
3. Start the app. Tables and the storage bucket are created automatically. **System** shows *Postgres (Supabase)* / *Supabase Storage* when it's connected.

**Hosting:** `docker compose up --build -d` on any server. The compose file reads `backend/.env`. With Supabase configured, the container keeps no data, so redeploys and restarts lose nothing.

Hosting checklist: set `SECRET_KEY`, create your admin account first, then set `ALLOW_SIGNUP=false` if only invited people should get accounts.

### Useful commands

```powershell
cd backend
.venv\Scripts\python -m pytest                                   # unit + API tests
.venv\Scripts\python -m ppe_core info                            # model classes, class map, supported PPE
.venv\Scripts\python -m ppe_core predict ..\samples\*.jpg --out outputs
```

## Using the app

0. **Home page** (`/`): what the app does. **Sign up / Log in** to use it.
1. **New Inspection:** drop photos (or **Take a photo** on a phone), choose the site, then run.
2. **Inspection page:** the annotated image and one card per worker with every required PPE item, its state and the reason.
3. **Review Queue:** confirm, mark as a false alarm, or mark resolved. Reviewer decisions produce the *review precision* metric on the dashboard.
4. **Dashboard:** compliance rate, open incidents, unknown rate, violations over time, per-item compliance, the latest inspection, and the active model.
5. **Reports:** a PDF summary (with worker crops) or a CSV incident log for any date range and site.
6. **Sites & Policies:** set the required PPE per site.
7. **Models:** upload trained weights, then activate one or combine several.

## Current models and their limitations

Both pretrained detectors run together as an **ensemble**. Their detections are merged with class-wise NMS before association.

| Model | Good at | Weak at | License |
|---|---|---|---|
| `construction-safety-yolov8n`: YOLOv8n trained on Roboflow *Construction Site Safety* ([source](https://github.com/snehilsanyal/Construction-Site-Safety-PPE-Detection)) | Helmets and hi-vis vests on construction sites; also masks and persons | Only helmet / vest / mask | **None stated.** Use for the academic demo only, and replace with our own model |
| `sh17-yolov8s`: [SH17](https://github.com/ahmadmughees/SH17dataset) release weights | Gloves, shoes, glasses, ear-muffs, and body parts (head/face/hands/foot) used for body regions | **Misses most construction hi-vis vests**; trained on factory stock photos | **CC BY-NC-SA 4.0** (non-commercial) |
| `yolo11n-pose` (Ultralytics) | 17 COCO keypoints for the body regions | Crowds, heavy occlusion | AGPL-3.0 |

What we saw on the 10 sample images:
- SH17 alone found 1 vest in total.
- With the construction model added, properly equipped workers come out *compliant*.
- Matching PPE to each worker matters: in `image796` there is a vest in the picture, yet 6 of the 8 workers are correctly flagged for not wearing one.

Known failure modes:
- **Low-resolution or blurry images:** neither detector nor pose finds anyone in `image182`.
- Small or occluded workers, which become *unknown*.
- Caps or hoods mistaken for helmets; yellow shirts mistaken for vests.
- SH17's `shoes` class covers any footwear, so "boots worn" does not mean *safety* boots.
- Gloves and boots are often hidden.

These are model problems, not app problems: training our own model (phase 2) is meant to fix them. The system is **decision support**: a person reviews every incident.

## Project layout

```
backend/
  ppe_core/      types, config (class mapping), models, associate (PPE → worker), policy, annotate, pipeline, CLI
  app/           main, db (SQLModel), auth (accounts, sessions), storage (local / Supabase), engine (model registry ↔ pipeline), services, routes/
  tests/         association unit tests, storage tests, end-to-end API tests (auth, per-user data)
  config.yaml    default detector / pose / thresholds / default policy
frontend/        React app (pages: Home, Login/Sign-up, Dashboard, Inspections, Inspection, Upload, Review, Reports, Models, Sites, System)
notebooks/       phase-2 training / evaluation (contract for attaching a model)
samples/         example images
```
