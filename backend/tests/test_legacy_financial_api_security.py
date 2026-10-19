"""Legacy financial endpoints fail closed until they are business-scoped."""

import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import main
from backend.auth import create_access_token
from backend.db.database import Base, build_engine, get_db
from backend.db.models import User


LEGACY_GET_ENDPOINTS = (
    "/api/dashboard",
    "/api/payments",
    "/api/settlements",
    "/api/refunds",
    "/api/reconciliation",
    "/api/bank-reconciliation",
    "/api/anomalies",
    "/api/investigations",
    "/api/cash-flow-forecast",
)
LEGACY_POST_ENDPOINTS = (
    "/api/run-reconciliation",
    "/api/run-full-analysis",
)


class LegacyFinancialApiSecurityTest(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine("sqlite:///:memory:", poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            user = User(email="legacy-api-test@example.com", password_hash="test-hash")
            db.add(user)
            db.commit()
            self.token = create_access_token(user.id)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app_overrides = main.app.dependency_overrides
        self.previous_overrides = app_overrides.copy()
        app_overrides[get_db] = override_get_db
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(self.previous_overrides)
        self.engine.dispose()

    @staticmethod
    def _csv_snapshot():
        data_dir = Path(main.DATA_DIR)
        return {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in data_dir.glob("*.csv")
        }

    def test_legacy_get_endpoints_reject_unauthenticated_requests(self):
        with patch("backend.main.load_csv") as load_csv:
            for endpoint in LEGACY_GET_ENDPOINTS:
                with self.subTest(endpoint=endpoint):
                    response = self.client.get(endpoint)
                    self.assertEqual(response.status_code, 401, response.text)
            load_csv.assert_not_called()

    def test_legacy_post_endpoints_reject_without_running_or_changing_csvs(self):
        before = self._csv_snapshot()
        with patch("backend.main.subprocess.run") as run_process:
            for endpoint in LEGACY_POST_ENDPOINTS:
                with self.subTest(endpoint=endpoint):
                    response = self.client.post(endpoint)
                    self.assertEqual(response.status_code, 401, response.text)
            run_process.assert_not_called()
        self.assertEqual(self._csv_snapshot(), before)

    def test_authenticated_users_are_denied_until_data_is_business_scoped(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        before = self._csv_snapshot()
        with patch("backend.main.load_csv") as load_csv, patch(
            "backend.main.subprocess.run"
        ) as run_process:
            for endpoint in LEGACY_GET_ENDPOINTS:
                with self.subTest(method="GET", endpoint=endpoint):
                    response = self.client.get(endpoint, headers=headers)
                    self.assertEqual(response.status_code, 503, response.text)
            for endpoint in LEGACY_POST_ENDPOINTS:
                with self.subTest(method="POST", endpoint=endpoint):
                    response = self.client.post(endpoint, headers=headers)
                    self.assertEqual(response.status_code, 503, response.text)
            load_csv.assert_not_called()
            run_process.assert_not_called()
        self.assertEqual(self._csv_snapshot(), before)

    def test_vite_fallback_origin_can_preflight_auth_requests(self):
        origins = (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
        )
        for origin in origins:
            with self.subTest(origin=origin):
                response = self.client.options(
                    "/api/auth/login",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers.get("access-control-allow-origin"), origin)


if __name__ == "__main__":
    unittest.main()
