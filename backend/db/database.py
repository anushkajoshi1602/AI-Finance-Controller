"""Database configuration and session management.

Configuration is read from the ``DATABASE_URL`` environment variable. If it is
not set, a local SQLite database is used at ``<project-root>/instance/ai_finance.db``.

``backend/.env`` is loaded (without overriding real environment variables) so the
URL can live next to the other backend settings. Nothing in this module prints
or logs the URL, because production URLs contain credentials.

The models only use portable SQLAlchemy types, so switching to PostgreSQL later
means changing ``DATABASE_URL`` (e.g. ``postgresql+psycopg://...``) and installing
the driver.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "instance" / "ai_finance.db"

# Read-only use of backend/.env; never overrides variables already set.
load_dotenv(BACKEND_DIR / ".env", override=False)


def get_database_url() -> str:
    """Return the configured database URL (do not print it: it may hold secrets)."""
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    return f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"


def safe_url_for_display(url: str) -> str:
    """Render a URL with any password masked, for diagnostics only."""
    return make_url(url).render_as_string(hide_password=True)


def build_engine(url: str | None = None, **kwargs) -> Engine:
    url = url or get_database_url()
    parsed = make_url(url)
    connect_args = dict(kwargs.pop("connect_args", {}))

    if parsed.get_backend_name() == "sqlite":
        # FastAPI may use the session from a different thread than it was created on.
        connect_args.setdefault("check_same_thread", False)
        db_path = parsed.database
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    return create_engine(url, connect_args=connect_args, future=True, **kwargs)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite ignores FOREIGN KEY constraints unless this pragma is on per connection."""
    module = type(dbapi_connection).__module__
    if module.startswith("sqlite3") or module.startswith("pysqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine: Engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
