"""Admin: see every member and control what they can do (role, suspend)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.phone import digits_only
from app.db.session import get_db
from app.models import Profile
from app.schemas.profile import AdminProfileOut, AdminProfileUpdate

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.get("", response_model=list[AdminProfileOut])
def list_users(
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Profile]:
    stmt = select(Profile)
    if q and q.strip():
        like = f"%{q.strip()}%"
        matches = [
            Profile.email.ilike(like),
            Profile.display_name.ilike(like),
            func.concat(Profile.first_name, " ", Profile.last_name).ilike(like),
        ]
        digits = digits_only(q)
        if len(digits) >= 4:
            # Phone and WhatsApp by digits, however they were typed: "703 555", "+91-77023".
            for column in (Profile.phone, Profile.whatsapp):
                stored = func.regexp_replace(func.coalesce(column, ""), r"\D", "", "g")
                matches.append(stored.like(f"%{digits}%"))
        stmt = stmt.where(or_(*matches))
    stmt = stmt.order_by(Profile.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.patch("/{user_id}", response_model=AdminProfileOut)
def update_user(
    user_id: uuid.UUID,
    payload: AdminProfileUpdate,
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Profile:
    if user_id == admin.id:
        # An admin locking themselves out would leave nobody to undo it.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "self_change", "message": "You can't change your own access."},
        )
    profile = db.get(Profile, user_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    for key, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile
