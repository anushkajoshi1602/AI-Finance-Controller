"""Initialize the identity schema and apply additive financial migrations.

Usage (from the project root):
    venv\\Scripts\\python.exe backend\\init_db.py

Identity tables are initialized additively. Financial tables are managed by a
versioned migration that creates only explicitly listed new tables and never
drops or alters existing tables. Do not use ``create_all`` as a migration tool.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import inspect  # noqa: E402

from db import Base, engine, get_database_url  # noqa: E402
from db import models  # noqa: E402,F401  (registers models on Base.metadata)
from db.database import safe_url_for_display  # noqa: E402
from db.financial_migrations import upgrade_financial_schema  # noqa: E402

IDENTITY_TABLES = ("users", "businesses", "business_memberships")


def init_db(db_engine=None) -> list[str]:
    """Initialize identity tables and financial migrations on the supplied engine.

    Passing an engine keeps migration callers/tests isolated; the default remains
    the configured application engine.
    """
    db_engine = db_engine or engine
    Base.metadata.create_all(
        bind=db_engine,
        tables=[Base.metadata.tables[name] for name in IDENTITY_TABLES],
    )
    upgrade_financial_schema(db_engine)
    return sorted(inspect(db_engine).get_table_names())


if __name__ == "__main__":
    tables = init_db()
    print(f"Database: {safe_url_for_display(get_database_url())}")
    print(f"Tables: {', '.join(tables)}")
