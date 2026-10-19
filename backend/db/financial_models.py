"""Business-scoped financial records and import/run provenance.

Source IDs are scoped to a business. Composite foreign keys ensure that related
records cannot refer across businesses even if two merchants reuse the same ID.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImportDatasetType(str, enum.Enum):
    CUSTOMERS = "customers"
    PAYMENTS = "payments"
    REFUNDS = "refunds"
    SETTLEMENTS = "settlements"
    BANK_TRANSACTIONS = "bank_transactions"


class ImportValidationStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    VALIDATED = "validated"
    FAILED = "failed"


class FinancialRunType(str, enum.Enum):
    RECONCILIATION = "reconciliation"
    BANK_RECONCILIATION = "bank_reconciliation"
    ANOMALY_DETECTION = "anomaly_detection"
    INVESTIGATION = "investigation"
    CASH_FLOW_FORECAST = "cash_flow_forecast"


class FinancialRunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    dataset_type: Mapped[str] = mapped_column(String(40), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        String(20), default=ImportValidationStatus.UPLOADED.value, nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_errors: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("business_id", "id", name="uq_import_batches_business_id_id"),
        UniqueConstraint(
            "business_id", "dataset_type", "content_hash",
            name="uq_import_batches_business_dataset_hash",
        ),
        CheckConstraint(
            "dataset_type IN ('customers', 'payments', 'refunds', 'settlements', 'bank_transactions')",
            name="ck_import_batches_dataset_type",
        ),
        CheckConstraint(
            "validation_status IN ('uploaded', 'validating', 'validated', 'failed')",
            name="ck_import_batches_validation_status",
        ),
        Index("ix_import_batches_business_uploaded", "business_id", "uploaded_at"),
    )


class FinancialRun(Base):
    __tablename__ = "financial_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    run_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=FinancialRunStatus.RUNNING.value, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_summary: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("business_id", "id", name="uq_financial_runs_business_id_id"),
        CheckConstraint(
            "run_type IN ('reconciliation', 'bank_reconciliation', 'anomaly_detection', 'investigation', 'cash_flow_forecast')",
            name="ck_financial_runs_type",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_financial_runs_status",
        ),
        Index("ix_financial_runs_business_started", "business_id", "started_at"),
    )


class FinancialRunImportBatch(Base):
    """Input batches used by a run, preserving reproducible provenance."""

    __tablename__ = "financial_run_import_batches"

    business_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    import_batch_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "run_id"],
            ["financial_runs.business_id", "financial_runs.id"],
            ondelete="CASCADE",
            name="fk_run_batches_run_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "import_batch_id"],
            ["import_batches.business_id", "import_batches.id"],
            ondelete="CASCADE",
            name="fk_run_batches_import_business",
        ),
        Index("ix_run_batches_import", "business_id", "import_batch_id"),
    )


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    import_batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))

    __table_args__ = (
        ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["business_id", "import_batch_id"],
            ["import_batches.business_id", "import_batches.id"],
            name="fk_customers_import_business",
        ),
        UniqueConstraint("business_id", "id", name="uq_customers_business_id_id"),
        UniqueConstraint("business_id", "external_id", name="uq_customers_business_external"),
        Index("ix_customers_import_batch", "business_id", "import_batch_id"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    import_batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_external_id: Mapped[str | None] = mapped_column(String(255))
    payment_method: Mapped[str | None] = mapped_column(String(80))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    payment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["business_id", "import_batch_id"],
            ["import_batches.business_id", "import_batches.id"],
            name="fk_payments_import_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "customer_external_id"],
            ["customers.business_id", "customers.external_id"],
            name="fk_payments_customer_business",
        ),
        UniqueConstraint("business_id", "id", name="uq_payments_business_id_id"),
        UniqueConstraint("business_id", "external_id", name="uq_payments_business_external"),
        Index("ix_payments_import_batch", "business_id", "import_batch_id"),
    )


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    import_batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    refund_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["business_id", "import_batch_id"],
            ["import_batches.business_id", "import_batches.id"],
            name="fk_refunds_import_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "payment_external_id"],
            ["payments.business_id", "payments.external_id"],
            name="fk_refunds_payment_business",
        ),
        UniqueConstraint("business_id", "id", name="uq_refunds_business_id_id"),
        UniqueConstraint("business_id", "external_id", name="uq_refunds_business_external"),
        Index("ix_refunds_import_batch", "business_id", "import_batch_id"),
    )


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    import_batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["business_id", "import_batch_id"],
            ["import_batches.business_id", "import_batches.id"],
            name="fk_settlements_import_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "payment_external_id"],
            ["payments.business_id", "payments.external_id"],
            name="fk_settlements_payment_business",
        ),
        UniqueConstraint("business_id", "id", name="uq_settlements_business_id_id"),
        UniqueConstraint("business_id", "external_id", name="uq_settlements_business_external"),
        Index("ix_settlements_import_batch", "business_id", "import_batch_id"),
    )


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    import_batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    settlement_external_id: Mapped[str | None] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    transaction_type: Mapped[str | None] = mapped_column(String(40))
    transaction_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["business_id", "import_batch_id"],
            ["import_batches.business_id", "import_batches.id"],
            name="fk_bank_transactions_import_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "settlement_external_id"],
            ["settlements.business_id", "settlements.external_id"],
            name="fk_bank_transactions_settlement_business",
        ),
        UniqueConstraint("business_id", "id", name="uq_bank_transactions_business_id_id"),
        UniqueConstraint("business_id", "external_id", name="uq_bank_transactions_business_external"),
        Index("ix_bank_transactions_import_batch", "business_id", "import_batch_id"),
    )


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payment_external_id: Mapped[str | None] = mapped_column(String(255))
    settlement_external_id: Mapped[str | None] = mapped_column(String(255))
    payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    refund_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    expected_settlement: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    actual_settlement: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["business_id", "run_id"], ["financial_runs.business_id", "financial_runs.id"],
            name="fk_reconciliation_results_run_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "payment_external_id"], ["payments.business_id", "payments.external_id"],
            name="fk_reconciliation_results_payment_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "settlement_external_id"],
            ["settlements.business_id", "settlements.external_id"],
            name="fk_reconciliation_results_settlement_business",
        ),
        UniqueConstraint("business_id", "id", name="uq_reconciliation_results_business_id_id"),
        Index("ix_reconciliation_results_run", "business_id", "run_id"),
    )


class BankReconciliationResult(Base):
    __tablename__ = "bank_reconciliation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    settlement_external_id: Mapped[str | None] = mapped_column(String(255))
    bank_transaction_external_id: Mapped[str | None] = mapped_column(String(255))
    settlement_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    bank_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["business_id", "run_id"], ["financial_runs.business_id", "financial_runs.id"],
            name="fk_bank_reconciliation_results_run_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "settlement_external_id"],
            ["settlements.business_id", "settlements.external_id"],
            name="fk_bank_reconciliation_results_settlement_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "bank_transaction_external_id"],
            ["bank_transactions.business_id", "bank_transactions.external_id"],
            name="fk_bank_reconciliation_results_bank_business",
        ),
        UniqueConstraint("business_id", "id", name="uq_bank_reconciliation_results_business_id_id"),
        Index("ix_bank_reconciliation_results_run", "business_id", "run_id"),
    )


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reconciliation_result_id: Mapped[str | None] = mapped_column(String(36))
    bank_reconciliation_result_id: Mapped[str | None] = mapped_column(String(36))
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    transaction_external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(80), nullable=False)
    amount_difference: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["business_id", "run_id"], ["financial_runs.business_id", "financial_runs.id"],
            name="fk_anomalies_run_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "reconciliation_result_id"],
            ["reconciliation_results.business_id", "reconciliation_results.id"],
            name="fk_anomalies_reconciliation_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "bank_reconciliation_result_id"],
            ["bank_reconciliation_results.business_id", "bank_reconciliation_results.id"],
            name="fk_anomalies_bank_reconciliation_business",
        ),
        UniqueConstraint("business_id", "id", name="uq_anomalies_business_id_id"),
        Index("ix_anomalies_run", "business_id", "run_id"),
    )


class InvestigationResult(Base):
    __tablename__ = "investigation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    anomaly_id: Mapped[str] = mapped_column(String(36), nullable=False)
    investigation_text: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["business_id", "run_id"], ["financial_runs.business_id", "financial_runs.id"],
            name="fk_investigations_run_business",
        ),
        ForeignKeyConstraint(
            ["business_id", "anomaly_id"], ["anomalies.business_id", "anomalies.id"],
            name="fk_investigations_anomaly_business",
        ),
        UniqueConstraint("business_id", "id", name="uq_investigations_business_id_id"),
        Index("ix_investigations_run", "business_id", "run_id"),
    )


class CashFlowForecast(Base):
    __tablename__ = "cash_flow_forecasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_cash_inflow: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["business_id", "run_id"], ["financial_runs.business_id", "financial_runs.id"],
            name="fk_cash_flow_forecasts_run_business",
        ),
        UniqueConstraint("business_id", "id", name="uq_cash_flow_forecasts_business_id_id"),
        UniqueConstraint("business_id", "run_id", "forecast_date", name="uq_forecast_run_date"),
        Index("ix_cash_flow_forecasts_run", "business_id", "run_id"),
    )

