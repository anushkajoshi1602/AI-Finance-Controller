"""Business workspace API tests using an isolated in-memory database."""

import unittest

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.auth import create_access_token, hash_password
from backend.db.database import Base, build_engine, get_db
from backend.db.models import (
    Business,
    BusinessMembership,
    MembershipRole,
    MembershipStatus,
    User,
)
from backend.main import app


class BusinessRoutesTest(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine("sqlite:///:memory:", poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            self.user = User(
                email="workspace-owner@example.com",
                password_hash=hash_password("isolated-test-password"),
                full_name="Workspace Owner",
            )
            db.add(self.user)
            db.commit()
            self.user_id = self.user.id
            self.other_user = User(
                email="workspace-member@example.com",
                password_hash=hash_password("another-isolated-password"),
                full_name="Workspace Member",
            )
            db.add(self.other_user)
            db.flush()
            self.other_user_id = self.other_user.id
            self.business = Business(
                name="Owner Workspace",
                slug="owner-workspace",
                created_by_user_id=self.user_id,
            )
            db.add(self.business)
            db.flush()
            self.business_id = self.business.id
            db.add(BusinessMembership(
                business_id=self.business_id,
                user_id=self.user_id,
                role=MembershipRole.OWNER.value,
                status=MembershipStatus.ACTIVE.value,
            ))
            db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.token = create_access_token(self.user_id)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_create_business_adds_active_owner_membership(self):
        response = self.client.post(
            "/api/businesses",
            json={"name": "Acme Finance"},
            headers={"Authorization": f"Bearer {self.token}"},
        )

        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(result["business"]["name"], "Acme Finance")
        self.assertEqual(result["business"]["slug"], "acme-finance")
        self.assertEqual(result["membership"]["user_id"], self.user_id)
        self.assertEqual(result["membership"]["role"], "owner")
        self.assertEqual(result["membership"]["status"], "active")
        self.assertNotIn("password_hash", response.text)

        with self.Session() as db:
            business = db.get(Business, result["business"]["id"])
            membership = db.get(BusinessMembership, result["membership"]["id"])
            self.assertIsNotNone(business)
            self.assertIsNotNone(membership)
            self.assertEqual(membership.business_id, business.id)
            self.assertEqual(membership.user_id, self.user_id)
            self.assertEqual(membership.role, "owner")
            self.assertEqual(membership.status, "active")

    def test_creation_requires_authentication(self):
        response = self.client.post("/api/businesses", json={"name": "Acme"})
        self.assertEqual(response.status_code, 401)
        with self.Session() as db:
            self.assertEqual(db.query(Business).count(), 1)
            self.assertEqual(db.query(BusinessMembership).count(), 1)

    def test_invalid_business_names_are_rejected(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        for payload in ({}, {"name": "   "}, {"name": "x" * 201}):
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/api/businesses", json=payload, headers=headers
                )
                self.assertEqual(response.status_code, 422)
        with self.Session() as db:
            self.assertEqual(db.query(Business).count(), 1)
            self.assertEqual(db.query(BusinessMembership).count(), 1)

    def test_owner_can_access_own_business(self):
        response = self.client.get(
            f"/api/businesses/{self.business_id}",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["business"]["id"], self.business_id)
        self.assertEqual(response.json()["membership"]["role"], "owner")

    def test_authenticated_user_can_list_only_active_businesses(self):
        response = self.client.get(
            "/api/businesses",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([row["id"] for row in response.json()], [self.business_id])
        self.assertEqual(self.client.get("/api/businesses").status_code, 401)

    def test_active_member_can_access_business(self):
        with self.Session() as db:
            db.add(BusinessMembership(
                business_id=self.business_id,
                user_id=self.other_user_id,
                role=MembershipRole.ANALYST.value,
                status=MembershipStatus.ACTIVE.value,
            ))
            db.commit()
        token = create_access_token(self.other_user_id)
        response = self.client.get(
            f"/api/businesses/{self.business_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["membership"]["role"], "analyst")

    def test_user_without_membership_cannot_access_business(self):
        token = create_access_token(self.other_user_id)
        response = self.client.get(
            f"/api/businesses/{self.business_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Business not found")

    def test_invited_and_revoked_memberships_cannot_access_business(self):
        for membership_status in (MembershipStatus.INVITED, MembershipStatus.REVOKED):
            with self.subTest(status=membership_status.value):
                with self.Session() as db:
                    db.add(BusinessMembership(
                        business_id=self.business_id,
                        user_id=self.other_user_id,
                        role=MembershipRole.VIEWER.value,
                        status=membership_status.value,
                    ))
                    db.commit()
                token = create_access_token(self.other_user_id)
                response = self.client.get(
                    f"/api/businesses/{self.business_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                self.assertEqual(response.status_code, 404)
                with self.Session() as db:
                    membership = db.query(BusinessMembership).filter_by(
                        business_id=self.business_id, user_id=self.other_user_id
                    ).one()
                    db.delete(membership)
                    db.commit()

    def test_business_detail_requires_authentication(self):
        response = self.client.get(f"/api/businesses/{self.business_id}")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
