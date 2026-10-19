"""Protected business-scoped cash-flow forecasting API."""

from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.business_routes import require_business_membership
from backend.cash_flow_service import run_cash_flow_forecast
from backend.db.database import get_db
from backend.db.models import BusinessMembership, CashFlowForecast, FinancialRun

router = APIRouter(prefix="/api/businesses/{business_id}/cash-flow", tags=["Cash Flow"])


def _amount(value):
    return format(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")


@router.post("/run", status_code=201)
def create_cash_flow_run(
    business_id: str,
    membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    if membership.business_id != business_id:
        raise HTTPException(status_code=404, detail="Business not found")
    run, forecasts = run_cash_flow_forecast(business_id, db)
    return {"business_id": business_id, "run_id": run.id, "status": run.status,
            "result_count": len(forecasts)}


@router.get("/results")
def get_cash_flow_results(
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
            FinancialRun.run_type == "cash_flow_forecast",
            FinancialRun.status == "succeeded",
        ).order_by(FinancialRun.completed_at.desc(), FinancialRun.started_at.desc()))
        run_id = latest.id if latest else None
    else:
        run = db.scalar(select(FinancialRun).where(
            FinancialRun.business_id == business_id,
            FinancialRun.id == run_id,
            FinancialRun.run_type == "cash_flow_forecast",
        ))
        if run is None:
            raise HTTPException(status_code=404, detail="Forecast run not found")
    if run_id is None:
        return {"business_id": business_id, "run_id": None, "results": []}
    forecasts = db.scalars(select(CashFlowForecast).where(
        CashFlowForecast.business_id == business_id,
        CashFlowForecast.run_id == run_id,
    ).order_by(CashFlowForecast.forecast_date)).all()
    return {"business_id": business_id, "run_id": run_id, "results": [
        {"forecast_date": row.forecast_date.isoformat(),
         "predicted_cash_inflow": _amount(row.predicted_cash_inflow)}
        for row in forecasts
    ]}

