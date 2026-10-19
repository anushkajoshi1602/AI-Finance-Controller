"""Protected business-scoped reconciliation API."""

from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.business_routes import require_business_membership
from backend.db.database import get_db
from backend.db.models import (
    BusinessMembership,
    FinancialRun,
    ReconciliationResult,
)
from backend.reconciliation_service import run_reconciliation

router = APIRouter(prefix="/api/businesses/{business_id}/reconciliation", tags=["Reconciliation"])
CENT = Decimal("0.01")


def _response_money(value):
    if value is None:
        return None
    return format(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP), ".2f")


def _result_payload(result: ReconciliationResult) -> dict:
    return {
        "id": result.id,
        "run_id": result.run_id,
        "payment_external_id": result.payment_external_id,
        "settlement_external_id": result.settlement_external_id,
        "payment_amount": _response_money(result.payment_amount),
        "refund_amount": _response_money(result.refund_amount),
        "expected_settlement": _response_money(result.expected_settlement),
        "actual_settlement": _response_money(result.actual_settlement),
        "difference": _response_money(result.difference),
        "status": result.status,
    }


@router.post("/run", status_code=201)
def create_reconciliation_run(
    business_id: str,
    membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    if membership.business_id != business_id:
        raise HTTPException(status_code=404, detail="Business not found")
    run, results = run_reconciliation(business_id, db)
    return {
        "business_id": business_id,
        "run_id": run.id,
        "status": run.status,
        "result_count": len(results),
    }


@router.get("/results")
def get_reconciliation_results(
    business_id: str,
    run_id: str | None = None,
    membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    if membership.business_id != business_id:
        raise HTTPException(status_code=404, detail="Business not found")
    if run_id is None:
        latest = db.scalar(select(FinancialRun).where(
            FinancialRun.business_id == business_id,
            FinancialRun.run_type == "reconciliation",
            FinancialRun.status == "succeeded",
        ).order_by(FinancialRun.completed_at.desc(), FinancialRun.started_at.desc()))
        run_id = latest.id if latest else None
    statement = select(ReconciliationResult).where(
        ReconciliationResult.business_id == business_id
    )
    if run_id is not None:
        run_exists = db.scalar(select(FinancialRun.id).where(
            FinancialRun.business_id == business_id,
            FinancialRun.id == run_id,
        ))
        if run_exists is None:
            raise HTTPException(status_code=404, detail="Reconciliation run not found")
        statement = statement.where(ReconciliationResult.run_id == run_id)
    else:
        return {"business_id": business_id, "run_id": None, "results": []}
    statement = statement.order_by(
        ReconciliationResult.payment_external_id,
        ReconciliationResult.settlement_external_id,
    )
    results = db.scalars(statement).all()
    return {
        "business_id": business_id,
        "run_id": run_id,
        "results": [_result_payload(result) for result in results],
    }

