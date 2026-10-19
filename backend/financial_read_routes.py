"""Business-scoped source-ledger and dashboard reads for the existing UI."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.business_routes import require_business_membership
from backend.db.database import get_db
from backend.db.models import (
    Anomaly,
    BankTransaction,
    BusinessMembership,
    FinancialRun,
    ImportBatch,
    Payment,
    Refund,
    Settlement,
)

router = APIRouter(prefix="/api/businesses/{business_id}", tags=["Financial Data"])
LEDGER_MODELS = {
    "payments": (Payment, "payments"),
    "settlements": (Settlement, "settlements"),
    "refunds": (Refund, "refunds"),
    "bank-transactions": (BankTransaction, "bank_transactions"),
}


def _records(business_id: str, dataset: str, db: Session) -> list[dict]:
    model, batch_type = LEDGER_MODELS[dataset]
    batch_ids = db.scalars(select(ImportBatch.id).where(
        ImportBatch.business_id == business_id,
        ImportBatch.dataset_type == batch_type,
        ImportBatch.validation_status == "validated",
    )).all()
    if not batch_ids:
        return []
    rows = db.scalars(select(model).where(
        model.business_id == business_id,
        model.import_batch_id.in_(batch_ids),
    )).all()
    records = []
    for row in rows:
        item = {column.name: getattr(row, column.name) for column in model.__table__.columns
                if column.name not in {"id", "business_id", "import_batch_id"}}
        item[{
            "payments": "payment_id",
            "settlements": "settlement_id",
            "refunds": "refund_id",
            "bank-transactions": "transaction_id",
        }[dataset]] = item.pop("external_id")
        if "customer_external_id" in item:
            item["customer_id"] = item.pop("customer_external_id")
        if "payment_external_id" in item:
            item["payment_id"] = item.pop("payment_external_id")
        if "settlement_external_id" in item:
            item["settlement_id"] = item.pop("settlement_external_id")
        for key, value in item.items():
            if hasattr(value, "isoformat"):
                item[key] = value.isoformat()
            elif isinstance(value, Decimal):
                item[key] = format(value, ".2f")
        records.append(item)
    return records


@router.get("/ledger/{dataset}")
def get_business_ledger(
    business_id: str,
    dataset: str,
    _membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    if dataset not in LEDGER_MODELS:
        raise HTTPException(status_code=404, detail="Ledger not found")
    return _records(business_id, dataset, db)


@router.get("/dashboard")
def get_business_dashboard(
    business_id: str,
    _membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    payments = _records(business_id, "payments", db)
    settlements = _records(business_id, "settlements", db)
    refunds = _records(business_id, "refunds", db)
    latest_anomaly_run = db.scalar(select(FinancialRun).where(
        FinancialRun.business_id == business_id,
        FinancialRun.run_type == "anomaly_detection",
        FinancialRun.status == "succeeded",
    ).order_by(FinancialRun.completed_at.desc(), FinancialRun.started_at.desc()))
    anomaly_count = 0
    if latest_anomaly_run:
        anomaly_count = len(db.scalars(select(Anomaly.id).where(
            Anomaly.business_id == business_id,
            Anomaly.run_id == latest_anomaly_run.id,
        )).all())
    successful = [row for row in payments if row.get("status") == "Success"]
    return {
        "total_payments": len(payments),
        "successful_payments": len(successful),
        "total_payment_amount": format(sum((Decimal(row["amount"]) for row in successful), Decimal("0")), ".2f"),
        "total_refunds": format(sum((Decimal(row["refund_amount"]) for row in refunds), Decimal("0")), ".2f"),
        "total_settlements": format(sum((Decimal(row["net_amount"]) for row in settlements), Decimal("0")), ".2f"),
        "total_anomalies": anomaly_count,
    }

