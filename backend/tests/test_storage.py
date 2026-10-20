"""Supabase Storage client against a mocked Storage REST API (no network)."""
from __future__ import annotations

import json

import httpx

from app.storage import LocalStorage, SupabaseStorage


def test_key_headers():
    legacy = SupabaseStorage("https://p.supabase.co", "eyJhbGciOi.legacy.jwt", "b")
    assert legacy.headers == {"apikey": "eyJhbGciOi.legacy.jwt", "Authorization": "Bearer eyJhbGciOi.legacy.jwt"}
    new = SupabaseStorage("https://p.supabase.co", "sb_secret_abc", "b")
    assert new.headers == {"apikey": "sb_secret_abc"}


def make_store(handler):
    s = SupabaseStorage("https://proj.supabase.co", "eyJservice-key", "ppe-media")
    s.client = httpx.Client(transport=httpx.MockTransport(handler), headers=s.headers)
    return s


def test_supabase_upload_read_sign_delete():
    seen, files = [], {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.path))
        assert req.headers["authorization"] == "Bearer eyJservice-key"
        path = req.url.path
        if req.method == "POST" and path.startswith("/storage/v1/object/sign/"):
            return httpx.Response(200, json={"signedURL": "/object/sign/ppe-media/crops/a.jpg?token=t"})
        if req.method == "POST" and path.startswith("/storage/v1/object/ppe-media/"):
            assert req.headers["x-upsert"] == "true"
            files[path.split("/ppe-media/", 1)[1]] = req.content
            return httpx.Response(200, json={"Key": "x"})
        if req.method == "GET" and path.startswith("/storage/v1/object/ppe-media/"):
            key = path.split("/ppe-media/", 1)[1]
            return httpx.Response(200, content=files[key]) if key in files else httpx.Response(404)
        if req.method == "DELETE" and path == "/storage/v1/object/ppe-media":
            for k in json.loads(req.content)["prefixes"]:
                files.pop(k, None)
            return httpx.Response(200, json=[])
        return httpx.Response(500)

    s = make_store(handler)
    s.save("crops/a.jpg", b"jpegbytes")
    assert s.read("crops/a.jpg") == b"jpegbytes"
    url = s.signed_url("crops/a.jpg")
    assert url == "https://proj.supabase.co/storage/v1/object/sign/ppe-media/crops/a.jpg?token=t"
    n = len(seen)
    assert s.signed_url("crops/a.jpg") == url and len(seen) == n  # cached, no new request
    s.delete(["crops/a.jpg"])
    assert s.read("crops/a.jpg") is None


def test_supabase_creates_missing_bucket():
    calls = []

    def handler(req):
        calls.append((req.method, req.url.path))
        if req.method == "GET":
            return httpx.Response(400, json={"error": "Bucket not found"})
        body = json.loads(req.content)
        assert body == {"id": "ppe-media", "name": "ppe-media", "public": False}
        return httpx.Response(200, json={"name": "ppe-media"})

    make_store(handler).ensure_bucket()
    assert calls == [("GET", "/storage/v1/bucket/ppe-media"), ("POST", "/storage/v1/bucket")]


def test_local_storage_blocks_path_traversal(tmp_path):
    s = LocalStorage(tmp_path)
    s.save("crops/x.jpg", b"1")
    assert s.read("crops/x.jpg") == b"1"
    try:
        s.read("../outside.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal not blocked")


def test_project_url_with_api_path_is_normalised():
    s = SupabaseStorage("https://abc.supabase.co/rest/v1/", "sb_secret_x", "b")
    assert s.base == "https://abc.supabase.co/storage/v1"
