"""Business-scoped reconciliation API tests using isolated SQLite and storage."""

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import csv_import_routes
from backend.auth import create_access_token
from backend.db.database import Base, build_engine, get_db
from backend.db.models import (
    Business,
    BusinessMembership,
    FinancialRun,
    FinancialRunImportBatch,
    ImportBatch,
    MembershipRole,
    MembershipStatus,
    Payment,
    ReconciliationResult,
    User,
)
from backend.main import app


class ReconciliationApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine("sqlite:///:memory:", poolclass=StaticPool)
        self.storage = tempfile.TemporaryDirectory()
        self.previous_storage_dir = csv_import_routes.STORAGE_DIR
        csv_import_routes.STORAGE_DIR = Path(self.storage.name)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            self.user_a = User(email="recon-a@example.com", password_hash="test-hash")
            self.user_b = User(email="recon-b@example.com", password_hash="test-hash")
            self.revoked_user = User(email="recon-revoked@example.com", password_hash="test-hash")
            db.add_all([self.user_a, self.user_b, self.revoked_user])
            db.flush()
            self.user_a_id = self.user_a.id
            self.user_b_id = self.user_b.id
            self.revoked_user_id = self.revoked_user.id
            self.business_a = Business(name="Reconciliation A", slug="reconciliation-a")
            self.business_b = Business(name="Reconciliation B", slug="reconciliation-b")
            db.add_all([self.business_a, self.business_b])
            db.flush()
            self.business_a_id = self.business_a.id
            self.business_b_id = self.business_b.id
            db.add_all([
                BusinessMembership(business_id=self.business_a_id, user_id=self.user_a_id,
                                   role=MembershipRole.OWNER.value, status=MembershipStatus.ACTIVE.value),
                BusinessMembership(business_id=self.business_b_id, user_id=self.user_b_id,
                                   role=MembershipRole.OWNER.value, status=MembershipStatus.ACTIVE.value),
                BusinessMembership(business_id=self.business_a_id, user_id=self.revoked_user_id,
                                   role=MembershipRole.ANALYST.value, status=MembershipStatus.REVOKED.value),
            ])
            db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        self.previous_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.headers_a = {"Authorization": f"Bearer {create_access_token(self.user_a_id)}"}
        self.headers_b = {"Authorization": f"Bearer {create_access_token(self.user_b_id)}"}
        self.headers_revoked = {"Authorization": f"Bearer {create_access_token(self.revoked_user_id)}"}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.previous_overrides)
        self.engine.dispose()
        csv_import_routes.STORAGE_DIR = self.previous_storage_dir
        self.storage.cleanup()

    def upload(self, business_id, dataset, data, headers):
        response = self.client.post(
            f"/api/businesses/{business_id}/imports/{dataset}",
            files={"file": (f"{dataset}.csv", data, "text/csv")},
            headers=headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["status"], "validated", response.text)
        return response.json()

    def import_reconciliation_data(self, business_id, headers, *, payment_amount="100.00"):
        self.upload(
            business_id, "customers",
            b"external_id,name,email\nc1,Customer One,c1@example.com\nc2,Customer Two,c2@example.com\n",
            headers,
        )
        self.upload(
            business_id, "payments",
            f"external_id,customer_external_id,amount,status\np1,c1,{payment_amount},Success\np2,c2,50.00,Success\n".encode(),
            headers,
        )
        self.upload(
            business_id, "refunds",
            b"external_id,payment_external_id,refund_amount\nr1,p1,10.00\n",
            headers,
        )
        self.upload(
            business_id, "settlements",
            b"external_id,payment_external_id,gross_amount,refund_amount,fee,tax,net_amount\ns1,p1,100.00,10.00,2.00,0.36,87.64\n",
            headers,
        )

    def test_reconciliation_persists_matched_and_missing_settlement_results(self):
        self.import_reconciliation_data(self.business_a_id, self.headers_a)
        response = self.client.post(
            f"/api/businesses/{self.business_a_id}/reconciliation/run",
            headers=self.headers_a,
        )
        self.assertEqual(response.status_code, 201, response.text)
        run_id = response.json()["run_id"]
        self.assertEqual(response.json()["status"], "succeeded")
        self.assertEqual(response.json()["result_count"], 2)

        results_response = self.client.get(
            f"/api/businesses/{self.business_a_id}/reconciliation/results",
            params={"run_id": run_id},
            headers=self.headers_a,
        )
        self.assertEqual(results_response.status_code, 200, results_response.text)
        results = {row["payment_external_id"]: row for row in results_response.json()["results"]}
        self.assertEqual(results["p1"]["status"], "Matched")
        self.assertEqual(Decimal(results["p1"]["expected_settlement"]), Decimal("87.64"))
        self.assertEqual(Decimal(results["p1"]["difference"]), Decimal("0.00"))
        self.assertEqual(results["p1"]["settlement_external_id"], "s1")
        self.assertEqual(results["p2"]["status"], "Missing Settlement")
        self.assertIsNone(results["p2"]["settlement_external_id"])
        self.assertIsNone(results["p2"]["expected_settlement"])

        with self.Session() as db:
            run = db.get(FinancialRun, run_id)
            rows = db.query(ReconciliationResult).filter_by(business_id=self.business_a_id, run_id=run_id).all()
            provenance = db.query(FinancialRunImportBatch).filter_by(business_id=self.business_a_id, run_id=run_id).all()
            self.assertEqual(run.status, "succeeded")
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(provenance), 3)
            self.assertEqual({row.business_id for row in rows}, {self.business_a_id})

    def test_empty_datasets_create_successful_empty_run(self):
        response = self.client.post(
            f"/api/businesses/{self.business_a_id}/reconciliation/run",
            headers=self.headers_a,
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["result_count"], 0)
        results = self.client.get(
            f"/api/businesses/{self.business_a_id}/reconciliation/results",
            params={"run_id": response.json()["run_id"]},
            headers=self.headers_a,
        )
        self.assertEqual(results.status_code, 200)
        self.assertEqual(results.json()["results"], [])

    def test_nonmember_cannot_run_or_read_results(self):
        for method, suffix in (("post", "run"), ("get", "results")):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    f"/api/businesses/{self.business_a_id}/reconciliation/{suffix}",
                    headers=self.headers_b,
                )
                self.assertEqual(response.status_code, 404)

    def test_revoked_member_cannot_run_or_read_results(self):
        for method, suffix in (("post", "run"), ("get", "results")):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    f"/api/businesses/{self.business_a_id}/reconciliation/{suffix}",
                    headers=self.headers_revoked,
                )
                self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user_cannot_run_or_read_results(self):
        for method, suffix in (("post", "run"), ("get", "results")):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    f"/api/businesses/{self.business_a_id}/reconciliation/{suffix}"
                )
                self.assertEqual(response.status_code, 401)

    def test_results_and_inputs_are_isolated_between_businesses(self):
        self.import_reconciliation_data(self.business_a_id, self.headers_a, payment_amount="100.00")
        self.import_reconciliation_data(self.business_b_id, self.headers_b, payment_amount="200.00")
        run_a = self.client.post(
            f"/api/businesses/{self.business_a_id}/reconciliation/run", headers=self.headers_a
        ).json()
        run_b = self.client.post(
            f"/api/businesses/{self.business_b_id}/reconciliation/run", headers=self.headers_b
        ).json()
        results_a = self.client.get(
            f"/api/businesses/{self.business_a_id}/reconciliation/results",
            params={"run_id": run_a["run_id"]}, headers=self.headers_a,
        ).json()["results"]
        results_b = self.client.get(
            f"/api/businesses/{self.business_b_id}/reconciliation/results",
            params={"run_id": run_b["run_id"]}, headers=self.headers_b,
        ).json()["results"]
        self.assertEqual(Decimal(next(r for r in results_a if r["payment_external_id"] == "p1")["payment_amount"]), Decimal("100.00"))
        self.assertEqual(Decimal(next(r for r in results_b if r["payment_external_id"] == "p1")["payment_amount"]), Decimal("200.00"))

        foreign_run = self.client.get(
            f"/api/businesses/{self.business_a_id}/reconciliation/results",
            params={"run_id": run_b["run_id"]}, headers=self.headers_a,
        )
        self.assertEqual(foreign_run.status_code, 404)
        cross_member = self.client.get(
            f"/api/businesses/{self.business_a_id}/reconciliation/results",
            params={"run_id": run_a["run_id"]}, headers=self.headers_b,
        )
        self.assertEqual(cross_member.status_code, 404)


if __name__ == "__main__":
    unittest.main()
