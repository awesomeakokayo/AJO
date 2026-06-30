import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.integrations.nomba.config import nomba_settings
from app.integrations.nomba.webhooks import verify_nomba_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/nomba")
async def nomba_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    raw = body.decode("utf-8")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON")

    received_signature = request.headers.get("x-nomba-signature", "")
    timestamp = request.headers.get("x-nomba-timestamp", "")

    if not received_signature or not timestamp:
        logger.warning("Nomba webhook missing signature or timestamp headers")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing signature headers")

    if not verify_nomba_signature(
        payload,
        timestamp,
        received_signature,
        nomba_settings.webhook_signature_key,
    ):
        logger.warning("Nomba webhook signature verification failed")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")

    data = payload.get("data", {})
    transaction = data.get("transaction", {})

    merchant_tx_ref = transaction.get("merchantTxRef", "")
    nomba_txn_id = transaction.get("transactionId", "")
    nomba_status = transaction.get("status", "")

    if merchant_tx_ref:
        nomba_txn = db.query(models.NombaTransaction).filter_by(
            merchant_tx_ref=merchant_tx_ref,
        ).first()
        if nomba_txn:
            nomba_txn.status = _map_status(nomba_status)
            nomba_txn.nomba_transaction_id = nomba_txn_id
            nomba_txn.raw_response = raw
            db.commit()

            if (
                nomba_txn.type == models.NombaTransactionType.contribution
                and nomba_txn.status == models.NombaTransactionStatus.successful
                and nomba_txn.circle_id
            ):
                circle = db.get(models.Circle, nomba_txn.circle_id)
                if circle:
                    circle.total_saved += nomba_txn.amount
                    db.commit()

    return {"ok": True}


def _map_status(status: str) -> models.NombaTransactionStatus:
    if status.upper() in ("SUCCESSFUL", "SUCCESS"):
        return models.NombaTransactionStatus.successful
    if status.upper() == "FAILED":
        return models.NombaTransactionStatus.failed
    return models.NombaTransactionStatus.pending
