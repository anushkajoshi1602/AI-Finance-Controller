"""Protected business-scoped anomaly detection API."""

from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.anomaly_service import run_anomaly_detection
from backend.business_routes import require_business_membership
from backend.db.database import get_db
from backend.db.models import Anomaly, BusinessMembership, FinancialRun, FinancialRunType

router = APIRouter(prefix="/api/businesses/{business_id}/anomalies", tags=["Anomalies"])


def _amount(value):
    return None if value is None else format(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


@router.post("/run", status_code=201)
def create_anomaly_run(
    business_id: str,
    membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    if membership.business_id != business_id:
        raise HTTPException(status_code=404, detail="Business not found")
    try:
        run, anomalies = run_anomaly_detection(business_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"business_id": business_id, "run_id": run.id, "status": run.status,
            "result_count": len(anomalies)}


@router.get("/results")
def get_anomaly_results(
    business_id: str,
    run_id: str | None = None,
    membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    if membership.business_id != business_id:
        raise HTTPException(status_code=404, detail="Business not found")
    statement = select(Anomaly).where(Anomaly.business_id == business_id)
    if run_id is None:
        latest = db.scalar(select(FinancialRun).where(
            FinancialRun.business_id == business_id,
            FinancialRun.run_type == FinancialRunType.ANOMALY_DETECTION.value,
            FinancialRun.status == "succeeded",
        ).order_by(FinancialRun.completed_at.desc(), FinancialRun.started_at.desc()))
        run_id = latest.id if latest else None
    if run_id is not None:
        exists = db.scalar(select(FinancialRun.id).where(
            FinancialRun.business_id == business_id,
            FinancialRun.id == run_id,
            FinancialRun.run_type == FinancialRunType.ANOMALY_DETECTION.value,
        ))
        if exists is None:
            raise HTTPException(status_code=404, detail="Anomaly run not found")
        statement = statement.where(Anomaly.run_id == run_id)
    else:
        return {"business_id": business_id, "run_id": None, "results": []}
    anomalies = db.scalars(statement.order_by(Anomaly.transaction_external_id)).all()
    return {"business_id": business_id, "run_id": run_id, "results": [
        {"id": row.id, "run_id": row.run_id,
         "reconciliation_result_id": row.reconciliation_result_id,
         "source": row.source, "transaction_external_id": row.transaction_external_id,
         "anomaly_type": row.anomaly_type, "amount_difference": _amount(row.amount_difference),
         "severity": row.severity}
        for row in anomalies
    ]}

