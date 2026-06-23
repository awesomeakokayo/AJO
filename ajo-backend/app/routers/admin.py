from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/verification-queue", response_model=List[schemas.AdminVerificationQueueItem])
def list_verification_queue(
    _admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Every user currently in `submitted` status, with their docs attached,
    so the admin can review NIN/BVN/selfie together rather than hunting
    across endpoints."""
    pending_users = (
        db.query(models.User)
        .filter(models.User.verification_status == models.VerificationStatus.submitted)
        .all()
    )
    return [
        schemas.AdminVerificationQueueItem(
            user=schemas.UserOut.model_validate(u),
            docs=[
                schemas.VerificationDocOut.model_validate(d)
                for d in db.query(models.VerificationDoc).filter_by(user_id=u.id).all()
            ],
        )
        for u in pending_users
    ]


@router.post("/verification/{user_id}/approve", response_model=schemas.UserOut)
def approve_verification(
    user_id: int,
    payload: schemas.AdminDecisionRequest,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    user.verification_status = models.VerificationStatus.verified
    db.query(models.VerificationDoc).filter_by(user_id=user_id).update(
        {
            "status": models.VerificationDocStatus.approved,
            "reviewed_by": admin.id,
            "reviewed_at": datetime.utcnow(),
        }
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/verification/{user_id}/reject", response_model=schemas.UserOut)
def reject_verification(
    user_id: int,
    payload: schemas.AdminDecisionRequest,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    user.verification_status = models.VerificationStatus.rejected
    db.query(models.VerificationDoc).filter_by(user_id=user_id).update(
        {
            "status": models.VerificationDocStatus.rejected,
            "reviewed_by": admin.id,
            "reviewed_at": datetime.utcnow(),
        }
    )
    db.commit()
    db.refresh(user)
    return user
