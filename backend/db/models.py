"""Identity and tenancy models (Stage 1).

    Tenancy rule for every later stage: a merchant-owned row carries a non-null
    ``business_id``, and access is granted only through an *active*
    ``BusinessMembership`` for the authenticated user — never because a client sent
    a business ID.
    """

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
        Boolean,
        CheckConstraint,
        DateTime,
        ForeignKey,
        Index,
        String,
        UniqueConstraint,
    )
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .database import Base


def _uuid() -> str:
        return str(uuid.uuid4())


def _utcnow() -> datetime:
        return datetime.now(timezone.utc)


class MembershipRole(str, enum.Enum):
        OWNER = "owner"
        ADMIN = "admin"
        ANALYST = "analyst"
        VIEWER = "viewer"


class MembershipStatus(str, enum.Enum):
        INVITED = "invited"
        ACTIVE = "active"
        REVOKED = "revoked"


def _in_list(column: str, values: list[str]) -> str:
        return f"{column} IN ({', '.join(repr(v) for v in values)})"


ROLE_VALUES = [r.value for r in MembershipRole]
STATUS_VALUES = [s.value for s in MembershipStatus]
BUSINESS_STATUS_VALUES = ["active", "suspended", "closed"]


class TimestampMixin:
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), default=_utcnow, nullable=False
        )
        updated_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
        )
class User(TimestampMixin, Base):
        __tablename__ = "users"

        # Random UUIDs: not enumerable, and portable across SQLite/PostgreSQL.
        id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
        # Stored lower-cased; uniqueness is therefore case-insensitive.
        email: Mapped[str] = mapped_column(String(320), nullable=False)
        # Hash only (e.g. argon2/bcrypt output). Plain passwords are never stored.
        password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
        full_name: Mapped[str | None] = mapped_column(String(200))
        is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
        email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
        last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

        memberships: Mapped[list["BusinessMembership"]] = relationship(
            back_populates="user",
            foreign_keys="BusinessMembership.user_id",
            cascade="all, delete-orphan",
            passive_deletes=True,
        )

        __table_args__ = (
            UniqueConstraint("email", name="uq_users_email"),
            CheckConstraint("length(password_hash) > 0", name="ck_users_password_hash_nonempty"),
        )

        @validates("email")
        def _normalize_email(self, _key: str, value: str) -> str:
            value = (value or "").strip().lower()
            if not value or "@" not in value:
                raise ValueError("A valid email address is required")
            return value

        def __repr__(self) -> str:  # never include password_hash
            return f"<User id={self.id} email={self.email!r}>"


class Business(TimestampMixin, Base):
        __tablename__ = "businesses"

        id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
        name: Mapped[str] = mapped_column(String(200), nullable=False)
        # URL-safe unique handle; lower-case letters, digits and hyphens.
        slug: Mapped[str] = mapped_column(String(100), nullable=False)
        legal_name: Mapped[str | None] = mapped_column(String(255))
        base_currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
        timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
        status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
        created_by_user_id: Mapped[str | None] = mapped_column(
            ForeignKey("users.id", ondelete="SET NULL")
        )

        memberships: Mapped[list["BusinessMembership"]] = relationship(
            back_populates="business",
            cascade="all, delete-orphan",
            passive_deletes=True,
        )

        __table_args__ = (
            UniqueConstraint("slug", name="uq_businesses_slug"),
            CheckConstraint("length(base_currency) = 3", name="ck_businesses_currency_len"),
            CheckConstraint(_in_list("status", BUSINESS_STATUS_VALUES), name="ck_businesses_status"),
            Index("ix_businesses_created_by_user_id", "created_by_user_id"),
        )

        @validates("slug")
        def _normalize_slug(self, _key: str, value: str) -> str:
            value = (value or "").strip().lower()
            if not value or not all(c.isalnum() or c == "-" for c in value):
                raise ValueError("Slug may contain only letters, digits and hyphens")
            return value

        @validates("base_currency")
        def _normalize_currency(self, _key: str, value: str) -> str:
            return (value or "").strip().upper()

        def __repr__(self) -> str:
            return f"<Business id={self.id} slug={self.slug!r}>"


class BusinessMembership(TimestampMixin, Base):
        """Authorises a user to act within one business, with a role."""

        __tablename__ = "business_memberships"

        id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
        business_id: Mapped[str] = mapped_column(
            ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
        )
        user_id: Mapped[str] = mapped_column(
            ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        )
        role: Mapped[str] = mapped_column(String(20), default=MembershipRole.VIEWER.value, nullable=False)
        status: Mapped[str] = mapped_column(
            String(20), default=MembershipStatus.ACTIVE.value, nullable=False
        )
        invited_by_user_id: Mapped[str | None] = mapped_column(
            ForeignKey("users.id", ondelete="SET NULL")
        )

        business: Mapped[Business] = relationship(back_populates="memberships")
        user: Mapped[User] = relationship(back_populates="memberships", foreign_keys=[user_id])

        __table_args__ = (
            # One membership row per (business, user).
            UniqueConstraint("business_id", "user_id", name="uq_membership_business_user"),
            CheckConstraint(_in_list("role", ROLE_VALUES), name="ck_membership_role"),
            CheckConstraint(_in_list("status", STATUS_VALUES), name="ck_membership_status"),
            # "Which businesses can this user access?" — the hot path for every request.
            Index("ix_membership_user_status", "user_id", "status"),
            Index("ix_membership_business_role", "business_id", "role"),
        )

        def __repr__(self) -> str:
            return (
                f"<BusinessMembership business={self.business_id} user={self.user_id} "
                f"role={self.role} status={self.status}>"
            )


# Import after identity models so all financial foreign keys resolve in metadata.
from .financial_models import (  # noqa: E402,F401
    Anomaly,
    BankReconciliationResult,
    BankTransaction,
    CashFlowForecast,
    Customer,
    FinancialRun,
    FinancialRunImportBatch,
    FinancialRunStatus,
    FinancialRunType,
    ImportBatch,
    ImportDatasetType,
    ImportValidationStatus,
    InvestigationResult,
    Payment,
    ReconciliationResult,
    Refund,
    Settlement,
)
