from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NombaTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class NombaErrorResponse(BaseModel):
    code: Optional[str] = None
    message: Optional[str] = None


class VirtualAccountRequest(BaseModel):
    accountRef: str
    accountName: str
    expectedAmount: Optional[str] = None


class VirtualAccountResponse(BaseModel):
    accountRef: str
    accountNumber: str
    accountName: str
    bankCode: str
    bankName: str
    status: str


class AccountEnquiryRequest(BaseModel):
    accountNumber: str
    bankCode: str


class AccountEnquiryResponse(BaseModel):
    accountNumber: str
    accountName: str
    bankCode: str


class TransferRequest(BaseModel):
    merchantTxRef: str
    destinationAccountNumber: str
    bankCode: str
    amount: str
    narration: str


class TransferResponse(BaseModel):
    merchantTxRef: str
    transactionId: Optional[str] = None
    status: str
    message: Optional[str] = None


class NombaWebhookPayload(BaseModel):
    event_type: str
    requestId: str
    data: dict
    timestamp: Optional[str] = None
