"""Authenticated, business-scoped CSV onboarding."""

import csv
import hashlib
import io
import json
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.business_routes import require_business_membership
from backend.db.database import PROJECT_ROOT, get_db
from backend.db.models import (
    BankTransaction, BusinessMembership, Customer, ImportBatch, Payment, Refund,
    Settlement,
)

router = APIRouter(prefix="/api/businesses/{business_id}/imports", tags=["Imports"])
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
STORAGE_DIR = PROJECT_ROOT / "instance" / "imports"

DATASETS = {
    "customers": (Customer, {"external_id", "name", "email"}, set()),
    "payments": (Payment, {"external_id", "amount", "status"}, {"customer_external_id"}),
    "refunds": (Refund, {"external_id", "payment_external_id", "refund_amount"}, {"payment_external_id"}),
    "settlements": (Settlement, {"external_id", "payment_external_id", "gross_amount", "refund_amount", "fee", "tax", "net_amount"}, {"payment_external_id"}),
    "bank_transactions": (BankTransaction, {"external_id", "amount"}, {"settlement_external_id"}),
}
MONEY_FIELDS = {"amount", "refund_amount", "gross_amount", "fee", "tax", "net_amount"}
DATE_FIELDS = {"payment_date", "refund_date", "transaction_date"}
HEADER_ALIASES = {
    "customers": {"customer_id": "external_id", "customer_name": "name", "customer_email": "email"},
    "payments": {"payment_id": "external_id", "customer_id": "customer_external_id"},
    "refunds": {"refund_id": "external_id", "payment_id": "payment_external_id"},
    "settlements": {"settlement_id": "external_id", "payment_id": "payment_external_id"},
    "bank_transactions": {"transaction_id": "external_id", "settlement_id": "settlement_external_id"},
}


def _parse_csv(data: bytes, dataset: str):
    model, required, _ = DATASETS[dataset]
    try:
        text = data.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
    except (UnicodeDecodeError, csv.Error):
        raise ValueError("Upload must be a UTF-8 CSV")
    aliases = HEADER_ALIASES[dataset]
    headers = {aliases.get(field, field) for field in (reader.fieldnames or [])}
    missing = sorted(required - headers)
    if missing:
        raise ValueError(f"Missing required headers: {', '.join(missing)}")
    if "business_id" in headers:
        # Ignore the untrusted column entirely. Tenant always comes from route authorization.
        pass
    rows, errors, seen = [], [], set()
    for line, raw in enumerate(reader, start=2):
        row = {aliases.get(k, k): (v.strip() if v is not None else "") for k, v in raw.items() if k}
        ext = row.get("external_id", "")
        if not ext:
            errors.append(f"Row {line}: external_id is required")
            continue
        if ext in seen:
            errors.append(f"Row {line}: duplicate external_id {ext!r} in upload")
            continue
        seen.add(ext)
        parsed = {}
        for key, value in row.items():
            if key == "business_id" or value == "":
                continue
            if key in MONEY_FIELDS:
                try:
                    amount = Decimal(value)
                    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
                        raise InvalidOperation
                    parsed[key] = amount
                except (InvalidOperation, ValueError):
                    errors.append(f"Row {line}: {key} must be a non-negative amount with at most 2 decimal places")
            elif key in DATE_FIELDS:
                try:
                    parsed[key] = datetime.combine(date.fromisoformat(value), datetime.min.time())
                except ValueError:
                    errors.append(f"Row {line}: {key} must use YYYY-MM-DD")
            elif key in model.__table__.columns:
                parsed[key] = value
        rows.append(parsed)
    if not rows:
        errors.append("CSV must contain at least one data row")
    return rows, errors


@router.post("/{dataset_type}", status_code=201)
async def upload_csv(
    business_id: str,
    dataset_type: str,
    file: UploadFile = File(...),
    membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    if dataset_type not in DATASETS:
        raise HTTPException(422, "Unsupported dataset type")
    if membership.business_id != business_id:
        raise HTTPException(404, "Business not found")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "CSV exceeds the 10 MiB upload limit")
    content_hash = hashlib.sha256(data).hexdigest()
    previous = db.scalar(select(ImportBatch).where(
        ImportBatch.business_id == business_id,
        ImportBatch.dataset_type == dataset_type,
        ImportBatch.content_hash == content_hash,
    ))
    if previous:
        return {"id": previous.id, "dataset_type": previous.dataset_type,
                "status": previous.validation_status, "content_hash": content_hash,
                "duplicate_upload": True, "validation_errors": json.loads(previous.validation_errors or "[]")}
    try:
        rows, errors = _parse_csv(data, dataset_type)
    except ValueError as exc:
        rows, errors = [], [str(exc)]
    model, _, references = DATASETS[dataset_type]
    for idx, row in enumerate(rows, start=2):
        for field in references:
            reference = row.get(field)
            if not reference:
                continue
            target = {"customer_external_id": Customer, "payment_external_id": Payment,
                      "settlement_external_id": Settlement}[field]
            found = db.scalar(select(target.id).where(target.business_id == business_id,
                target.external_id == reference))
            if not found:
                errors.append(f"Row {idx}: {field} {reference!r} does not exist in this business")
    key = f"{uuid.uuid4().hex}.csv"
    batch = ImportBatch(business_id=business_id, dataset_type=dataset_type,
        original_filename=Path(file.filename or "upload.csv").name[:255], storage_key=key,
        content_hash=content_hash, validation_status="failed" if errors else "validating",
        validation_errors=json.dumps(errors))
    path = STORAGE_DIR / key
    try:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        db.add(batch)
        db.flush()
        if not errors:
            for row in rows:
                db.add(model(business_id=business_id, import_batch_id=batch.id, **row))
            batch.validation_status = "validated"
        db.commit()
        db.refresh(batch)
    except IntegrityError:
        db.rollback()
        path.unlink(missing_ok=True)
        # A concurrent retry may have won; return the canonical batch safely.
        previous = db.scalar(select(ImportBatch).where(ImportBatch.business_id == business_id,
            ImportBatch.dataset_type == dataset_type, ImportBatch.content_hash == content_hash))
        if previous:
            return {"id": previous.id, "dataset_type": dataset_type, "status": previous.validation_status,
                    "content_hash": content_hash, "duplicate_upload": True,
                    "validation_errors": json.loads(previous.validation_errors or "[]")}
        raise HTTPException(422, "Import conflicts with existing business records")
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return {"id": batch.id, "dataset_type": dataset_type, "status": batch.validation_status,
            "content_hash": content_hash, "duplicate_upload": False, "validation_errors": errors}


@router.get("/{batch_id}")
def get_import_status(business_id: str, batch_id: str,
    membership: BusinessMembership = Depends(require_business_membership), db: Session = Depends(get_db)):
    batch = db.scalar(select(ImportBatch).where(ImportBatch.business_id == business_id,
        ImportBatch.id == batch_id))
    if batch is None:
        raise HTTPException(404, "Import batch not found")
    return {"id": batch.id, "dataset_type": batch.dataset_type, "status": batch.validation_status,
            "content_hash": batch.content_hash, "uploaded_at": batch.uploaded_at,
            "validation_errors": json.loads(batch.validation_errors or "[]")}
