"""Versioned financial migrations with explicit SQLite recovery and verification."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, Index, MetaData, String,
    Table, Text, UniqueConstraint, inspect, select, text,
)
from sqlalchemy.schema import CreateTable
from sqlalchemy.engine import Engine

from .database import Base
from . import models as _models  # noqa: F401 - registers all mapped tables


FINANCIAL_MIGRATION_VERSION = "0002_financial_data"
IMPORT_BATCH_VALIDATION_MIGRATION_VERSION = "0003_import_batch_validation_and_idempotency"
FINANCIAL_TABLES = (
    "import_batches",
    "financial_runs",
    "financial_run_import_batches",
    "customers",
    "payments",
    "refunds",
    "settlements",
    "bank_transactions",
    "reconciliation_results",
    "bank_reconciliation_results",
    "anomalies",
    "investigation_results",
    "cash_flow_forecasts",
)

_migration_metadata = MetaData()
_schema_migrations = Table(
    "schema_migrations",
    _migration_metadata,
    Column("version", String(100), primary_key=True),
    Column("applied_at", DateTime(timezone=True), nullable=False),
)


def _legacy_import_batches() -> Table:
    """Frozen import_batches definition from migration 0002 (before v3 fields)."""
    metadata = MetaData()
    # Register the referenced identity table so SQLAlchemy can compile the
    # frozen FK while this metadata is used by the migration tests/runtime.
    Base.metadata.tables["businesses"].to_metadata(metadata)
    table = Table(
        "import_batches", metadata,
        Column("id", String(36), primary_key=True),
        Column("business_id", String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        Column("dataset_type", String(40), nullable=False),
        Column("original_filename", String(255), nullable=False),
        Column("storage_key", String(255), nullable=False, unique=True),
        Column("uploaded_at", DateTime(timezone=True), nullable=False),
        Column("validation_status", String(20), nullable=False),
        Column("content_hash", String(64), nullable=False),
        UniqueConstraint("business_id", "id", name="uq_import_batches_business_id_id"),
        CheckConstraint("dataset_type IN ('customers', 'payments', 'refunds', 'settlements', 'bank_transactions')", name="ck_import_batches_dataset_type"),
        CheckConstraint("validation_status IN ('uploaded', 'validating', 'validated', 'failed')", name="ck_import_batches_validation_status"),
        Index("ix_import_batches_business_uploaded", "business_id", "uploaded_at"),
    )
    return table


LEGACY_IMPORT_BATCHES = _legacy_import_batches()


def _shape(engine: Engine, table: Table) -> list[str]:
    """Return structural differences in required columns, FKs, uniques and indexes."""
    inspector = inspect(engine)
    name = table.name
    if name not in inspector.get_table_names():
        return [f"missing table {name}"]
    errors = []
    expected_columns = set(table.columns.keys())
    actual_columns = {column["name"] for column in inspector.get_columns(name)}
    if expected_columns != actual_columns:
        errors.append(f"columns expected {sorted(expected_columns)}, found {sorted(actual_columns)}")
    expected_pk = tuple(column.name for column in table.primary_key.columns)
    actual_pk = tuple(inspector.get_pk_constraint(name).get("constrained_columns") or ())
    if expected_pk != actual_pk:
        errors.append(f"primary key expected {expected_pk}, found {actual_pk}")
    def fk_set(rows):
        return {(tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"])) for fk in rows}
    expected_fks = {(tuple(element.parent.name for element in constraint.elements), constraint.elements[0].column.table.name,
                     tuple(element.column.name for element in constraint.elements))
                    for constraint in table.foreign_key_constraints}
    actual_fks = fk_set(inspector.get_foreign_keys(name))
    if expected_fks != actual_fks:
        errors.append(f"foreign keys expected {sorted(expected_fks)}, found {sorted(actual_fks)}")
    expected_uniques = {tuple(column.name for column in constraint.columns)
                        for constraint in table.constraints if isinstance(constraint, UniqueConstraint)}
    # Column-level unique=True is exposed separately by SQLAlchemy as a unique index.
    actual_unique_rows = inspector.get_unique_constraints(name)
    actual_uniques = {tuple(row["column_names"]) for row in actual_unique_rows}
    expected_unique_indexes = {tuple(index.columns.keys()) for index in table.indexes if index.unique}
    actual_indexes = inspector.get_indexes(name)
    actual_unique_indexes = {tuple(row["column_names"]) for row in actual_indexes if row.get("unique")}
    if expected_uniques != actual_uniques or expected_unique_indexes != actual_unique_indexes:
        errors.append(f"unique constraints/indexes expected {sorted(expected_uniques | expected_unique_indexes)}, found {sorted(actual_uniques | actual_unique_indexes)}")
    expected_indexes = {(index.name, tuple(index.columns.keys())) for index in table.indexes if not index.unique}
    actual_named_indexes = {(row["name"], tuple(row["column_names"])) for row in actual_indexes if not row.get("unique")}
    if expected_indexes != actual_named_indexes:
        errors.append(f"indexes expected {sorted(expected_indexes)}, found {sorted(actual_named_indexes)}")
    normalize = lambda value: "".join(str(value).lower().split()).replace("(", "").replace(")", "")
    expected_checks = {normalize(constraint.sqltext) for constraint in table.constraints if isinstance(constraint, CheckConstraint)}
    actual_checks = {normalize(row["sqltext"]) for row in inspector.get_check_constraints(name)}
    if expected_checks != actual_checks:
        errors.append(f"check constraints expected {sorted(expected_checks)}, found {sorted(actual_checks)}")
    return errors


def _verify_tables(engine: Engine, *, legacy_import_batch: bool = False) -> None:
    for name in FINANCIAL_TABLES:
        table = LEGACY_IMPORT_BATCHES if name == "import_batches" and legacy_import_batch else Base.metadata.tables[name]
        differences = _shape(engine, table)
        if differences:
            raise RuntimeError(f"Incompatible financial schema in {name!r}: {'; '.join(differences)}")


def _verify_v2_or_completed_v3(engine: Engine) -> None:
    """Validate other v2 tables and allow v3's rebuild to have committed pre-marker."""
    for name in FINANCIAL_TABLES:
        table = Base.metadata.tables[name]
        if name == "import_batches":
            legacy_errors = _shape(engine, LEGACY_IMPORT_BATCHES)
            current_errors = _shape(engine, table)
            if not legacy_errors or not current_errors:
                continue
            raise RuntimeError(
                "Incompatible financial schema in 'import_batches': neither frozen 0002 "
                f"nor complete 0003 shape matches (0002: {'; '.join(legacy_errors)}; "
                f"0003: {'; '.join(current_errors)})"
            )
        differences = _shape(engine, table)
        if differences:
            raise RuntimeError(f"Incompatible financial schema in {name!r}: {'; '.join(differences)}")


