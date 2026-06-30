import hashlib
import hmac
import base64
import logging

logger = logging.getLogger(__name__)


def verify_nomba_signature(
    payload: dict,
    timestamp: str,
    received_signature: str,
    signature_key: str,
) -> bool:
    data = payload.get("data", {})
    merchant = data.get("merchant", {})
    transaction = data.get("transaction", {})

    hashing_payload = ":".join([
        str(payload.get("event_type", "")),
        str(payload.get("requestId", "")),
        str(merchant.get("userId", "")),
        str(merchant.get("walletId", "")),
        str(transaction.get("transactionId", "")),
        str(transaction.get("type", "")),
        str(transaction.get("time", "")),
        str(transaction.get("responseCode", "")),
    ])
    message = f"{hashing_payload}:{timestamp}"

    computed = hmac.new(
        signature_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).digest()
    computed_signature = base64.b64encode(computed).decode()

    result = hmac.compare_digest(computed_signature, received_signature)
    if not result:
        logger.warning("Nomba webhook signature mismatch")
    return result
