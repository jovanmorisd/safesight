"""End-to-end API tests with the real models (skipped if the weights are not downloaded)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import io

import numpy as np
from PIL import Image
import pytest

BACKEND = Path(__file__).resolve().parent.parent
os.environ["PPE_DATA_DIR"] = tempfile.mkdtemp(prefix="ppe_test_")

pytestmark = pytest.mark.skipif(not (BACKEND / "models" / "yolo8s.pt").exists(),
                                reason="default weights not downloaded")


@pytest.fixture(scope="module")
def app():
    os.chdir(BACKEND)
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="module")
def admin(app):
    """First account → admin. Runs the app lifespan (model loading) once."""
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        if c.get("/api/auth/config").json()["first_user"]:
            r = c.post("/api/auth/register", json={"name": "Admin", "email": "admin@test.io", "password": "adminpass1"})
        else:
            r = c.post("/api/auth/login", json={"email": "admin@test.io", "password": "adminpass1"})
        assert r.status_code == 200, r.text
        yield c


@pytest.fixture(scope="module")
def worker(app, admin):
    from fastapi.testclient import TestClient

    c = TestClient(app)
    r = c.post("/api/auth/register", json={"name": "Worker", "email": "worker@test.io", "password": "workerpass1"})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "user"
    return c


def _sample_image() -> bytes:
    samples = sorted((BACKEND.parent / "samples").glob("*.jpg"))
    if samples:
        return samples[0].read_bytes()
    buf = io.BytesIO()
    Image.fromarray(np.full((480, 640, 3), 200, np.uint8)).save(buf, format="JPEG")
    return buf.getvalue()


def _upload(client, name="site.jpg"):
    r = client.post("/api/inspections", files=[("files", (name, _sample_image(), "image/jpeg"))])
    assert r.status_code == 200, r.text
    return r.json()["inspections"][0]


def test_requires_login(app, admin):
    from fastapi.testclient import TestClient

    anon = TestClient(app)
    assert anon.get("/api/health").status_code == 200  # public
    for path in ("/api/inspections", "/api/stats", "/api/incidents", "/api/meta", "/api/reports/summary.pdf"):
        assert anon.get(path).status_code == 401, path
    assert anon.post("/api/auth/login", json={"email": "admin@test.io", "password": "nope"}).status_code == 401


def test_first_user_is_admin_and_meta(admin):
    me = admin.get("/api/auth/me").json()
    assert me["role"] == "admin"
    assert "helmet" in admin.get("/api/meta").json()["pipeline"]["supported"]


def test_upload_review_report_flow(admin):
    sites = admin.get("/api/sites").json()
    assert sites and sites[0]["required_ppe"]
    insp = _upload(admin)
    detail = admin.get(f"/api/inspections/{insp['id']}").json()
    assert detail["annotated_url"].startswith("/media/users/")
    assert len(detail["persons"]) == detail["num_persons"]
    assert admin.get(detail["annotated_url"]).status_code == 200
    for p in detail["persons"]:
        for item in detail["required"]:
            assert p["items"][item]["state"] in {"worn", "absent", "unknown", "not_checked"}

    incidents = admin.get("/api/incidents").json()
    if incidents["items"]:
        x = incidents["items"][0]
        upd = admin.patch(f"/api/incidents/{x['id']}", json={"status": "false_positive", "notes": "test"}).json()
        assert upd["status"] == "false_positive" and upd["reviewer"] == "Admin"

    assert admin.get("/api/stats?days=7").json()["kpis"]["inspections"] >= 1
    assert admin.get("/api/reports/summary.pdf").content[:4] == b"%PDF"
    assert admin.get("/api/reports/incidents.csv").text.startswith("incident_id")


def test_users_only_see_their_own_data(admin, worker):
    mine = _upload(worker, "worker.jpg")
    theirs = _upload(admin, "admin.jpg")

    ids = {i["id"] for i in worker.get("/api/inspections").json()["items"]}
    assert mine["id"] in ids and theirs["id"] not in ids
    assert worker.get(f"/api/inspections/{theirs['id']}").status_code == 404
    assert worker.get(theirs["annotated_url"]).status_code == 404       # cannot open other users' images
    assert worker.delete(f"/api/inspections/{theirs['id']}").status_code == 404
    assert worker.get(mine["annotated_url"]).status_code == 200
    assert all(x["inspection_id"] != theirs["id"] for x in worker.get("/api/incidents").json()["items"])
    assert worker.get("/api/stats").json()["kpis"]["inspections"] == 1

    # the admin sees everyone's work
    admin_ids = {i["id"] for i in admin.get("/api/inspections?limit=200").json()["items"]}
    assert {mine["id"], theirs["id"]} <= admin_ids
    assert admin.get(mine["annotated_url"]).status_code == 200


def test_admin_only_endpoints(worker):
    assert worker.get("/api/models").status_code == 403
    assert worker.post("/api/sites", json={"name": "X", "required_ppe": ["helmet"]}).status_code == 403
    assert worker.get("/api/sites").status_code == 200


def test_register_validation(app):
    from fastapi.testclient import TestClient

    c = TestClient(app)
    assert c.post("/api/auth/register", json={"name": "A", "email": "bad", "password": "longenough"}).status_code == 400
    assert c.post("/api/auth/register", json={"name": "A", "email": "a@b.co", "password": "short"}).status_code == 400
    assert c.post("/api/auth/register", json={"name": "W", "email": "worker@test.io", "password": "whatever12"}).status_code == 409


def test_logout(app, admin):
    from fastapi.testclient import TestClient

    c = TestClient(app)
    c.post("/api/auth/login", json={"email": "admin@test.io", "password": "adminpass1"})
    assert c.get("/api/auth/me").status_code == 200
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").status_code == 401


def test_retention_purges_old_inspections(admin):
    from datetime import timedelta

    from sqlmodel import Session

    from app.db import Inspection, engine, utcnow
    from app.services import purge_older_than
    from app.storage import storage

    iid = _upload(admin, "old.jpg")["id"]
    with Session(engine) as s:
        i = s.get(Inspection, iid)
        key = i.annotated_path
        i.created_at = utcnow() - timedelta(days=45)
        s.add(i)
        s.commit()
        assert storage.read(key) is not None
        assert purge_older_than(s, 30) >= 1
        assert s.get(Inspection, iid) is None
    assert storage.read(key) is None
    assert admin.get(f"/api/inspections/{iid}").status_code == 404


def test_rejects_non_images(admin):
    r = admin.post("/api/inspections", files=[("files", ("notes.txt", b"hello", "text/plain"))])
    assert r.status_code == 400


def test_forgot_and_reset_password(app, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from fastapi.testclient import TestClient

    import app.mailer as mailer

    sent = []
    monkeypatch.setattr(mailer, "deliver_reset_link", lambda email, name, link, minutes: sent.append((email, link)))

    old = TestClient(app)  # a session that should be logged out by the reset
    assert old.post("/api/auth/register", json={"name": "Rita", "email": "rita@test.io", "password": "firstpass1"}).status_code == 200
    assert old.get("/api/auth/me").status_code == 200

    c = TestClient(app)
    # same answer for unknown addresses, and nothing is sent
    assert c.post("/api/auth/forgot", json={"email": "nobody@test.io"}).json() == {"ok": True}
    assert sent == []
    assert c.post("/api/auth/forgot", json={"email": "RITA@test.io"}).json() == {"ok": True}
    assert len(sent) == 1 and sent[0][0] == "rita@test.io"
    c.post("/api/auth/forgot", json={"email": "rita@test.io"})  # cooldown: no second email
    assert len(sent) == 1

    token = parse_qs(urlparse(sent[0][1]).query)["token"][0]
    assert c.get(f"/api/auth/reset/check?token={token}").json() == {"valid": True}
    assert c.post("/api/auth/reset", json={"token": token, "password": "short"}).status_code == 400
    r = c.post("/api/auth/reset", json={"token": token, "password": "secondpass2"})
    assert r.status_code == 200 and r.json()["email"] == "rita@test.io"
    assert c.get("/api/auth/me").status_code == 200                      # logged in with the new password
    assert old.get("/api/auth/me").status_code == 401                    # old session revoked
    assert c.post("/api/auth/reset", json={"token": token, "password": "thirdpass3"}).status_code == 400  # one-time
    assert c.get(f"/api/auth/reset/check?token={token}").json() == {"valid": False}
    assert c.post("/api/auth/login", json={"email": "rita@test.io", "password": "firstpass1"}).status_code == 401
    assert c.post("/api/auth/login", json={"email": "rita@test.io", "password": "secondpass2"}).status_code == 200


def test_register_onnx_model_upload_flow(admin, worker):
    onnx = (BACKEND / "models" / "construction-safety-yolov8n.onnx").read_bytes()
    assert worker.post("/api/models/upload-url", json={"name": "my-model"}).status_code == 403
    up = admin.post("/api/models/upload-url", json={"name": "my-model"}).json()
    assert up["key"] == "models/uploads/my-model.onnx" and up["method"] == "PUT"
    assert admin.put(up["url"], content=onnx).status_code == 200            # browser -> storage
    m = admin.post("/api/models", json={"name": "my-model", "key": up["key"], "notes": "test"}).json()
    assert set(m["supported"]) == {"helmet", "vest", "mask"} and "Hardhat" in m["classes"]
    assert admin.post("/api/models/upload-url", json={"name": "my-model"}).status_code == 409

    before = [x for x in admin.get("/api/models").json() if x["is_active"]]
    assert admin.patch(f"/api/models/{m['id']}", json={"is_active": True, "exclusive": True}).status_code == 200
    assert _upload(admin, "swap.jpg")["model_label"] == "my-model"
    for x in before:                                                         # restore the default ensemble
        admin.patch(f"/api/models/{x['id']}", json={"is_active": True, "exclusive": False})
    admin.patch(f"/api/models/{m['id']}", json={"is_active": False, "exclusive": False})
    assert admin.delete(f"/api/models/{m['id']}").status_code == 200


def test_bad_model_file_is_rejected(admin):
    up = admin.post("/api/models/upload-url", json={"name": "broken"}).json()
    admin.put(up["url"], content=b"not an onnx file")
    r = admin.post("/api/models", json={"name": "broken", "key": up["key"]})
    assert r.status_code == 400 and "onnx" in r.json()["detail"].lower()
    assert admin.post("/api/models", json={"name": "never-uploaded", "key": "models/uploads/never-uploaded.onnx"}).status_code == 400


def test_cron_retention_endpoint(app, admin, monkeypatch):
    from fastapi.testclient import TestClient

    anon = TestClient(app)
    assert anon.get("/api/cron/retention").status_code == 401
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    assert anon.get("/api/cron/retention", headers={"Authorization": "Bearer wrong"}).status_code == 401
    r = anon.get("/api/cron/retention", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200 and "deleted" in r.json()
    assert admin.get("/api/cron/retention").status_code == 200
