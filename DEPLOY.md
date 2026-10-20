# Deploying SafeSight on Vercel (+ Supabase)

One Vercel project serves both the React site and the FastAPI backend (`api/index.py`).
Models run with ONNX Runtime (no PyTorch), so the function bundle is ~270 MB (< 500 MB limit).
Supabase holds the database and all images / uploaded models.

## 1. Push the code to GitHub
```powershell
cd C:\Users\jovan\Disk\College\Sem_7\CV\CV_Project
git init -b main
git add .
git commit -m "SafeSight"
git remote add origin https://github.com/<you>/safesight.git   # empty repo, private is fine
git push -u origin main
```
`.gitignore` keeps `.env`, `.pt` files, local data and datasets out; the 3 default `.onnx` models are included.

## 2. Import into Vercel
vercel.com → **Add New → Project** → pick the repo → keep **Root Directory = `./`** (repo root;
`vercel.json` sets the build) → open **Environment Variables** and add:

| Name | Value |
|---|---|
| `DATABASE_URL` | from `backend/.env` |
| `SUPABASE_URL` | from `backend/.env` |
| `SUPABASE_SERVICE_KEY` | from `backend/.env` |
| `SECRET_KEY` | long random text |
| `CRON_SECRET` | another long random text (protects the daily auto-delete job) |
| `APP_URL` | your Vercel URL, e.g. `https://safesight.vercel.app` (add after the first deploy, then redeploy) |
| `ALLOW_SIGNUP` | `true` |
| `SMTP_*` | optional, for password-reset emails |

→ **Deploy**. Check `https://<your-app>.vercel.app/api/health` → `"database":"postgresql","storage":"supabase"`.

## 3. Use it
Open the Vercel URL → sign up (first account = admin). Every `git push` redeploys automatically.

## Notes
- Functions run in Tokyo (`hnd1`, next to your Supabase project). First request after idle: ~3–5 s
  (models load); then ~1–2 s per photo.
- New models: export to ONNX in the notebook → **Models → Register** (uploaded straight to Supabase).
- Auto-delete (30 days) runs daily via Vercel Cron.