def _record_version(engine: Engine, version: str) -> None:
    with engine.begin() as connection:
        connection.execute(_schema_migrations.insert().values(
            version=version, applied_at=datetime.now(timezone.utc),
        ))


def _has_version(engine: Engine, version: str) -> bool:
    with engine.begin() as connection:
        return connection.execute(select(_schema_migrations.c.version).where(
            _schema_migrations.c.version == version,
        )).first() is not None


def _apply_v2(engine: Engine) -> list[str]:
    """Apply the frozen 0002 schema without the later import-batch additions."""
    _schema_migrations.create(engine, checkfirst=True)
    created = []
    for name in FINANCIAL_TABLES:
        table = LEGACY_IMPORT_BATCHES if name == "import_batches" else Base.metadata.tables[name]
        existed = name in inspect(engine).get_table_names()
        if existed:
            differences = _shape(engine, table)
            if differences:
                raise RuntimeError(f"Cannot safely resume migration 0002 in {name!r}: {'; '.join(differences)}")
        else:
            table.create(engine)
            created.append(name)
    _verify_tables(engine, legacy_import_batch=True)
    _record_version(engine, FINANCIAL_MIGRATION_VERSION)
    return created


def _upgrade_import_batches_v3(engine: Engine) -> None:
    """SQLite-safe rebuild to add validation_errors and upload hash uniqueness."""
    table = Base.metadata.tables["import_batches"]
    differences = _shape(engine, table)
    if not differences:
        return
    inspector = inspect(engine)
    if "import_batches" not in inspector.get_table_names():
        raise RuntimeError("Cannot apply 0003: import_batches is missing; rerun/resume 0002 first")
    old_columns = {column["name"] for column in inspector.get_columns("import_batches")}
    required_v2_columns = set(LEGACY_IMPORT_BATCHES.columns.keys())
    if old_columns != required_v2_columns:
        raise RuntimeError(
            "Cannot safely rebuild import_batches for 0003: existing columns do not match frozen 0002 shape; "
            "manual review required"
        )
    if "validation_errors" in old_columns:
        raise RuntimeError("Cannot safely repair import_batches: unexpected partial 0003 shape; manual review required")
    with engine.connect() as check_connection:
        duplicate_hashes = check_connection.exec_driver_sql(
            "SELECT business_id, dataset_type, content_hash FROM import_batches "
            "GROUP BY business_id, dataset_type, content_hash HAVING COUNT(*) > 1 LIMIT 5"
        ).all()
    if duplicate_hashes:
        raise RuntimeError(
            "Cannot apply 0003 upload uniqueness: duplicate existing business/dataset/content hashes "
            f"must be reviewed first (examples: {duplicate_hashes})"
        )

    metadata = MetaData()
    Base.metadata.tables["businesses"].to_metadata(metadata)
    temp = table.to_metadata(metadata, name="import_batches__0003_new")
    temp_indexes = []
    for index in list(temp.indexes):
        original_name = index.name
        index.name = f"{original_name}__0003_new"
        temp_indexes.append((index.name, original_name))

    connection = engine.connect()
    try:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        transaction = connection.begin()
        try:
            # sqlite3's legacy transaction mode does not start a DB transaction
            # for DDL by itself; force one so the rebuild rolls back as a unit.
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            connection.execute(CreateTable(temp))
            new_cols = list(table.columns.keys())
            old_cols = [column for column in new_cols if column != "validation_errors"]
            quoted_new = ", ".join(f'"{c}"' for c in new_cols)
            selected = ", ".join(f'"{c}"' if c in old_columns else "NULL" for c in new_cols)
            connection.exec_driver_sql(
                f'INSERT INTO "{temp.name}" ({quoted_new}) SELECT {selected} FROM "import_batches"'
            )
            connection.exec_driver_sql('DROP TABLE "import_batches"')
            connection.exec_driver_sql(f'ALTER TABLE "{temp.name}" RENAME TO "import_batches"')
            for temp_name, _ in temp_indexes:
                connection.exec_driver_sql(f'DROP INDEX IF EXISTS "{temp_name}"')
            for index in table.indexes:
                index.create(connection, checkfirst=True)
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
            if violations:
                raise RuntimeError(f"SQLite foreign-key check failed after 0003 rebuild: {violations[:5]}")
            transaction.commit()
        except Exception:
            transaction.rollback()
            raise
        _verify_tables(engine, legacy_import_batch=False)
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f"Could not safely rebuild import_batches for migration 0003: {exc}") from exc
    finally:
        if connection.in_transaction():
            connection.rollback()
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.commit()
        connection.close()


def upgrade_financial_schema(engine: Engine) -> list[str]:
    """Apply/resume 0002, then upgrade import batch structure with 0003."""
    inspector = inspect(engine)
    if "businesses" not in inspector.get_table_names():
        raise RuntimeError("Initialize the identity schema before financial migrations")
    _schema_migrations.create(engine, checkfirst=True)
    created = []
    has_v2 = _has_version(engine, FINANCIAL_MIGRATION_VERSION)
    has_v3 = _has_version(engine, IMPORT_BATCH_VALIDATION_MIGRATION_VERSION)
    if has_v2:
        # A recorded version is not accepted as proof that the schema remains intact.
        if has_v3:
            _verify_tables(engine)
        else:
            _verify_v2_or_completed_v3(engine)
    else:
        created = _apply_v2(engine)

    if has_v3:
        _verify_tables(engine)
    else:
        _upgrade_import_batches_v3(engine)
        _verify_tables(engine)
        _record_version(engine, IMPORT_BATCH_VALIDATION_MIGRATION_VERSION)
    return created


