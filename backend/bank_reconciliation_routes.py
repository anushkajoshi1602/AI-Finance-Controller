"""Protected business-scoped bank reconciliation API."""

from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.bank_reconciliation_service import run_bank_reconciliation
from backend.business_routes import require_business_membership
from backend.db.database import get_db
from backend.db.models import BankReconciliationResult, BusinessMembership, FinancialRun

router = APIRouter(prefix="/api/businesses/{business_id}/bank-reconciliation", tags=["Bank Reconciliation"])


def _amount(value):
    return None if value is None else format(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


@router.post("/run", status_code=201)
def create_bank_reconciliation_run(
    business_id: str,
    membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    if membership.business_id != business_id:
        raise HTTPException(status_code=404, detail="Business not found")
    run, results = run_bank_reconciliation(business_id, db)
    return {"business_id": business_id, "run_id": run.id, "status": run.status,
            "result_count": len(results)}


@router.get("/results")
def get_bank_reconciliation_results(
    business_id: str,
    run_id: str | None = None,
    membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    if membership.business_id != business_id:
        raise HTTPException(status_code=404, detail="Business not found")
    if run_id is None:
        run = db.scalar(select(FinancialRun).where(
            FinancialRun.business_id == business_id,
            FinancialRun.run_type == "bank_reconciliation",
            FinancialRun.status == "succeeded",
        ).order_by(FinancialRun.completed_at.desc(), FinancialRun.started_at.desc()))
        run_id = run.id if run else None
    else:
        run = db.scalar(select(FinancialRun.id).where(
            FinancialRun.business_id == business_id,
            FinancialRun.id == run_id,
            FinancialRun.run_type == "bank_reconciliation",
        ))
        if run is None:
            raise HTTPException(status_code=404, detail="Bank reconciliation run not found")
    if run_id is None:
        return {"business_id": business_id, "run_id": None, "results": []}
    rows = db.scalars(select(BankReconciliationResult).where(
        BankReconciliationResult.business_id == business_id,
        BankReconciliationResult.run_id == run_id,
    ).order_by(BankReconciliationResult.settlement_external_id)).all()
    return {"business_id": business_id, "run_id": run_id, "results": [
        {"settlement_id": row.settlement_external_id,
         "bank_transaction_id": row.bank_transaction_external_id,
         "settlement_amount": _amount(row.settlement_amount),
         "bank_amount": _amount(row.bank_amount),
         "difference": _amount(row.difference), "status": row.status}
        for row in rows
    ]}

