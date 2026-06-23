from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=schemas.UserOut)
def update_me(
    payload: schemas.UserUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.email is not None:
        current_user.email = payload.email
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/verification", response_model=schemas.VerificationDocOut, status_code=201)
def submit_verification(
    payload: schemas.VerificationSubmitRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stores the NIN/BVN/selfie submission and sets the user to
    `submitted`. Approval is a manual admin action (see admin.py) — this
    is a deliberate change from the original PRD's auto-approve stub."""
    doc = models.VerificationDoc(
        user_id=current_user.id,
        type=payload.type,
        value_or_url=payload.value_or_url,
    )
    db.add(doc)

    if current_user.verification_status == models.VerificationStatus.unverified:
        current_user.verification_status = models.VerificationStatus.submitted

    db.commit()
    db.refresh(doc)
    return doc


@router.get("/me/verification", response_model=List[schemas.VerificationDocOut])
def list_my_verification_docs(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(models.VerificationDoc).filter_by(user_id=current_user.id).all()
