"""CSV import tests use a fresh in-memory database for every test."""

import unittest
import tempfile
from pathlib import Path
from io import BytesIO

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.auth import create_access_token, hash_password
from backend.db.database import Base, build_engine, get_db
from backend.db.models import (Business, BusinessMembership, Customer, ImportBatch,
                               MembershipRole, MembershipStatus, Payment, User)
from backend.main import app
from backend import csv_import_routes


class CsvImportTest(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine("sqlite:///:memory:", poolclass=StaticPool)
        self.storage = tempfile.TemporaryDirectory()
        self.previous_storage_dir = csv_import_routes.STORAGE_DIR
        csv_import_routes.STORAGE_DIR = Path(self.storage.name)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            self.user = User(email="imports@example.com", password_hash=hash_password("test-pass"), full_name="Import User")
            self.other = User(email="outsider@example.com", password_hash=hash_password("test-pass"), full_name="Outsider")
            db.add_all([self.user, self.other]); db.flush()
            self.user_id, self.other_id = self.user.id, self.other.id
            self.other_business = Business(name="Other Workspace", slug="other-workspace", created_by_user_id=self.other_id)
            db.add(self.other_business); db.flush()
            self.other_business_id = self.other_business.id
            db.add(BusinessMembership(business_id=self.other_business_id, user_id=self.other_id, role="owner", status="active"))
            db.commit()
        def override():
            db = self.Session()
            try: yield db
            finally: db.close()
        app.dependency_overrides[get_db] = override
        self.client = TestClient(app)
        self.headers = {"Authorization": f"Bearer {create_access_token(self.user_id)}"}
        created = self.client.post("/api/businesses", json={"name": "Temporary Import Test Business"}, headers=self.headers)
        if created.status_code != 201:
            raise AssertionError(created.text)
        self.business_id = created.json()["business"]["id"]

    def tearDown(self):
        self.client.close(); app.dependency_overrides.clear(); self.engine.dispose()
        csv_import_routes.STORAGE_DIR = self.previous_storage_dir
        self.storage.cleanup()

    def upload(self, dataset, content, headers=None, filename="unsafe-name.csv"):
        return self.client.post(f"/api/businesses/{self.business_id}/imports/{dataset}",
            files={"file": (filename, content, "text/csv")}, headers=self.headers if headers is None else headers)

    def test_success_and_retry_are_idempotent(self):
        data = b"external_id,name,email\nc1,Ada,ada@example.com\n"
        response = self.upload("customers", data)
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(result["status"], "validated")
        with self.Session() as db:
            customer = db.query(Customer).one()
            batch = db.get(ImportBatch, result["id"])
            self.assertEqual(customer.business_id, self.business_id)
            self.assertEqual(batch.business_id, self.business_id)
            self.assertEqual(customer.import_batch_id, batch.id)
            self.assertNotIn("unsafe-name", batch.storage_key)
            self.assertEqual(batch.content_hash, result["content_hash"])
        retried = self.upload("customers", data)
        self.assertTrue(retried.json()["duplicate_upload"])
        self.assertEqual(retried.json()["id"], result["id"])
        inspected = self.client.get(f"/api/businesses/{self.business_id}/imports/{result['id']}", headers=self.headers)
        self.assertEqual(inspected.status_code, 200)
        outsider = {"Authorization": f"Bearer {create_access_token(self.other_id)}"}
        hidden_batch = self.client.get(f"/api/businesses/{self.business_id}/imports/{result['id']}", headers=outsider)
        self.assertEqual(hidden_batch.status_code, 404)
        hidden_business = self.client.get(f"/api/businesses/{self.business_id}", headers=outsider)
        self.assertEqual(hidden_business.status_code, 404)

    def test_invalid_headers_are_recorded_without_rows(self):
        response = self.upload("payments", b"foo\nbar\n")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "failed")
        with self.Session() as db:
            self.assertEqual(db.query(Payment).count(), 0)
            self.assertEqual(db.query(ImportBatch).one().validation_errors, '["Missing required headers: amount, external_id, status"]')

    def test_invalid_amount_and_duplicate_ids_fail_atomically(self):
        response = self.upload("payments", b"external_id,amount,status\np1,nope,ok\np1,2.00,ok\n")
        self.assertEqual(response.json()["status"], "failed")
        with self.Session() as db: self.assertEqual(db.query(Payment).count(), 0)

    def test_existing_external_id_conflict_fails_atomically(self):
        data = b"external_id,amount,status\np1,1.00,ok\np1,2.00,ok\n"
        response = self.upload("payments", data)
        self.assertEqual(response.json()["status"], "failed")
        with self.Session() as db: self.assertEqual(db.query(Payment).count(), 0)

    def test_missing_reference_is_rejected(self):
        response = self.upload("refunds", b"external_id,payment_external_id,refund_amount\nr1,missing,1.00\n")
        self.assertEqual(response.json()["status"], "failed")

    def test_reference_to_another_business_is_rejected(self):
        other_headers = {"Authorization": f"Bearer {create_access_token(self.other_id)}"}
        other_upload = self.client.post(
            f"/api/businesses/{self.other_business_id}/imports/customers",
            files={"file": ("x.csv", b"customer_id,customer_name,customer_email\nforeign,Other,o@example.com\n", "text/csv")},
            headers=other_headers,
        )
        self.assertEqual(other_upload.status_code, 201, other_upload.text)
        payment = self.upload("payments", b"payment_id,customer_id,amount,status\np1,foreign,5.00,Success\n")
        self.assertEqual(payment.json()["status"], "failed")
        self.assertIn("does not exist in this business", payment.json()["validation_errors"][0])

    def test_unauthorized_and_cross_business_access_are_hidden(self):
        self.assertEqual(self.upload("customers", b"external_id\nc1\n", headers={}).status_code, 401)
        outsider = {"Authorization": f"Bearer {create_access_token(self.other_id)}"}
        self.assertEqual(self.upload("customers", b"external_id\nc1\n", headers=outsider).status_code, 404)

    def test_upload_business_id_column_is_ignored(self):
        response = self.upload("customers", f"external_id,name,email,business_id\nc1,Ada,ada@example.com,{self.other_business_id}\n".encode())
        self.assertEqual(response.json()["status"], "validated", response.text)
        with self.Session() as db: self.assertEqual(db.query(Customer).one().business_id, self.business_id)


if __name__ == "__main__": unittest.main()
