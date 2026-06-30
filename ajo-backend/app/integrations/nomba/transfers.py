import json
import logging

from sqlalchemy.orm import Session

from app import models
from app.integrations.nomba.client import nomba_client, NombaClientError
from app.integrations.nomba.schemas import AccountEnquiryResponse, TransferResponse

logger = logging.getLogger(__name__)


async def name_enquiry(
    account_number: str,
    bank_code: str,
) -> AccountEnquiryResponse:
    data = await nomba_client.post(
        "/v1/transfers/name-enquiry",
        {"accountNumber": account_number, "bankCode": bank_code},
    )
    return AccountEnquiryResponse(**data)


async def payout_to_recipient(
    db: Session,
    payout: models.Payout,
    destination_account_number: str,
    bank_code: str,
) -> TransferResponse:
    merchant_tx_ref = f"ajo-payout-{payout.id}"

    existing = db.query(models.NombaTransaction).filter_by(
        merchant_tx_ref=merchant_tx_ref,
    ).first()
    if existing:
        logger.info("Payout %d already has a Nomba transaction ref, skipping", payout.id)
        return TransferResponse(
            merchantTxRef=merchant_tx_ref,
            transactionId=existing.nomba_transaction_id,
            status=existing.status.value,
        )

    amount_kobo = str(int(payout.amount * 100))
    payload = {
        "merchantTxRef": merchant_tx_ref,
        "destinationAccountNumber": destination_account_number,
        "bankCode": bank_code,
        "amount": amount_kobo,
        "narration": f"Ajo payout #{payout.id}",
    }

    nomba_txn = models.NombaTransaction(
        merchant_tx_ref=merchant_tx_ref,
        type=models.NombaTransactionType.payout,
        circle_id=payout.circle_id,
        amount=payout.amount,
        status=models.NombaTransactionStatus.pending,
    )
    db.add(nomba_txn)
    db.commit()

    try:
        data = await nomba_client.post("/v1/transfers/disburse", payload)
        response = TransferResponse(**data)

        nomba_txn.status = _map_nomba_status(response.status)
        nomba_txn.nomba_transaction_id = response.transactionId
        nomba_txn.raw_response = json.dumps(data)
        db.commit()

        return response

    except NombaClientError:
        nomba_txn.status = models.NombaTransactionStatus.failed
        db.commit()
        raise


def _map_nomba_status(status: str) -> models.NombaTransactionStatus:
    if status.upper() in ("SUCCESSFUL", "SUCCESS"):
        return models.NombaTransactionStatus.successful
    if status.upper() == "FAILED":
        return models.NombaTransactionStatus.failed
    return models.NombaTransactionStatus.pending
