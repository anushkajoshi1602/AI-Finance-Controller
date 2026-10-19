"""Business-scoped settlement-to-bank matching over validated imports."""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import (
    BankReconciliationResult,
    BankTransaction,
    FinancialRun,
    FinancialRunImportBatch,
    ImportBatch,
    Settlement,
)

CENT = Decimal("0.01")


def _money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def run_bank_reconciliation(business_id: str, db: Session):
    batches = db.scalars(select(ImportBatch).where(
        ImportBatch.business_id == business_id,
        ImportBatch.validation_status == "validated",
        ImportBatch.dataset_type.in_(("settlements", "bank_transactions")),
    )).all()
    batch_ids = {"settlements": [], "bank_transactions": []}
    for batch in batches:
        batch_ids[batch.dataset_type].append(batch.id)

    def load_rows(model, dataset):
        if not batch_ids[dataset]:
            return []
        return db.scalars(select(model).where(
            model.business_id == business_id,
            model.import_batch_id.in_(batch_ids[dataset]),
        )).all()

    settlements = load_rows(Settlement, "settlements")
    transactions = load_rows(BankTransaction, "bank_transactions")
    transactions_by_settlement = defaultdict(list)
    for row in transactions:
        if row.settlement_external_id:
            transactions_by_settlement[row.settlement_external_id].append(row)

    run = FinancialRun(business_id=business_id, run_type="bank_reconciliation", status="running")
    db.add(run)
    db.flush()
    results = []
    matched_transaction_ids = set()
    for settlement in settlements:
        linked = transactions_by_settlement[settlement.external_id]
        if not linked:
            results.append(BankReconciliationResult(
                business_id=business_id, run_id=run.id,
                settlement_external_id=settlement.external_id,
                settlement_amount=_money(settlement.net_amount),
                bank_amount=None, difference=None, status="Missing Bank Transaction",
            ))
            continue
        for transaction in linked:
            matched_transaction_ids.add(transaction.id)
            difference = _money(_money(settlement.net_amount) - _money(transaction.amount))
            results.append(BankReconciliationResult(
                business_id=business_id, run_id=run.id,
                settlement_external_id=settlement.external_id,
                bank_transaction_external_id=transaction.external_id,
                settlement_amount=_money(settlement.net_amount),
                bank_amount=_money(transaction.amount), difference=difference,
                status="Matched" if abs(difference) < CENT else "Amount Mismatch",
            ))
    for transaction in transactions:
        if transaction.id not in matched_transaction_ids and not transaction.settlement_external_id:
            results.append(BankReconciliationResult(
                business_id=business_id, run_id=run.id,
                settlement_external_id=None,
                bank_transaction_external_id=transaction.external_id,
                settlement_amount=None, bank_amount=_money(transaction.amount),
                difference=None, status="Unmatched Bank Transaction",
            ))
    db.add_all(results)
    for batch in batches:
        db.add(FinancialRunImportBatch(
            business_id=business_id, run_id=run.id, import_batch_id=batch.id,
        ))
    run.status = "succeeded"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run, results

