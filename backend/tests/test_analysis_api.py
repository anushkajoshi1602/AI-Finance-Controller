"""Business-scoped anomaly and cash-flow API tests on isolated resources."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import csv_import_routes
from backend.auth import create_access_token
from backend.db.database import Base, build_engine, get_db
from backend.db.models import Business, BusinessMembership, User
from backend.main import app


class AnalysisApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine("sqlite:///:memory:", poolclass=StaticPool)
        self.storage = tempfile.TemporaryDirectory()
        self.previous_storage_dir = csv_import_routes.STORAGE_DIR
        csv_import_routes.STORAGE_DIR = Path(self.storage.name)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            self.owner = User(email="analysis-owner@example.com", password_hash="test-hash")
            self.outsider = User(email="analysis-outsider@example.com", password_hash="test-hash")
            db.add_all([self.owner, self.outsider])
            db.flush()
            self.owner_id, self.outsider_id = self.owner.id, self.outsider.id
            self.business = Business(name="Analysis Workspace", slug="analysis-workspace")
            db.add(self.business)
            db.flush()
            self.business_id = self.business.id
            db.add(BusinessMembership(business_id=self.business_id, user_id=self.owner_id,
                                      role="owner", status="active"))
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
        self.owner_headers = {"Authorization": f"Bearer {create_access_token(self.owner_id)}"}
        self.outsider_headers = {"Authorization": f"Bearer {create_access_token(self.outsider_id)}"}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.previous_overrides)
        self.engine.dispose()
        csv_import_routes.STORAGE_DIR = self.previous_storage_dir
        self.storage.cleanup()

    def upload(self, dataset, data):
        response = self.client.post(
            f"/api/businesses/{self.business_id}/imports/{dataset}",
            files={"file": (f"{dataset}.csv", data, "text/csv")},
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["status"], "validated", response.text)

    def load_source_data(self):
        self.upload("customers", b"external_id,name,email\nc1,One,one@example.com\nc2,Two,two@example.com\n")
        self.upload(
            "payments",
            b"external_id,customer_external_id,amount,status,payment_date\np1,c1,100.00,Success,2025-01-01\np2,c2,50.00,Success,2025-01-01\n",
        )
        self.upload(
            "settlements",
            b"external_id,payment_external_id,gross_amount,refund_amount,fee,tax,net_amount\ns1,p1,100.00,0.00,5.00,0.00,94.00\n",
        )
        self.upload("bank_transactions", b"external_id,settlement_external_id,amount\nb1,s1,90.00\n")

    def run_reconciliation(self):
        response = self.client.post(
            f"/api/businesses/{self.business_id}/reconciliation/run", headers=self.owner_headers
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_anomaly_detection_persists_scoped_results(self):
        self.load_source_data()
        missing_prerequisite = self.client.post(
            f"/api/businesses/{self.business_id}/anomalies/run", headers=self.owner_headers
        )
        self.assertEqual(missing_prerequisite.status_code, 409)
        self.run_reconciliation()

        response = self.client.post(
            f"/api/businesses/{self.business_id}/anomalies/run", headers=self.owner_headers
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["result_count"], 2)
        results = self.client.get(
            f"/api/businesses/{self.business_id}/anomalies/results",
            params={"run_id": response.json()["run_id"]},
            headers=self.owner_headers,
        )
        self.assertEqual(results.status_code, 200, results.text)
        by_transaction = {row["transaction_external_id"]: row for row in results.json()["results"]}
        self.assertEqual(by_transaction["p1"]["anomaly_type"], "Mismatch")
        self.assertEqual(by_transaction["p1"]["amount_difference"], "1.00")
        self.assertEqual(by_transaction["p2"]["anomaly_type"], "Missing Settlement")

    def test_cash_flow_forecast_persists_seven_scoped_days(self):
        self.load_source_data()
        with patch("backend.cash_flow_service.datetime") as clock:
            clock.now.return_value = datetime(2025, 1, 10)
            response = self.client.post(
                f"/api/businesses/{self.business_id}/cash-flow/run", headers=self.owner_headers
            )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["result_count"], 7)
        results = self.client.get(
            f"/api/businesses/{self.business_id}/cash-flow/results",
            params={"run_id": response.json()["run_id"]},
            headers=self.owner_headers,
        )
        self.assertEqual(results.status_code, 200, results.text)
        rows = results.json()["results"]
        self.assertEqual(rows[0]["forecast_date"], "2025-01-11")
        self.assertEqual(rows[-1]["forecast_date"], "2025-01-17")
        self.assertEqual({row["predicted_cash_inflow"] for row in rows}, {"94.00"})

    def test_bank_reconciliation_matches_imported_statement_records(self):
        self.load_source_data()
        response = self.client.post(
            f"/api/businesses/{self.business_id}/bank-reconciliation/run", headers=self.owner_headers
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["result_count"], 1)
        results = self.client.get(
            f"/api/businesses/{self.business_id}/bank-reconciliation/results",
            params={"run_id": response.json()["run_id"]}, headers=self.owner_headers,
        )
        self.assertEqual(results.status_code, 200, results.text)
        rows = {row["settlement_id"]: row for row in results.json()["results"]}
        self.assertEqual(rows["s1"]["status"], "Amount Mismatch")
        self.assertEqual(rows["s1"]["difference"], "4.00")

    def test_anomaly_run_deduplicates_batches_shared_by_reconciliation_runs(self):
        self.load_source_data()
        self.run_reconciliation()
        bank_run = self.client.post(
            f"/api/businesses/{self.business_id}/bank-reconciliation/run",
            headers=self.owner_headers,
        )
        self.assertEqual(bank_run.status_code, 201, bank_run.text)
        response = self.client.post(
            f"/api/businesses/{self.business_id}/anomalies/run",
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["result_count"], 3)

    def test_anomaly_and_cash_flow_routes_require_active_business_membership(self):
        for path in ("anomalies/run", "anomalies/results", "cash-flow/run", "cash-flow/results"):
            with self.subTest(path=path, actor="unauthenticated"):
                response = self.client.get(f"/api/businesses/{self.business_id}/{path}") if path.endswith("results") else self.client.post(f"/api/businesses/{self.business_id}/{path}")
                self.assertEqual(response.status_code, 401)
            with self.subTest(path=path, actor="nonmember"):
                response = self.client.get(
                    f"/api/businesses/{self.business_id}/{path}", headers=self.outsider_headers
                ) if path.endswith("results") else self.client.post(
                    f"/api/businesses/{self.business_id}/{path}", headers=self.outsider_headers
                )
                self.assertEqual(response.status_code, 404)

    def test_source_ledgers_and_dashboard_are_business_scoped(self):
        self.load_source_data()
        payments = self.client.get(
            f"/api/businesses/{self.business_id}/ledger/payments", headers=self.owner_headers
        )
        self.assertEqual(payments.status_code, 200, payments.text)
        self.assertEqual({row["payment_id"] for row in payments.json()}, {"p1", "p2"})
        dashboard = self.client.get(
            f"/api/businesses/{self.business_id}/dashboard", headers=self.owner_headers
        )
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        self.assertEqual(dashboard.json()["total_payments"], 2)
        denied = self.client.get(
            f"/api/businesses/{self.business_id}/ledger/payments", headers=self.outsider_headers
        )
        self.assertEqual(denied.status_code, 404)


if __name__ == "__main__":
    unittest.main()
