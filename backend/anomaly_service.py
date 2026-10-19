"""Business-scoped anomaly detection over persisted reconciliation results."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import (
    Anomaly,
    BankReconciliationResult,
    FinancialRun,
    FinancialRunImportBatch,
    FinancialRunStatus,
    FinancialRunType,
    ReconciliationResult,
)


def run_anomaly_detection(business_id: str, db: Session) -> tuple[FinancialRun, list[Anomaly]]:
    reconciliation_run = db.scalar(
        select(FinancialRun)
        .where(
            FinancialRun.business_id == business_id,
            FinancialRun.run_type == FinancialRunType.RECONCILIATION.value,
            FinancialRun.status == FinancialRunStatus.SUCCEEDED.value,
        )
        .order_by(FinancialRun.completed_at.desc(), FinancialRun.started_at.desc())
    )
    bank_run = db.scalar(select(FinancialRun).where(
        FinancialRun.business_id == business_id,
        FinancialRun.run_type == FinancialRunType.BANK_RECONCILIATION.value,
        FinancialRun.status == FinancialRunStatus.SUCCEEDED.value,
    ).order_by(FinancialRun.completed_at.desc(), FinancialRun.started_at.desc()))
    if reconciliation_run is None and bank_run is None:
        raise ValueError("Run payment or bank reconciliation before detecting anomalies")

    source_results = []
    if reconciliation_run is not None:
        source_results = db.scalars(
            select(ReconciliationResult).where(
            ReconciliationResult.business_id == business_id,
            ReconciliationResult.run_id == reconciliation_run.id,
            ReconciliationResult.status != "Matched",
            )
        ).all()
    bank_source_results = []
    if bank_run is not None:
        bank_source_results = db.scalars(select(BankReconciliationResult).where(
            BankReconciliationResult.business_id == business_id,
            BankReconciliationResult.run_id == bank_run.id,
            BankReconciliationResult.status != "Matched",
        )).all()
    input_run_ids = [run.id for run in (reconciliation_run, bank_run) if run is not None]
    input_batches = db.scalars(select(FinancialRunImportBatch).where(
            FinancialRunImportBatch.business_id == business_id,
            FinancialRunImportBatch.run_id.in_(input_run_ids),
    )).all()
    # The two prerequisite runs can share validated imports (especially the
    # settlements batch). A downstream run records each input batch once.
    input_batch_ids = {batch.import_batch_id for batch in input_batches}

    run = FinancialRun(
        business_id=business_id,
        run_type=FinancialRunType.ANOMALY_DETECTION.value,
        status=FinancialRunStatus.RUNNING.value,
    )
    db.add(run)
    db.flush()

    anomalies = [
        Anomaly(
            business_id=business_id,
            run_id=run.id,
            reconciliation_result_id=result.id,
            source="Payment Reconciliation",
            transaction_external_id=result.payment_external_id or result.settlement_external_id or "unknown",
            anomaly_type=result.status,
            amount_difference=result.difference,
            severity="High",
        )
        for result in source_results
    ]
    anomalies.extend(
        Anomaly(
            business_id=business_id,
            run_id=run.id,
            bank_reconciliation_result_id=result.id,
            source="Bank Reconciliation",
            transaction_external_id=result.bank_transaction_external_id or result.settlement_external_id or "unknown",
            anomaly_type=result.status,
            amount_difference=result.difference,
            severity="High",
        )
        for result in bank_source_results
    )
    db.add_all(anomalies)
    for batch_id in input_batch_ids:
        db.add(FinancialRunImportBatch(
            business_id=business_id,
            run_id=run.id,
            import_batch_id=batch_id,
        ))
    run.status = FinancialRunStatus.SUCCEEDED.value
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run, anomalies

