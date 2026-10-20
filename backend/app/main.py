"""FastAPI entry point.

Local:   `uvicorn app.main:app` from the backend directory (also serves the built React app).
Vercel:  imported by api/index.py as a serverless function; the static site is served by Vercel.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from . import engine as eng
from .auth import current_user, is_admin, optional_user
from .db import BACKEND_DIR, DB_KIND, RETENTION_DAYS, User, engine, init_db
from .routes import admin, auth, incidents, inspections, reports, stats
from .services import purge_older_than
from .storage import storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ppe.main")
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
SERVERLESS = bool(os.environ.get("VERCEL"))
RETENTION_CHECK_HOURS = 6

_ready = False
_ready_lock = threading.Lock()


def ensure_ready() -> None:
    """One-time setup per server instance: tables, storage bucket, default models and site.
    Called lazily on the first request because serverless platforms may skip lifespan events."""
    global _ready
    if _ready:
        return
    with _ready_lock:
        if _ready:
            return
        log.info("database: %s · storage: %s · retention: %s", DB_KIND, storage.name,
                 f"{RETENTION_DAYS} days" if RETENTION_DAYS > 0 else "off")
        init_db()
        storage.ensure_bucket()
        with Session(engine) as s:
            eng.seed(s)
        _ready = True


async def retention_loop() -> None:
    while True:
        try:
            with Session(engine) as s:
                await asyncio.to_thread(purge_older_than, s, RETENTION_DAYS)
        except Exception:  # never let housekeeping kill the app
            log.exception("retention run failed")
        await asyncio.sleep(RETENTION_CHECK_HOURS * 3600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = None
    if not SERVERLESS:  # long-running server: set up and load models now, run retention in-process
        await asyncio.to_thread(ensure_ready)
        await asyncio.to_thread(eng.reload)
        if RETENTION_DAYS > 0:
            task = asyncio.create_task(retention_loop())
    yield
    if task:
        task.cancel()


app = FastAPI(title="SafeSight PPE Compliance API", version="1.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def setup_on_first_request(request: Request, call_next):
    if not _ready and request.url.path.startswith(("/api", "/media")) and request.url.path != "/api/health":
        await asyncio.to_thread(ensure_ready)
    return await call_next(request)


for r in (auth.router, inspections.router, incidents.router, stats.router, reports.router, admin.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "database": DB_KIND, "storage": storage.name}


@app.get("/api/cron/retention", include_in_schema=False)
def cron_retention(request: Request, user: User | None = Depends(optional_user)):
    """Daily auto-delete on serverless hosts (Vercel Cron calls this with the CRON_SECRET bearer token)."""
    secret = os.environ.get("CRON_SECRET", "")
    given = request.headers.get("authorization", "")
    if not ((secret and hmac.compare_digest(given, f"Bearer {secret}")) or (user and is_admin(user))):
        raise HTTPException(401)
    with Session(engine) as s:
        return {"deleted": purge_older_than(s, RETENTION_DAYS), "retention_days": RETENTION_DAYS}


@app.get("/media/{key:path}", include_in_schema=False)
def media(key: str, user: User = Depends(current_user)):
    """Images, only for their owner (or an admin): served from disk locally, or redirected to a
    short-lived signed Supabase URL. Keys look like users/<id>/annotated/<file>.jpg."""
    kinds = ("originals", "annotated", "crops")
    parts = key.split("/")
    if len(parts) == 4 and parts[0] == "users" and parts[2] in kinds:
        allowed = parts[1] == str(user.id) or is_admin(user)
    elif len(parts) == 2 and parts[0] in kinds:  # files from before accounts existed (owned by the admin)
        allowed = is_admin(user)
    else:
        allowed = False
    if not allowed:
        raise HTTPException(404)
    if storage.remote:
        url = storage.signed_url(key)
        if not url:
            raise HTTPException(404)
        return RedirectResponse(url, status_code=307, headers={"Cache-Control": "private, max-age=1800"})
    try:
        path = storage.path(key)
    except ValueError:
        raise HTTPException(404)
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})


# Serve the built React app when present (local single-process mode; Vercel serves it itself).
if FRONTEND_DIST.is_dir() and not SERVERLESS:
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = FRONTEND_DIST / path
        if path and target.is_file() and FRONTEND_DIST in target.resolve().parents:
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
