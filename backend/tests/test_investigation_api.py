"""Isolated integration tests for the business-scoped Investigator workflow."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import csv_import_routes
from backend.auth import create_access_token
from backend.db.database import Base, build_engine, get_db
from backend.db.models import Anomaly, Business, BusinessMembership, FinancialRun, User
from backend.main import app


class InvestigatorApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine("sqlite:///:memory:", poolclass=StaticPool)
        self.storage = tempfile.TemporaryDirectory()
        self.old_storage = csv_import_routes.STORAGE_DIR
        csv_import_routes.STORAGE_DIR = Path(self.storage.name)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            owner = User(email="investigator-owner@example.com", password_hash="test-hash")
            outsider = User(email="investigator-outsider@example.com", password_hash="test-hash")
            db.add_all([owner, outsider])
            db.flush()
            business = Business(name="Investigation Workspace", slug="investigation-workspace")
            db.add(business)
            db.flush()
            db.add(BusinessMembership(business_id=business.id, user_id=owner.id,
                                      role="owner", status="active"))
            self.owner_id, self.outsider_id, self.business_id = owner.id, outsider.id, business.id
            db.commit()

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        self.old_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.owner_headers = {"Authorization": f"Bearer {create_access_token(self.owner_id)}"}
        self.outsider_headers = {"Authorization": f"Bearer {create_access_token(self.outsider_id)}"}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.old_overrides)
        self.engine.dispose()
        csv_import_routes.STORAGE_DIR = self.old_storage
        self.storage.cleanup()

    def upload(self, dataset, body):
        response = self.client.post(
            f"/api/businesses/{self.business_id}/imports/{dataset}",
            files={"file": (f"{dataset}.csv", body, "text/csv")},
            headers=self.owner_headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["status"], "validated", response.text)

    def prepare(self, bank_amount="90.00"):
        self.upload("customers", b"external_id,name,email\nc1,Customer One,one@example.com\nc2,Customer Two,two@example.com\n")
        self.upload("payments", b"external_id,customer_external_id,amount,status,payment_date\np1,c1,100.00,Success,2025-01-01\np2,c2,50.00,Success,2025-01-01\n")
        self.upload("settlements", b"external_id,payment_external_id,gross_amount,refund_amount,fee,tax,net_amount\ns1,p1,100.00,0.00,6.00,0.00,94.00\n")
        self.upload("bank_transactions", f"external_id,settlement_external_id,amount\nb1,s1,{bank_amount}\n".encode())
        for path in ("reconciliation/run", "bank-reconciliation/run", "anomalies/run"):
            response = self.client.post(f"/api/businesses/{self.business_id}/{path}", headers=self.owner_headers)
            self.assertEqual(response.status_code, 201, response.text)
            if path == "anomalies/run":
                self.assertGreater(response.json()["result_count"], 0, response.text)

    def run_report(self):
        return self.client.post(
            f"/api/businesses/{self.business_id}/investigations/run", headers=self.owner_headers
        )

    def reports(self):
        response = self.client.get(
            f"/api/businesses/{self.business_id}/investigations/results", headers=self.owner_headers
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_positive_bank_variance_is_grounded_and_fallback_is_labelled(self):
        self.prepare("90.00")
        with patch("backend.investigation_service._gemini_assessment", side_effect=RuntimeError("unavailable")):
            self.assertEqual(self.run_report().status_code, 201)
        bank = next(row for row in self.reports()["results"] if row["record"]["source"] == "Bank Reconciliation")
        self.assertEqual(bank["verified_evidence"]["settlement_amount"], "94.00")
        self.assertEqual(bank["verified_evidence"]["bank_amount"], "90.00")
        self.assertEqual(bank["verified_evidence"]["variance"], "4.00")
        self.assertEqual(bank["mode"], "rule_based_fallback")
        self.assertEqual(bank["likely_explanation"]["label"], "Hypothesis")
        self.assertIn("short credit", bank["likely_explanation"]["text"])

    def test_negative_bank_variance_uses_direction_aware_hypothesis(self):
        self.prepare("100.00")
        with patch("backend.investigation_service._gemini_assessment", side_effect=RuntimeError("unavailable")):
            self.run_report()
        bank = next(row for row in self.reports()["results"] if row["record"]["source"] == "Bank Reconciliation")
        self.assertEqual(bank["verified_evidence"]["variance"], "-6.00")
        self.assertIn("exceeds", bank["likely_explanation"]["text"])
        self.assertIn("hypothesis", bank["likely_explanation"]["text"])

    def test_missing_settlement_never_fabricates_amounts(self):
        self.prepare()
        with patch("backend.investigation_service._gemini_assessment", side_effect=RuntimeError("not configured")):
            self.run_report()
        missing = next(row for row in self.reports()["results"] if row["anomaly_type"] == "Missing Settlement")
        self.assertIsNone(missing["verified_evidence"]["actual_settlement"])
        self.assertIsNone(missing["verified_evidence"]["variance"])
        self.assertEqual(missing["confidence"]["level"], "Limited")
        self.assertEqual(missing["likely_explanation"]["label"], "Hypothesis")

    def test_allowlisted_gemini_response_is_marked_ai_assisted(self):
        self.prepare()
        with patch("backend.investigation_service._gemini_assessment", return_value="supported"):
            self.run_report()
        bank = next(row for row in self.reports()["results"] if row["record"]["source"] == "Bank Reconciliation")
        self.assertEqual(bank["mode"], "gemini_assisted")
        self.assertEqual(bank["verified_evidence"]["variance"], "4.00")

    def test_missing_linked_source_record_is_not_treated_as_verified_variance(self):
        self.prepare()
        with self.Session() as db:
            anomaly_run = db.query(FinancialRun).filter_by(
                business_id=self.business_id, run_type="anomaly_detection"
            ).one()
            db.add(Anomaly(business_id=self.business_id, run_id=anomaly_run.id,
                           source="Payment Reconciliation", transaction_external_id="orphan",
                           anomaly_type="Mismatch", amount_difference="1.23", severity="High"))
            db.commit()
        with patch("backend.investigation_service._gemini_assessment", side_effect=RuntimeError("unavailable")):
            self.run_report()
        item = next(row for row in self.reports()["results"] if row["record"]["external_id"] == "orphan")
        self.assertFalse(item["verified_evidence"]["record_found"])
        self.assertIsNone(item["verified_evidence"]["variance"])
        self.assertEqual(item["verified_evidence"]["anomaly_amount_difference"], "1.23")
        self.assertEqual(item["confidence"]["level"], "Limited")

    def test_idempotency_authentication_membership_and_tenant_scope(self):
        self.prepare()
        with patch("backend.investigation_service._gemini_assessment", side_effect=RuntimeError("unavailable")):
            first = self.run_report().json()
            second = self.run_report()
        self.assertEqual(second.status_code, 201, second.text)
        self.assertTrue(second.json()["reused"])
        self.assertEqual(first["run_id"], second.json()["run_id"])
        path = f"/api/businesses/{self.business_id}/investigations"
        self.assertEqual(self.client.get(path + "/results").status_code, 401)
        self.assertEqual(self.client.post(path + "/run").status_code, 401)
        self.assertEqual(self.client.get(path + "/results", headers=self.outsider_headers).status_code, 404)
        self.assertEqual(self.client.post(path + "/run", headers=self.outsider_headers).status_code, 404)
        with self.Session() as db:
            member = db.query(BusinessMembership).filter_by(business_id=self.business_id).one()
            member.status = "revoked"
            db.commit()
        self.assertEqual(self.client.get(path + "/results", headers=self.owner_headers).status_code, 404)

    def test_empty_read_and_missing_anomaly_run(self):
        self.assertEqual(self.reports()["results"], [])
        self.assertEqual(self.run_report().status_code, 409)


if __name__ == "__main__":
    unittest.main()
