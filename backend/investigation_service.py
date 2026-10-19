"""Evidence-grounded business-scoped anomaly investigations."""

import json
import os
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import (
    Anomaly, BankReconciliationResult, FinancialRun, FinancialRunImportBatch,
    FinancialRunStatus, FinancialRunType, InvestigationResult, ReconciliationResult,
)

MODEL_DEFAULT = "gemini-3.8-flash"  # Existing integration model; override with GEMINI_MODEL.


def _money(value):
    return None if value is None else format(Decimal(value), ".2f")


def _evidence_for(anomaly, db):
    """Fetch only the linked source row and always constrain it to this tenant."""
    if anomaly.bank_reconciliation_result_id:
        row = db.scalar(select(BankReconciliationResult).where(
            BankReconciliationResult.business_id == anomaly.business_id,
            BankReconciliationResult.id == anomaly.bank_reconciliation_result_id,
        ))
        if row is None:
            return {"source": anomaly.source, "source_record_id": anomaly.bank_reconciliation_result_id,
                    "record_found": False, "status": None, "settlement_id": None,
                    "bank_transaction_id": None, "settlement_amount": None, "bank_amount": None,
                    "variance": None, "variance_convention": "settlement_amount - bank_amount"}
        return {"source": anomaly.source, "source_record_id": row.id, "record_found": True,
                "status": row.status, "settlement_id": row.settlement_external_id,
                "bank_transaction_id": row.bank_transaction_external_id,
                "settlement_amount": _money(row.settlement_amount), "bank_amount": _money(row.bank_amount),
                "variance": _money(row.difference),
                "variance_convention": "settlement_amount - bank_amount; positive means bank credit is lower"}
    if anomaly.reconciliation_result_id:
        row = db.scalar(select(ReconciliationResult).where(
            ReconciliationResult.business_id == anomaly.business_id,
            ReconciliationResult.id == anomaly.reconciliation_result_id,
        ))
        if row is None:
            return {"source": anomaly.source, "source_record_id": anomaly.reconciliation_result_id,
                    "record_found": False, "status": None, "payment_id": None, "settlement_id": None,
                    "payment_amount": None, "refund_amount": None, "expected_settlement": None,
                    "actual_settlement": None, "variance": None,
                    "variance_convention": "expected_settlement - actual_settlement"}
        return {"source": anomaly.source, "source_record_id": row.id, "record_found": True,
                "status": row.status, "payment_id": row.payment_external_id,
                "settlement_id": row.settlement_external_id, "payment_amount": _money(row.payment_amount),
                "refund_amount": _money(row.refund_amount),
                "expected_settlement": _money(row.expected_settlement),
                "actual_settlement": _money(row.actual_settlement), "variance": _money(row.difference),
                "variance_convention": "expected_settlement - actual_settlement; positive means actual is lower"}
    return {"source": anomaly.source, "source_record_id": None, "record_found": False,
            "status": None, "variance": None,
            "anomaly_amount_difference": _money(anomaly.amount_difference),
            "variance_convention": "No linked source result; the anomaly row contains only a summary amount"}


def _assessment(anomaly, evidence):
    status = evidence.get("status") or anomaly.anomaly_type
    variance = evidence.get("variance")
    amount = Decimal(variance) if variance is not None else None
    is_bank = "bank" in (anomaly.source or "").lower()
    if not evidence.get("record_found"):
        return "The linked reconciliation result is unavailable, so the cause cannot be assessed.", "Restore or rerun the source reconciliation, then review its linked result.", "Limited"
    if status == "Matched" or (amount == 0 and status in {"Mismatch", "Amount Mismatch"}):
        return "The linked stored amounts do not show a variance; the anomaly label is not supported by this result.", "Review the anomaly run and linked source result for stale or inconsistent records.", "High"
    if status == "Missing Bank Transaction":
        return "A bank transaction is not linked to this settlement. Missing statement data or an unmatched reference is possible, but unproven.", "Check the imported bank statement and settlement reference before making an adjustment.", "Limited"
    if status == "Unmatched Bank Transaction":
        return "This bank transaction has no linked settlement. A missing settlement import or reference mismatch is possible, but unproven.", "Check the settlement import and bank transaction reference before making an adjustment.", "Limited"
    if amount is not None and amount > 0:
        if is_bank:
            return "The stored settlement amount exceeds the linked bank credit. A short credit is a hypothesis; the records do not establish its cause.", "Compare the bank statement entry with the processor settlement and confirm any fees or timing differences.", "High"
        return "The expected settlement exceeds the recorded settlement. A short settlement is a hypothesis; the records do not establish its cause.", "Review the payment, refund, fee, tax, and settlement records for this reference.", "High"
    if amount is not None and amount < 0:
        if is_bank:
            return "The linked bank credit exceeds the settlement amount. An excess or duplicate/incorrect credit is a hypothesis, not an established cause.", "Verify the bank entry and settlement reference; do not adjust the ledger until confirmed.", "High"
        return "The recorded settlement exceeds the expected settlement. An excess settlement is a hypothesis; the cause is not established.", "Review linked payment, refund, fee, tax, and settlement records before adjustment.", "High"
    if status == "Missing Settlement":
        return "No settlement amount is present in the linked result. A missing import or unmatched payment reference is possible, but unproven.", "Check the settlement import and payment reference, then rerun reconciliation after correcting source data.", "Limited"
    return "The stored result does not contain enough linked amount evidence to identify a likely explanation.", "Review the source records and references, then rerun reconciliation if data was corrected.", "Limited"


