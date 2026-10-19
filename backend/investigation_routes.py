"""Authenticated business-scoped AI Investigator API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.business_routes import require_business_membership
from backend.db.database import get_db
from backend.db.models import BusinessMembership
from backend.investigation_service import get_latest_investigation, run_investigation

router = APIRouter(prefix="/api/businesses/{business_id}/investigations", tags=["Investigations"])


def _check_business(business_id, membership):
    if membership.business_id != business_id:
        raise HTTPException(status_code=404, detail="Business not found")


@router.post("/run", status_code=201)
def create_investigation_run(
    business_id: str,
    membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    _check_business(business_id, membership)
    try:
        run, results, reused = run_investigation(business_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"business_id": business_id, "run_id": run.id, "status": run.status,
            "result_count": len(results), "reused": reused}


@router.get("/results")
def read_investigation_results(
    business_id: str,
    membership: BusinessMembership = Depends(require_business_membership),
    db: Session = Depends(get_db),
):
    _check_business(business_id, membership)
    return get_latest_investigation(business_id, db)
