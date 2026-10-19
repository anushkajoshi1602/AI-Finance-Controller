"""Business workspace creation endpoints."""

import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth_routes import get_current_user
from backend.db.database import get_db
from backend.db.models import (
    Business,
    BusinessMembership,
    MembershipRole,
    MembershipStatus,
    User,
)

router = APIRouter(prefix="/api/businesses", tags=["Businesses"])


def require_business_membership(
    business_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessMembership:
    """Return the caller's active membership, hiding inaccessible businesses."""
    membership = db.scalar(
        select(BusinessMembership).where(
            BusinessMembership.business_id == business_id,
            BusinessMembership.user_id == user.id,
            BusinessMembership.status == MembershipStatus.ACTIVE.value,
        )
    )
    if membership is None:
        # Same response for nonexistent businesses and businesses the caller
        # cannot access, so this dependency does not reveal another tenant.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return membership


def require_business_role(*allowed_roles: MembershipRole):
    """Build a dependency that checks only the explicitly listed roles.

    This does not define a product-wide role policy. Call sites must choose
    their allowed roles explicitly; no implicit owner/admin hierarchy exists.
    """
    role_values = {role.value for role in allowed_roles}

    def check_role(
        membership: BusinessMembership = Depends(require_business_membership),
    ) -> BusinessMembership:
        if membership.role not in role_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient business role",
            )
        return membership

    return check_role


class CreateBusinessRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


def _slug_base(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Business name must contain letters or numbers",
        )
    return slug[:100].rstrip("-")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_business(
    payload: CreateBusinessRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Business name cannot be blank",
        )

    base_slug = _slug_base(name)
    slug = base_slug
    suffix = 2
    while db.query(Business.id).filter(Business.slug == slug).first():
        ending = f"-{suffix}"
        slug = f"{base_slug[:100 - len(ending)].rstrip('-')}{ending}"
        suffix += 1

    business = Business(
        name=name,
        slug=slug,
        created_by_user_id=user.id,
    )
    membership = BusinessMembership(
        business=business,
        user_id=user.id,
        role=MembershipRole.OWNER.value,
        status=MembershipStatus.ACTIVE.value,
    )
    db.add_all([business, membership])

    try:
        db.commit()
        db.refresh(business)
        db.refresh(membership)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create business workspace",
        )

    return {
        "business": {
            "id": business.id,
            "name": business.name,
            "slug": business.slug,
            "legal_name": business.legal_name,
            "base_currency": business.base_currency,
            "timezone": business.timezone,
            "status": business.status,
        },
        "membership": {
            "id": membership.id,
            "business_id": membership.business_id,
            "user_id": membership.user_id,
            "role": membership.role,
            "status": membership.status,
        },
    }


@router.get("")
def list_businesses(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memberships = db.scalars(
        select(BusinessMembership).where(
            BusinessMembership.user_id == user.id,
            BusinessMembership.status == MembershipStatus.ACTIVE.value,
        ).order_by(BusinessMembership.created_at)
    ).all()
    return [{
        "id": membership.business.id,
        "name": membership.business.name,
        "slug": membership.business.slug,
        "role": membership.role,
    } for membership in memberships]


@router.get("/{business_id}")
def get_business(
    membership: BusinessMembership = Depends(require_business_membership),
):
    business = membership.business
    return {
        "business": {
            "id": business.id,
            "name": business.name,
            "slug": business.slug,
            "legal_name": business.legal_name,
            "base_currency": business.base_currency,
            "timezone": business.timezone,
            "status": business.status,
        },
        "membership": {
            "id": membership.id,
            "business_id": membership.business_id,
            "user_id": membership.user_id,
            "role": membership.role,
            "status": membership.status,
        },
    }
