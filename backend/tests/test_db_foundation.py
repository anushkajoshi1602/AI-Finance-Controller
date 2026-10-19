"""Stage 1 database foundation tests. Uses an in-memory DB; touches no real data.

Run from the project root:
    venv\\Scripts\\python.exe -m unittest discover -s backend\\tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from db import Base, Business, BusinessMembership, User  # noqa: E402
from db.database import build_engine  # noqa: E402


class DatabaseFoundationTest(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _user(self, email="owner@example.com"):
        u = User(email=email, password_hash="hash-placeholder")
        self.db.add(u)
        self.db.commit()
        return u

    def _business(self, slug="acme"):
        b = Business(name="Acme", slug=slug)
        self.db.add(b)
        self.db.commit()
        return b

    def test_tables_and_constraints_exist(self):
        insp = inspect(self.engine)
        self.assertTrue(
            {"users", "businesses", "business_memberships"}
            <= set(insp.get_table_names())
        )
        uniques = {u["name"] for u in insp.get_unique_constraints("business_memberships")}
        self.assertIn("uq_membership_business_user", uniques)
        indexes = {i["name"] for i in insp.get_indexes("business_memberships")}
        self.assertTrue({"ix_membership_user_status", "ix_membership_business_role"} <= indexes)
        fks = {fk["referred_table"] for fk in insp.get_foreign_keys("business_memberships")}
        self.assertEqual(fks, {"businesses", "users"})

    def test_foreign_keys_enforced(self):
        self.assertEqual(self.db.execute(text("PRAGMA foreign_keys")).scalar(), 1)
        self.db.add(BusinessMembership(business_id="missing", user_id="missing", role="viewer"))
        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_email_normalized_and_unique(self):
        u = self._user("  Owner@Example.COM ")
        self.assertEqual(u.email, "owner@example.com")
        self.db.add(User(email="OWNER@example.com", password_hash="x"))
        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_invalid_email_rejected(self):
        with self.assertRaises(ValueError):
            User(email="not-an-email", password_hash="x")

    def test_slug_unique(self):
        self._business("acme")
        self.db.add(Business(name="Other", slug="ACME"))
        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_membership_unique_per_business_user(self):
        u, b = self._user(), self._business()
        self.db.add(BusinessMembership(business_id=b.id, user_id=u.id, role="owner"))
        self.db.commit()
        self.db.add(BusinessMembership(business_id=b.id, user_id=u.id, role="viewer"))
        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_invalid_role_rejected(self):
        u, b = self._user(), self._business()
        self.db.add(BusinessMembership(business_id=b.id, user_id=u.id, role="superuser"))
        with self.assertRaises(IntegrityError):
            self.db.commit()

    def test_same_user_in_two_businesses(self):
        u = self._user()
        b1, b2 = self._business("one"), self._business("two")
        self.db.add_all([
            BusinessMembership(business_id=b1.id, user_id=u.id, role="owner"),
            BusinessMembership(business_id=b2.id, user_id=u.id, role="viewer"),
        ])
        self.db.commit()
        self.assertEqual(len(self.db.get(User, u.id).memberships), 2)

    def test_deleting_business_cascades_memberships(self):
        u, b = self._user(), self._business()
        self.db.add(BusinessMembership(business_id=b.id, user_id=u.id, role="owner"))
        self.db.commit()
        self.db.execute(text("DELETE FROM businesses WHERE id = :id"), {"id": b.id})
        self.db.commit()
        count = self.db.execute(text("SELECT COUNT(*) FROM business_memberships")).scalar()
        self.assertEqual(count, 0)

    def test_repr_hides_password_hash(self):
        u = self._user()
        self.assertNotIn("hash-placeholder", repr(u))


if __name__ == "__main__":
    unittest.main()
