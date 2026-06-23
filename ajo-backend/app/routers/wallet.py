from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_user
from app.security import verify_pin
from app.services.alatpay_service import initiate_collection, initiate_disbursement, verify_webhook_signature

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=schemas.WalletOut)
def get_wallet(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    wallet = current_user.wallet
    active_circles = (
        db.query(models.Membership)
        .filter_by(user_id=current_user.id, status=models.MembershipStatus.active)
        .count()
    )
    contributions_sum = sum(c.amount for c in db.query(models.Contribution).filter_by(user_id=current_user.id).all())
    return schemas.WalletOut(balance=wallet.balance, total_savings=contributions_sum, active_circles=active_circles)


@router.post("/fund", response_model=schemas.FundWalletResponse)
def fund_wallet(
    payload: schemas.FundWalletRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = initiate_collection(payload.amount, current_user.id)
    db.add(
        models.Transaction(
            wallet_id=current_user.wallet.id,
            type=models.TransactionType.funding,
            amount=payload.amount,
            status=models.TransactionStatus.pending,
            reference=result["reference"],
        )
    )
    db.commit()
    return schemas.FundWalletResponse(**result)


@router.post("/webhook/alatpay")
def alatpay_webhook(payload: schemas.AlatpayWebhookPayload, db: Session = Depends(get_db)):
    if not verify_webhook_signature(payload.model_dump_json().encode(), payload.signature or ""):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")

    txn = db.query(models.Transaction).filter_by(reference=payload.reference).first()
    if not txn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")

    if payload.status == "success" and txn.status != models.TransactionStatus.success:
        txn.status = models.TransactionStatus.success
        txn.wallet.balance += txn.amount
    elif payload.status == "failed":
        txn.status = models.TransactionStatus.failed

    db.commit()
    return {"ok": True}


@router.post("/withdraw", response_model=schemas.TransactionOut)
def withdraw(
    payload: schemas.WithdrawRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_pin(payload.pin, current_user.pin_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect PIN")

    wallet = current_user.wallet
    if wallet.balance < payload.amount:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Insufficient balance")

    result = initiate_disbursement(payload.amount, payload.bank_account_number, payload.bank_code)
    wallet.balance -= payload.amount

    txn = models.Transaction(
        wallet_id=wallet.id,
        type=models.TransactionType.withdrawal,
        amount=-payload.amount,
        status=models.TransactionStatus.pending,
        reference=result["reference"],
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


@router.get("/transactions", response_model=List[schemas.TransactionOut])
def list_transactions(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.Transaction)
        .filter_by(wallet_id=current_user.wallet.id)
        .order_by(models.Transaction.created_at.desc())
        .all()
    )
