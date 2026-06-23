"""
ALATPay integration stub. Replace the TODOs with real ALATPay API calls
once sandbox credentials are wired up — the rest of the app only depends
on these three function signatures, so swapping the internals later
shouldn't require touching any router code.
"""

import os
import secrets

ALATPAY_API_KEY = os.getenv("ALATPAY_API_KEY")
ALATPAY_BASE_URL = os.getenv("ALATPAY_BASE_URL", "https://sandbox.alatpay.ng/api")


def initiate_collection(amount: float, user_id: int) -> dict:
    """Create a wallet-funding request. Returns a checkout URL + reference
    the frontend opens in a WebView/WebBrowser."""
    # TODO: replace with a real POST to ALATPay's collection/checkout endpoint.
    reference = f"FUND-{secrets.token_hex(6)}"
    return {
        "checkout_url": f"{ALATPAY_BASE_URL}/checkout/{reference}?amount={amount}",
        "reference": reference,
    }


def initiate_disbursement(amount: float, bank_account_number: str, bank_code: str) -> dict:
    """Create a withdrawal/transfer request. Returns a reference; status
    starts pending until ALATPay confirms via webhook or polling."""
    # TODO: replace with a real POST to ALATPay's transfer/disbursement endpoint.
    reference = f"WTHD-{secrets.token_hex(6)}"
    return {"reference": reference, "status": "pending"}


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """TODO: verify the ALATPay webhook signature using the shared secret.
    Returning True unconditionally for local/demo testing only — DO NOT
    ship this to production unmodified."""
    return True
