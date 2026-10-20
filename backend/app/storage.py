"""Where images and uploaded model weights live.

* Local (default): files under `data/media/`.
* Supabase Storage: used when SUPABASE_URL and SUPABASE_SERVICE_KEY are set. The bucket is
  private; the browser gets short-lived signed URLs through `/media/<key>` redirects, and the
  service key never leaves the server.

Keys look like "originals/ab12.jpg", "annotated/ab12.jpg", "crops/ab12_0.jpg",
"models/uploads/my-model.pt".
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote, urlsplit

import httpx

from .db import MEDIA_DIR

log = logging.getLogger("ppe.storage")


class LocalStorage:
    remote = False
    name = "local"

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError(f"invalid storage key: {key!r}")
        return p

    def save(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def read(self, key: str) -> Optional[bytes]:
        p = self.path(key)
        return p.read_bytes() if p.is_file() else None

    def delete(self, keys: Iterable[str]) -> None:
        for k in keys:
            if k:
                self.path(k).unlink(missing_ok=True)

    def ensure_bucket(self) -> None:
        pass


class SupabaseStorage:
    remote = True
    name = "supabase"

    def __init__(self, url: str, service_key: str, bucket: str):
        # Accept the project URL with or without a copied API path (e.g. ".../rest/v1/").
        parts = urlsplit(url.strip())
        self.base = f"{parts.scheme}://{parts.netloc}/storage/v1"
        self.bucket = bucket
        # New-style secret keys (sb_secret_...) go only in `apikey`; legacy service_role keys are JWTs
        # ("eyJ...") and are also sent as a Bearer token.
        self.headers = {"apikey": service_key}
        if service_key.startswith("eyJ"):
            self.headers["Authorization"] = f"Bearer {service_key}"
        self.client = httpx.Client(timeout=60, headers=self.headers)
        self._signed: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def _obj(self, key: str) -> str:
        return f"{self.base}/object/{self.bucket}/{quote(key)}"

    def ensure_bucket(self) -> None:
        r = self.client.get(f"{self.base}/bucket/{self.bucket}")
        if r.status_code == 200:
            return
        r = self.client.post(f"{self.base}/bucket", json={"id": self.bucket, "name": self.bucket, "public": False})
        if r.status_code not in (200, 201) and "already exists" not in r.text.lower():
            raise RuntimeError(f"Supabase: could not create bucket {self.bucket!r}: {r.status_code} {r.text}")
        log.info("created Supabase storage bucket %s", self.bucket)

    def save(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        r = self.client.post(self._obj(key), content=data,
                             headers={"Content-Type": content_type, "x-upsert": "true"})
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Supabase upload failed for {key}: {r.status_code} {r.text}")
        return key

    def read(self, key: str) -> Optional[bytes]:
        r = self.client.get(self._obj(key))
        return r.content if r.status_code == 200 else None

    def delete(self, keys: Iterable[str]) -> None:
        keys = [k for k in keys if k]
        for i in range(0, len(keys), 500):
            r = self.client.request("DELETE", f"{self.base}/object/{self.bucket}", json={"prefixes": keys[i:i + 500]})
            if r.status_code not in (200, 204):
                log.warning("Supabase delete failed: %s %s", r.status_code, r.text)
        with self._lock:
            for k in keys:
                self._signed.pop(k, None)

    def upload_url(self, key: str) -> str:
        """One-time URL the browser can PUT a file to directly (bypasses the app server's request
        size limit, e.g. Vercel's 4.5 MB)."""
        r = self.client.post(f"{self.base}/object/upload/sign/{self.bucket}/{quote(key)}", headers={"x-upsert": "true"})
        if r.status_code != 200:
            raise RuntimeError(f"Supabase: could not create upload URL: {r.status_code} {r.text}")
        return self.base + r.json()["url"]

    def signed_url(self, key: str, expires: int = 3600) -> Optional[str]:
        now = time.time()
        with self._lock:
            hit = self._signed.get(key)
            if hit and hit[1] > now:
                return hit[0]
        r = self.client.post(f"{self.base}/object/sign/{self.bucket}/{quote(key)}", json={"expiresIn": expires})
        if r.status_code != 200:
            return None
        url = self.base + r.json()["signedURL"]
        with self._lock:
            self._signed[key] = (url, now + expires * 0.8)
        return url


def _make() -> LocalStorage | SupabaseStorage:
    url, key = os.environ.get("SUPABASE_URL", "").strip(), os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if url and key:
        return SupabaseStorage(url, key, os.environ.get("SUPABASE_BUCKET", "ppe-media").strip() or "ppe-media")
    return LocalStorage(MEDIA_DIR)


storage = _make()
