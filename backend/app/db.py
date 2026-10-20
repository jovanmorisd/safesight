"""Database models and engine.

`DATABASE_URL` (e.g. Supabase Postgres) selects the database; without it a local SQLite file in
`data/` is used, so development needs no setup. Settings can also come from `backend/.env`.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from sqlalchemy import JSON, Column, event, inspect, text
from sqlmodel import Field, Session, SQLModel, create_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")
DATA_DIR = Path(os.environ.get("PPE_DATA_DIR") or ("/tmp/ppe-data" if os.environ.get("VERCEL") else BACKEND_DIR / "data"))
MEDIA_DIR = DATA_DIR / "media"
CONFIG_PATH = Path(os.environ.get("PPE_CONFIG", BACKEND_DIR / "config.yaml"))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "30"))  # 0 keeps everything


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    """Timezone-aware UTC, whatever the database driver returned (SQLite stores no offset)."""
    return dt.replace(tzinfo=timezone.utc) if dt.utcoffset() is None else dt.astimezone(timezone.utc)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return None if dt is None else as_utc(dt).isoformat(timespec="seconds").replace("+00:00", "Z")


def JSONField(factory: Any = None) -> Any:  # noqa: N802 - mirrors Field()
    """JSON column; `factory` (list/dict) gives a fresh default per row, None means nullable."""
    if factory is None:
        return Field(default=None, sa_column=Column(JSON, nullable=True))
    return Field(default_factory=factory, sa_column=Column(JSON, nullable=False))


class User(SQLModel, table=True):
    __tablename__ = "app_user"  # "user" is a reserved word in Postgres
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str = ""
    password_hash: str
    role: str = "user"  # admin | user
    created_at: datetime = Field(default_factory=utcnow)


class PasswordReset(SQLModel, table=True):
    """One-time password-reset links. Only a hash of the token is stored."""
    __tablename__ = "password_reset"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="app_user.id", index=True)
    token_hash: str = Field(index=True, unique=True)
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)


class AppSetting(SQLModel, table=True):
    """Small key/value store, e.g. the session-signing secret when SECRET_KEY is not set."""
    __tablename__ = "app_setting"
    key: str = Field(primary_key=True)
    value: str


class Site(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    location: str = ""
    required_ppe: list = JSONField(list)
    created_at: datetime = Field(default_factory=utcnow)


class ModelVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    weights_path: str
    sha256: Optional[str] = None
    conf: float = 0.35
    imgsz: int = 640
    class_map: Optional[dict] = JSONField()  # None -> auto mapping
    classes: list = JSONField(list)
    supported: list = JSONField(list)
    is_active: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Inspection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="app_user.id", index=True)
    site_id: Optional[int] = Field(default=None, foreign_key="site.id", index=True)
    filename: str = ""
    image_path: str
    annotated_path: str
    width: int = 0
    height: int = 0
    level: str = "pose"  # kept for older databases; only one association method is used
    required: list = JSONField(list)
    supported: list = JSONField(list)
    model_label: str = ""
    model_ids: list = JSONField(list)
    status: str = "empty"  # compliant | violation | unknown | empty
    num_persons: int = 0
    num_violations: int = 0
    num_unknown: int = 0
    num_compliant: int = 0
    latency_ms: float = 0.0
    timings: dict = JSONField(dict)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class DetectionRow(SQLModel, table=True):
    __tablename__ = "detection"
    id: Optional[int] = Field(default=None, primary_key=True)
    inspection_id: int = Field(foreign_key="inspection.id", index=True)
    label: str  # canonical class name ("cls" would clash with SQLModel.__new__)
    raw_label: str
    conf: float
    box: list = JSONField(list)
    source: str = ""


class PersonRow(SQLModel, table=True):
    __tablename__ = "person_assessment"
    id: Optional[int] = Field(default=None, primary_key=True)
    inspection_id: int = Field(foreign_key="inspection.id", index=True)
    idx: int
    box: list = JSONField(list)
    conf: float = 0.0
    has_pose: bool = False
    overall: str = "unknown"
    missing: list = JSONField(list)
    uncertain: list = JSONField(list)
    items: dict = JSONField(dict)
    crop_path: str = ""


class Incident(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="app_user.id", index=True)
    inspection_id: int = Field(foreign_key="inspection.id", index=True)
    person_id: int = Field(foreign_key="person_assessment.id")
    site_id: Optional[int] = Field(default=None, foreign_key="site.id", index=True)
    kind: str = "violation"  # violation | review
    items: list = JSONField(list)
    severity: str = "medium"
    status: str = Field(default="open", index=True)  # open | confirmed | false_positive | resolved
    reviewer: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=utcnow, index=True)
    reviewed_at: Optional[datetime] = None


def _make_engine():
    if DATABASE_URL:
        # Supabase gives "postgresql://..." (or legacy "postgres://"); use the psycopg 3 driver.
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        url = url.replace("postgresql://", "postgresql+psycopg://", 1) if "+" not in url.split("://")[0] else url
        return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=1800)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    eng = create_engine(f"sqlite:///{(DATA_DIR / 'ppe.db').as_posix()}",
                        connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _):  # behave like Postgres: enforce foreign keys
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return eng


engine = _make_engine()
DB_KIND = engine.dialect.name  # "postgresql" | "sqlite"


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Tiny migration for databases created before user accounts existed."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in ("inspection", "incident"):
            if "user_id" not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES app_user(id)"))
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table} (user_id)"))


def get_session():
    with Session(engine) as session:
        yield session
