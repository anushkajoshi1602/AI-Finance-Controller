"""Business-scoped seven-day cash-flow forecast from validated relational imports."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import (
    CashFlowForecast,
    FinancialRun,
    FinancialRunImportBatch,
    ImportBatch,
    Payment,
    Settlement,
)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def run_cash_flow_forecast(business_id: str, db: Session) -> tuple[FinancialRun, list[CashFlowForecast]]:
    batches = db.scalars(select(ImportBatch).where(
        ImportBatch.business_id == business_id,
        ImportBatch.validation_status == "validated",
        ImportBatch.dataset_type.in_(("payments", "settlements")),
    )).all()
    batch_ids = {"payments": [], "settlements": []}
    for batch in batches:
        batch_ids[batch.dataset_type].append(batch.id)

    def load_rows(model, dataset_type):
        if not batch_ids[dataset_type]:
            return []
        return db.scalars(select(model).where(
            model.business_id == business_id,
            model.import_batch_id.in_(batch_ids[dataset_type]),
        )).all()

    payments = load_rows(Payment, "payments")
    settlements = load_rows(Settlement, "settlements")
    payments_by_external = {row.external_id: row for row in payments}
    settlements_by_payment = defaultdict(list)
    for settlement in settlements:
        settlements_by_payment[settlement.payment_external_id].append(settlement)

    daily_totals = defaultdict(lambda: ZERO)
    for payment in payments:
        if payment.status != "Success" or payment.payment_date is None:
            continue
        for settlement in settlements_by_payment[payment.external_id]:
            day = payment.payment_date.date()
            daily_totals[day] += Decimal(settlement.net_amount).quantize(CENT, rounding=ROUND_HALF_UP)

    forecasts = []
    if daily_totals:
        average_inflow = (sum(daily_totals.values(), ZERO) / Decimal(len(daily_totals))).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        today = datetime.now(timezone.utc).date()
        forecast_days = [today + timedelta(days=offset) for offset in range(1, 8)]
    else:
        average_inflow = ZERO
        forecast_days = []

    run = FinancialRun(business_id=business_id, run_type="cash_flow_forecast", status="running")
    db.add(run)
    db.flush()
    forecasts = [CashFlowForecast(
        business_id=business_id,
        run_id=run.id,
        forecast_date=forecast_day,
        predicted_cash_inflow=average_inflow,
    ) for forecast_day in forecast_days]
    db.add_all(forecasts)
    for batch in batches:
        db.add(FinancialRunImportBatch(
            business_id=business_id,
            run_id=run.id,
            import_batch_id=batch.id,
        ))
    run.status = "succeeded"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run, forecasts

