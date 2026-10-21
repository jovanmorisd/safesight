"""Accounts and sessions.

Users live in the app database (Supabase Postgres when hosted). Passwords are hashed with scrypt.
A session is an HMAC-signed, http-only cookie, so the browser also sends it for <img> requests
and images can be restricted to their owner.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from .db import AppSetting, Incident, Inspection, User, engine, get_session

COOKIE = "ss_session"
SESSION_DAYS = 7
_secret_cache: Optional[bytes] = None


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ----------------------------------------------------------------------------- passwords

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        test = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(test, _unb64(dk))
    except Exception:
        return False


# ----------------------------------------------------------------------------- session tokens

def _secret() -> bytes:
    """SECRET_KEY from the environment, otherwise one generated once and kept in the database
    (so sessions survive restarts and are shared by every server using the same database)."""
    global _secret_cache
    if _secret_cache is None:
        env = os.environ.get("SECRET_KEY", "").strip()
        if env:
            _secret_cache = env.encode()
        else:
            # Several server instances may start at once (serverless): only one insert can win, and
            # everyone then uses the stored value, so all instances sign sessions with the same key.
            with Session(engine) as s:
                row = s.get(AppSetting, "session_secret")
                if row is None:
                    try:
                        s.add(AppSetting(key="session_secret", value=secrets.token_urlsafe(48)))
                        s.commit()
                    except Exception:
                        s.rollback()
                    s.expire_all()
                    row = s.get(AppSetting, "session_secret")
                _secret_cache = row.value.encode()
    return _secret_cache


def _sign(uid: str, exp: str, password_hash: str) -> bytes:
    # The password hash is part of the signature, so changing the password logs out every session.
    return hmac.new(_secret(), f"{uid}.{exp}.{password_hash}".encode(), hashlib.sha256).digest()


def make_token(user: User) -> str:
    uid, exp = str(user.id), str(int(time.time()) + SESSION_DAYS * 86400)
    return f"{uid}.{exp}.{_b64(_sign(uid, exp, user.password_hash))}"


def read_token(token: str, session: Session) -> Optional[User]:
    try:
        uid, exp, sig = token.split(".")
        if int(exp) < time.time():
            return None
        user = session.get(User, int(uid))
        if user and hmac.compare_digest(_sign(uid, exp, user.password_hash), _unb64(sig)):
            return user
    except Exception:
        pass
    return None


def set_session_cookie(response: Response, request: Request, user: User) -> None:
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(COOKIE, make_token(user), max_age=SESSION_DAYS * 86400, httponly=True,
                        samesite="lax", secure=https, path="/")


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


# ----------------------------------------------------------------------------- dependencies

def optional_user(request: Request, session: Session = Depends(get_session)) -> Optional[User]:
    return read_token(request.cookies.get(COOKIE, ""), session)


def current_user(user: Optional[User] = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, "Please log in")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Admins only")
    return user


def is_admin(user: User) -> bool:
    return user.role == "admin"


def scope(query, model, user: User):
    """Admins see everything; everyone else only their own rows."""
    return query if is_admin(user) else query.where(model.user_id == user.id)


def can_access(user: User, owner_id: Optional[int]) -> bool:
    return is_admin(user) or owner_id == user.id


def claim_orphans(session: Session, admin: User) -> None:
    """Data created before accounts existed is given to the first admin."""
    for model in (Inspection, Incident):
        for row in session.exec(select(model).where(model.user_id == None)).all():  # noqa: E711
            row.user_id = admin.id
            session.add(row)
    session.commit()
