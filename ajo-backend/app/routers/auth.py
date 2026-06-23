import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_user
from app.security import create_access_token, hash_pin, verify_pin

router = APIRouter(prefix="/auth", tags=["auth"])

# Comma-separated phone numbers that get is_admin=True on signup, e.g.
# "08010000001,08010000002". Sprint-friendly way to bootstrap an admin
# account without a separate promote-to-admin endpoint.
ADMIN_PHONES = {p.strip() for p in os.getenv("ADMIN_PHONES", "").split(",") if p.strip()}


@router.post("/signup", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: schemas.SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.phone == payload.phone).first()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Phone number already registered")

    user = models.User(
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        pin_hash=hash_pin(payload.pin),
        is_admin=payload.phone in ADMIN_PHONES,
    )
    db.add(user)
    db.flush()

    # The other dev's Wallet table — created here so every user always has
    # one, even though Wallet itself is owned by the circles/wallet dev.
    db.add(models.Wallet(user_id=user.id, balance=0))
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id))
    return schemas.TokenResponse(access_token=token, user=schemas.UserOut.model_validate(user))


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == payload.phone).first()
    if not user or not verify_pin(payload.pin, user.pin_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid phone number or PIN")

    token = create_access_token(subject=str(user.id))
    return schemas.TokenResponse(access_token=token, user=schemas.UserOut.model_validate(user))


@router.post("/verify-pin")
def verify_pin_endpoint(
    payload: schemas.PinVerifyRequest,
    current_user: models.User = Depends(get_current_user),
):
    if not verify_pin(payload.pin, current_user.pin_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect PIN")
    return {"ok": True}
