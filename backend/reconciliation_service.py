"""Business-scoped reconciliation over validated relational imports."""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import (
    FinancialRun,
    FinancialRunImportBatch,
    ImportBatch,
    Payment,
    ReconciliationResult,
    Refund,
    Settlement,
)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def _money(value) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def run_reconciliation(business_id: str, db: Session) -> tuple[FinancialRun, list[ReconciliationResult]]:
    """Reconcile one business using only its validated payment/refund/settlement imports."""
    batches = db.scalars(
        select(ImportBatch).where(
            ImportBatch.business_id == business_id,
            ImportBatch.validation_status == "validated",
            ImportBatch.dataset_type.in_(("payments", "refunds", "settlements")),
        )
    ).all()
    batch_ids_by_type = defaultdict(list)
    for batch in batches:
        batch_ids_by_type[batch.dataset_type].append(batch.id)

    def load_rows(model, dataset_type):
        batch_ids = batch_ids_by_type[dataset_type]
        if not batch_ids:
            return []
        return db.scalars(
            select(model).where(
                model.business_id == business_id,
                model.import_batch_id.in_(batch_ids),
            )
        ).all()

    payments = load_rows(Payment, "payments")
    refunds = load_rows(Refund, "refunds")
    settlements = load_rows(Settlement, "settlements")

    payment_by_external_id = {payment.external_id: payment for payment in payments}
    refunds_by_payment = defaultdict(lambda: ZERO)
    for refund in refunds:
        refunds_by_payment[refund.payment_external_id] += _money(refund.refund_amount)

    settlements_by_payment = defaultdict(list)
    for settlement in settlements:
        settlements_by_payment[settlement.payment_external_id].append(settlement)

    run = FinancialRun(
        business_id=business_id,
        run_type="reconciliation",
        status="running",
    )
    db.add(run)
    db.flush()

    results = []
    for settlement in sorted(settlements, key=lambda row: (row.payment_external_id, row.external_id)):
        payment = payment_by_external_id.get(settlement.payment_external_id)
        if payment is None:
            # The composite foreign key should make this impossible with FK checks enabled.
            continue
        refund_amount = refunds_by_payment[payment.external_id]
        payment_amount = _money(payment.amount)
        expected = _money(payment_amount - refund_amount - _money(settlement.fee) - _money(settlement.tax))
        actual = _money(settlement.net_amount)
        difference = _money(expected - actual)
        results.append(ReconciliationResult(
            business_id=business_id,
            run_id=run.id,
            payment_external_id=payment.external_id,
            settlement_external_id=settlement.external_id,
            payment_amount=payment_amount,
            refund_amount=refund_amount,
            expected_settlement=expected,
            actual_settlement=actual,
            difference=difference,
            status="Matched" if abs(difference) < CENT else "Mismatch",
        ))

    for payment in sorted(payments, key=lambda row: row.external_id):
        if payment.status == "Success" and not settlements_by_payment[payment.external_id]:
            results.append(ReconciliationResult(
                business_id=business_id,
                run_id=run.id,
                payment_external_id=payment.external_id,
                settlement_external_id=None,
                payment_amount=_money(payment.amount),
                refund_amount=refunds_by_payment[payment.external_id],
                expected_settlement=None,
                actual_settlement=None,
                difference=None,
                status="Missing Settlement",
            ))

    db.add_all(results)
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
    return run, results

