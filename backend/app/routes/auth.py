from __future__ import annotations

import hashlib
import os
import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import Session, func, select

from .. import mailer
from ..auth import (claim_orphans, clear_session_cookie, current_user, hash_password, set_session_cookie,
                    verify_password)
from ..db import PasswordReset, User, as_utc, get_session, iso, utcnow

router = APIRouter(prefix="/api/auth", tags=["auth"])
ALLOW_SIGNUP = os.environ.get("ALLOW_SIGNUP", "true").lower() in ("1", "true", "yes")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RESET_MINUTES = 30
RESET_COOLDOWN_SECONDS = 60


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    token: str
    password: str


def user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "created_at": iso(u.created_at)}


def _check_password(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.get("/config")
def auth_config(session: Session = Depends(get_session)):
    has_users = session.exec(select(func.count()).select_from(User)).one() > 0
    return {"signup_enabled": ALLOW_SIGNUP or not has_users, "first_user": not has_users,
            "email_enabled": mailer.email_enabled()}


@router.post("/register")
def register(body: RegisterIn, request: Request, response: Response, session: Session = Depends(get_session)):
    email = body.email.strip().lower()
    name = body.name.strip()
    first = session.exec(select(func.count()).select_from(User)).one() == 0
    if not (ALLOW_SIGNUP or first):
        raise HTTPException(403, "Sign-up is disabled; ask an admin for an account")
    if not name:
        raise HTTPException(400, "Please enter your name")
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Please enter a valid email address")
    _check_password(body.password)
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, name=name, password_hash=hash_password(body.password), role="admin" if first else "user")
    session.add(user)
    session.commit()
    session.refresh(user)
    if first:
        claim_orphans(session, user)
    set_session_cookie(response, request, user)
    return user_out(user)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == body.email.strip().lower())).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    set_session_cookie(response, request, user)
    return user_out(user)


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


# ----------------------------------------------------------------------------- password reset

@router.post("/forgot")
def forgot_password(body: ForgotIn, tasks: BackgroundTasks, session: Session = Depends(get_session)):
    """Always answers the same way, so nobody can find out which emails have accounts."""
    user = session.exec(select(User).where(User.email == body.email.strip().lower())).first()
    if user:
        last = session.exec(select(PasswordReset).where(PasswordReset.user_id == user.id)
                            .order_by(PasswordReset.created_at.desc())).first()
        recent = last and (utcnow() - as_utc(last.created_at)).total_seconds() < RESET_COOLDOWN_SECONDS
        if not recent:
            token = secrets.token_urlsafe(32)
            session.add(PasswordReset(user_id=user.id, token_hash=_token_hash(token),
                                      expires_at=utcnow() + timedelta(minutes=RESET_MINUTES)))
            session.commit()
            link = f"{mailer.app_url()}/reset-password?token={token}"
            tasks.add_task(mailer.deliver_reset_link, user.email, user.name, link, RESET_MINUTES)
    return {"ok": True}


def _valid_reset(session: Session, token: str) -> PasswordReset | None:
    row = session.exec(select(PasswordReset).where(PasswordReset.token_hash == _token_hash(token))).first()
    if row is None or row.used_at is not None or as_utc(row.expires_at) < utcnow():
        return None
    return row


@router.get("/reset/check")
def check_reset(token: str, session: Session = Depends(get_session)):
    return {"valid": _valid_reset(session, token) is not None}


@router.post("/reset")
def reset_password(body: ResetIn, request: Request, response: Response, session: Session = Depends(get_session)):
    row = _valid_reset(session, body.token)
    if row is None:
        raise HTTPException(400, "This reset link is invalid or has expired. Please request a new one.")
    _check_password(body.password)
    user = session.get(User, row.user_id)
    user.password_hash = hash_password(body.password)  # also invalidates every existing session
    now = utcnow()
    for r in session.exec(select(PasswordReset).where(PasswordReset.user_id == user.id,
                                                      PasswordReset.used_at == None)).all():  # noqa: E711
        r.used_at = now
        session.add(r)
    session.add(user)
    session.commit()
    session.refresh(user)
    set_session_cookie(response, request, user)
    return user_out(user)
