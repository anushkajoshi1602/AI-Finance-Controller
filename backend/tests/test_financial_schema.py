"""Financial schema and additive migration tests on isolated databases."""

import unittest
import uuid
import tempfile
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import Table

from backend.db import (
    Base,
    Business,
    Customer,
    ImportBatch,
    Payment,
)
from backend.db.database import build_engine
from backend.db.financial_migrations import (
    FINANCIAL_MIGRATION_VERSION,
    IMPORT_BATCH_VALIDATION_MIGRATION_VERSION,
    FINANCIAL_TABLES,
    upgrade_financial_schema,
)
from backend.db import financial_migrations
from backend.init_db import init_db


class FinancialSchemaTest(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.connection = self.engine.connect()

    def tearDown(self):
        if self.connection is not None:
            self.connection.close()
        self.engine.dispose()

    def _business(self, suffix):
        business = Business(
            id=str(uuid.uuid4()),
            name=f"Merchant {suffix}",
            slug=f"merchant-{suffix}",
        )
        self.connection.execute(Business.__table__.insert().values(
            id=business.id,
            name=business.name,
            slug=business.slug,
        ))
        return business.id

    def _batch(self, business_id, suffix="payments"):
        batch = ImportBatch(
            id=str(uuid.uuid4()),
            business_id=business_id,
            dataset_type=suffix,
            original_filename=f"{suffix}.csv",
            storage_key=f"opaque/{business_id}/{suffix}",
            content_hash="a" * 64,
        )
        self.connection.execute(ImportBatch.__table__.insert().values(
            id=batch.id,
            business_id=batch.business_id,
            dataset_type=batch.dataset_type,
            original_filename=batch.original_filename,
            storage_key=batch.storage_key,
            content_hash=batch.content_hash,
        ))
        return batch.id

    def test_all_financial_tables_are_created(self):
        tables = set(inspect(self.engine).get_table_names())
        self.assertTrue(set(FINANCIAL_TABLES) <= tables)
        self.assertTrue({
            "import_batches",
            "financial_runs",
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
        } <= tables)

    def test_duplicate_external_id_is_rejected_within_business(self):
        business_id = self._business("one")
        batch_id = self._batch(business_id)
        self.connection.execute(Payment.__table__.insert().values(
            business_id=business_id,
            import_batch_id=batch_id,
            external_id="pay-duplicate",
            amount=100,
            status="Success",
        ))
        with self.assertRaises(IntegrityError):
            self.connection.execute(Payment.__table__.insert().values(
                business_id=business_id,
                import_batch_id=batch_id,
                external_id="pay-duplicate",
                amount=200,
                status="Success",
            ))

    def test_same_external_id_is_allowed_across_businesses(self):
        first_business = self._business("one")
        second_business = self._business("two")
        first_batch = self._batch(first_business)
        second_batch = self._batch(second_business)
        self.connection.execute(Payment.__table__.insert().values(
            business_id=first_business,
            import_batch_id=first_batch,
            external_id="shared-payment-id",
            amount=100,
            status="Success",
        ))
        self.connection.execute(Payment.__table__.insert().values(
            business_id=second_business,
            import_batch_id=second_batch,
            external_id="shared-payment-id",
            amount=200,
            status="Success",
        ))

    def test_cross_business_customer_payment_relationship_is_rejected(self):
        first_business = self._business("one")
        second_business = self._business("two")
        first_batch = self._batch(first_business)
        second_batch = self._batch(second_business, "customers")
        self.connection.execute(Customer.__table__.insert().values(
            business_id=second_business,
            import_batch_id=second_batch,
            external_id="customer-shared-id",
            name="Customer",
        ))
        with self.assertRaises(IntegrityError):
            self.connection.execute(Payment.__table__.insert().values(
                business_id=first_business,
                import_batch_id=first_batch,
                external_id="pay-cross-tenant",
                customer_external_id="customer-shared-id",
                amount=125,
                status="Success",
            ))

    def test_import_batch_cannot_be_linked_across_businesses(self):
        first_business = self._business("one")
        second_business = self._business("two")
        foreign_batch = self._batch(second_business)
        with self.assertRaises(IntegrityError):
            self.connection.execute(Payment.__table__.insert().values(
                business_id=first_business,
                import_batch_id=foreign_batch,
                external_id="pay-wrong-batch",
                amount=100,
                status="Success",
            ))

    def test_additive_migration_is_repeatable_and_preserves_existing_rows(self):
        self.connection.close()
        self.connection = None
        foundation_engine = build_engine("sqlite:///:memory:")
        try:
            Base.metadata.create_all(
                foundation_engine,
                tables=[
                    Base.metadata.tables[name]
                    for name in ("users", "businesses", "business_memberships")
                ],
            )
            with foundation_engine.begin() as connection:
                connection.execute(Business.__table__.insert().values(
                    id="preserved-business",
                    name="Preserved",
                    slug="preserved",
                ))
            created = upgrade_financial_schema(foundation_engine)
            self.assertEqual(set(created), set(FINANCIAL_TABLES))
            self.assertEqual(upgrade_financial_schema(foundation_engine), [])
            with foundation_engine.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        Business.__table__.select().with_only_columns(Business.id)
                    ).scalar_one(),
                    "preserved-business",
                )
                versions = connection.exec_driver_sql(
                    "SELECT version FROM schema_migrations"
                ).scalars().all()
                self.assertEqual(versions, [FINANCIAL_MIGRATION_VERSION, IMPORT_BATCH_VALIDATION_MIGRATION_VERSION])
        finally:
            foundation_engine.dispose()

    def _identity_only_engine(self):
        engine = build_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in ("users", "businesses", "business_memberships")])
        return engine

    def test_interrupted_v2_creation_resumes_and_preserves_existing_rows(self):
        engine = self._identity_only_engine()
        original_create = Table.create
        created = 0

        def interrupt_after_first_financial_table(table, *args, **kwargs):
            nonlocal created
            result = original_create(table, *args, **kwargs)
            if table.name in FINANCIAL_TABLES:
                created += 1
                if created == 1:
                    raise RuntimeError("simulated interruption")
            return result

        try:
            with engine.begin() as connection:
                connection.execute(Business.__table__.insert().values(id="resume-business", name="Preserved", slug="resume"))
            with patch.object(Table, "create", new=interrupt_after_first_financial_table):
                with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                    upgrade_financial_schema(engine)
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO import_batches (id,business_id,dataset_type,original_filename,storage_key,uploaded_at,validation_status,content_hash) VALUES ('batch-preserved','resume-business','customers','x.csv','opaque-x','2026-01-01','validated',:hash)"), {"hash": "a" * 64})
            self.assertEqual(upgrade_financial_schema(engine)[0], "financial_runs")
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT business_id FROM import_batches WHERE id='batch-preserved'")).scalar_one(), "resume-business")
                self.assertEqual(connection.execute(text("SELECT validation_errors FROM import_batches WHERE id='batch-preserved'")).scalar_one(), None)
        finally:
            engine.dispose()

    def test_v3_adds_required_column_and_hash_uniqueness_to_v2_rows(self):
        engine = self._identity_only_engine()
        try:
            with engine.begin() as connection:
                connection.execute(Business.__table__.insert().values(id="v2-business", name="V2", slug="v2"))
            financial_migrations._apply_v2(engine)
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO import_batches (id,business_id,dataset_type,original_filename,storage_key,uploaded_at,validation_status,content_hash) VALUES ('v2-batch','v2-business','customers','x.csv','opaque-v2','2026-01-01','validated',:hash)"), {"hash": "b" * 64})
            upgrade_financial_schema(engine)
            inspector = inspect(engine)
            self.assertIn("validation_errors", {c["name"] for c in inspector.get_columns("import_batches")})
            unique_cols = {tuple(row["column_names"]) for row in inspector.get_unique_constraints("import_batches")}
            self.assertIn(("business_id", "dataset_type", "content_hash"), unique_cols)
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT id FROM import_batches WHERE id='v2-batch'")).scalar_one(), "v2-batch")
        finally:
            engine.dispose()

    def test_partial_v3_constraint_shape_fails_safely(self):
        engine = self._identity_only_engine()
        try:
            financial_migrations._apply_v2(engine)
            with engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE import_batches ADD COLUMN validation_errors TEXT")
            with self.assertRaisesRegex(RuntimeError, "Incompatible financial schema|unexpected partial 0003 shape"):
                upgrade_financial_schema(engine)
            self.assertIn("import_batches", inspect(engine).get_table_names())
        finally:
            engine.dispose()

    def test_v3_rebuild_before_version_record_resumes(self):
        engine = self._identity_only_engine()
        try:
            financial_migrations._apply_v2(engine)
            financial_migrations._upgrade_import_batches_v3(engine)
            # Simulates an interruption after the table rebuild committed but
            # before 0003's version row was written.
            self.assertEqual(upgrade_financial_schema(engine), [])
            with engine.connect() as connection:
                versions = connection.execute(text("SELECT version FROM schema_migrations ORDER BY version")).scalars().all()
                self.assertEqual(versions, [FINANCIAL_MIGRATION_VERSION, IMPORT_BATCH_VALIDATION_MIGRATION_VERSION])
        finally:
            engine.dispose()

    def test_v3_duplicate_existing_hashes_fail_without_losing_rows(self):
        engine = self._identity_only_engine()
        try:
            with engine.begin() as connection:
                connection.execute(Business.__table__.insert().values(id="dupe-business", name="Duplicate", slug="dupe"))
            financial_migrations._apply_v2(engine)
            with engine.begin() as connection:
                for batch_id in ("dupe-1", "dupe-2"):
                    connection.execute(text("INSERT INTO import_batches (id,business_id,dataset_type,original_filename,storage_key,uploaded_at,validation_status,content_hash) VALUES (:id,'dupe-business','customers','x.csv',:key,'2026-01-01','validated',:hash)"), {"id": batch_id, "key": f"opaque-{batch_id}", "hash": "c" * 64})
            with self.assertRaisesRegex(RuntimeError, "duplicate existing business/dataset/content hashes"):
                upgrade_financial_schema(engine)
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT COUNT(*) FROM import_batches")).scalar_one(), 2)
        finally:
            engine.dispose()

    def test_initialization_preserves_identity_rows_and_local_csv_files(self):
        engine = build_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in ("users", "businesses", "business_memberships")])
        try:
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO users (id,email,password_hash,is_active,created_at,updated_at) VALUES ('u1','u@example.com','hash',1,'2026-01-01','2026-01-01')"))
                connection.execute(text("INSERT INTO businesses (id,name,slug,base_currency,timezone,status,created_at,updated_at,created_by_user_id) VALUES ('b1','Business','business','INR','Asia/Kolkata','active','2026-01-01','2026-01-01','u1')"))
                connection.execute(text("INSERT INTO business_memberships (id,business_id,user_id,role,status,created_at,updated_at) VALUES ('m1','b1','u1','owner','active','2026-01-01','2026-01-01')"))
            with tempfile.TemporaryDirectory() as storage:
                csv_path = Path(storage) / "existing.csv"
                upload_path = Path(storage) / "opaque-upload.csv"
                csv_path.write_bytes(b"legacy,csv\n1,2\n")
                upload_path.write_bytes(b"uploaded bytes\n")
                before = {p.name: p.read_bytes() for p in (csv_path, upload_path)}
                init_db(engine)
                self.assertEqual({p.name: p.read_bytes() for p in (csv_path, upload_path)}, before)
            with engine.connect() as connection:
                for table, identity in (("users", "u1"), ("businesses", "b1"), ("business_memberships", "m1")):
                    self.assertEqual(connection.execute(text(f"SELECT id FROM {table}")).scalar_one(), identity)
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