def _gemini_assessment(evidence, fallback_text):
    """Ask Gemini to classify evidence against two bounded choices; never accept prose from it."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Gemini is not configured")
    from google import genai
    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL", MODEL_DEFAULT)
    model_evidence = {key: value for key, value in evidence.items()
                      if key in {"source", "status", "record_found", "payment_amount", "refund_amount",
                                 "expected_settlement", "actual_settlement", "settlement_amount",
                                 "bank_amount", "variance", "variance_convention"}}
    prompt = ("Classify only whether the stored evidence supports reviewing this candidate hypothesis. "
              "Return exactly one code: supported or insufficient_evidence. Do not add causes or facts. "
              "Candidate hypothesis: " + fallback_text + "\nEvidence: " + json.dumps(model_evidence, sort_keys=True))
    response = client.models.generate_content(model=model, contents=prompt)
    answer = (getattr(response, "text", None) or "").strip()
    if answer not in {"supported", "insufficient_evidence"}:
        raise ValueError("Gemini response was outside the allowed evidence classifications")
    return answer


def _investigation(anomaly, db):
    evidence = _evidence_for(anomaly, db)
    explanation, action, confidence = _assessment(anomaly, evidence)
    label = "Evidence assessment" if "not supported by this result" in explanation else "Hypothesis"
    mode = "rule_based_fallback"
    try:
        model_assessment = _gemini_assessment(evidence, explanation)
        if model_assessment == "insufficient_evidence":
            explanation = "The stored evidence is insufficient to support a specific explanation; the cause remains unverified."
        mode = "gemini_assisted"
    except Exception:
        # Provider errors are neither exposed nor allowed to replace verified evidence.
        pass
    basis = ("Linked stored amounts and variance are present; they support the discrepancy, not its cause."
             if confidence == "High" else "A linked source amount is missing; the cause cannot be verified.")
    return {"anomaly_id": anomaly.id,
            "record": {"source": anomaly.source, "external_id": anomaly.transaction_external_id},
            "anomaly_type": anomaly.anomaly_type, "verified_evidence": evidence,
            "likely_explanation": {"label": label, "text": explanation},
            "severity": anomaly.severity,
            "confidence": {"level": confidence, "basis": basis},
            "recommended_next_action": action, "mode": mode}


def run_investigation(business_id: str, db: Session):
    anomaly_run = db.scalar(select(FinancialRun).where(
        FinancialRun.business_id == business_id,
        FinancialRun.run_type == FinancialRunType.ANOMALY_DETECTION.value,
        FinancialRun.status == FinancialRunStatus.SUCCEEDED.value,
    ).order_by(FinancialRun.completed_at.desc(), FinancialRun.started_at.desc()))
    if anomaly_run is None:
        raise ValueError("Run anomaly detection before investigation")
    anomalies = db.scalars(select(Anomaly).where(
        Anomaly.business_id == business_id, Anomaly.run_id == anomaly_run.id,
    ).order_by(Anomaly.transaction_external_id, Anomaly.id)).all()
    anomaly_ids = {row.id for row in anomalies}
    previous = db.scalar(select(FinancialRun).where(
        FinancialRun.business_id == business_id,
        FinancialRun.run_type == FinancialRunType.INVESTIGATION.value,
        FinancialRun.status == FinancialRunStatus.SUCCEEDED.value,
    ).order_by(FinancialRun.completed_at.desc(), FinancialRun.started_at.desc()))
    if previous is not None:
        prior_ids = set(db.scalars(select(InvestigationResult.anomaly_id).where(
            InvestigationResult.business_id == business_id, InvestigationResult.run_id == previous.id,
        )).all())
        if prior_ids == anomaly_ids:
            rows = db.scalars(select(InvestigationResult).where(
                InvestigationResult.business_id == business_id, InvestigationResult.run_id == previous.id,
            ).order_by(InvestigationResult.id)).all()
            return previous, rows, True
    run = FinancialRun(business_id=business_id, run_type=FinancialRunType.INVESTIGATION.value,
                       status=FinancialRunStatus.RUNNING.value)
    db.add(run)
    db.flush()
    for batch in db.scalars(select(FinancialRunImportBatch).where(
        FinancialRunImportBatch.business_id == business_id, FinancialRunImportBatch.run_id == anomaly_run.id,
    )).all():
        db.add(FinancialRunImportBatch(business_id=business_id, run_id=run.id, import_batch_id=batch.import_batch_id))
    results = []
    try:
        for anomaly in anomalies:
            result = InvestigationResult(business_id=business_id, run_id=run.id, anomaly_id=anomaly.id,
                                         investigation_text=json.dumps(_investigation(anomaly, db)))
            db.add(result)
            results.append(result)
        run.status = FinancialRunStatus.SUCCEEDED.value
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return run, results, False
    except Exception:
        db.rollback()
        raise


def get_latest_investigation(business_id: str, db: Session):
    run = db.scalar(select(FinancialRun).where(
        FinancialRun.business_id == business_id,
        FinancialRun.run_type == FinancialRunType.INVESTIGATION.value,
        FinancialRun.status == FinancialRunStatus.SUCCEEDED.value,
    ).order_by(FinancialRun.completed_at.desc(), FinancialRun.started_at.desc()))
    if run is None:
        return {"business_id": business_id, "run_id": None, "completed_at": None, "results": []}
    rows = db.scalars(select(InvestigationResult).where(
        InvestigationResult.business_id == business_id, InvestigationResult.run_id == run.id,
    ).order_by(InvestigationResult.id)).all()
    results = []
    for row in rows:
        try:
            results.append(json.loads(row.investigation_text))
        except (TypeError, json.JSONDecodeError):
            results.append({"anomaly_id": row.anomaly_id,
                            "likely_explanation": {"label": "Stored report", "text": row.investigation_text},
                            "mode": "rule_based_fallback"})
    return {"business_id": business_id, "run_id": run.id,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "results": results}
