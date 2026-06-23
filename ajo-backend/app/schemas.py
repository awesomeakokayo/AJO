from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    CircleFrequency,
    CircleStatus,
    ContributionStatus,
    InviteStatus,
    MembershipStatus,
    PayoutOrderType,
    TransactionStatus,
    TransactionType,
    VerificationDocStatus,
    VerificationDocType,
    VerificationStatus,
)


# =====================================================================
# Auth / Users / Admin verification — OWNED BY: Auth/KYC dev
# =====================================================================

class SignupRequest(BaseModel):
    full_name: str
    phone: str
    email: Optional[str] = None
    pin: str = Field(min_length=4, max_length=4)


class LoginRequest(BaseModel):
    phone: str
    pin: str


class PinVerifyRequest(BaseModel):
    pin: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    phone: str
    email: Optional[str] = None
    verification_status: VerificationStatus
    is_admin: bool
    trust_score: int
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None


class VerificationSubmitRequest(BaseModel):
    type: VerificationDocType
    value_or_url: str


class VerificationDocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: VerificationDocType
    status: VerificationDocStatus
    created_at: datetime


class AdminVerificationQueueItem(BaseModel):
    """One pending user's full submission, for the admin review screen."""
    user: UserOut
    docs: List[VerificationDocOut]


class AdminDecisionRequest(BaseModel):
    reason: Optional[str] = None


# =====================================================================
# Circles / Memberships / Contributions / Payouts — OWNED BY: other dev
# =====================================================================

class CircleCreate(BaseModel):
    name: str
    contribution_amount: float
    frequency: CircleFrequency = CircleFrequency.weekly
    member_capacity: int = Field(ge=2, le=50, default=4)
    payout_order: PayoutOrderType = PayoutOrderType.random
    open_join: bool = False


class CircleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_by: int
    contribution_amount: float
    frequency: CircleFrequency
    member_capacity: int
    payout_order: PayoutOrderType
    open_join: bool
    status: CircleStatus
    cycle_goal: float
    total_saved: float
    current_turn_index: int
    created_at: datetime


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    circle_id: int
    user_id: int
    status: MembershipStatus
    payout_position: Optional[int] = None
    joined_at: datetime


class JoinRequestOut(BaseModel):
    membership_id: int
    user: UserOut
    ai_summary: Optional[str] = None
    requested_at: datetime


class ContributionCreate(BaseModel):
    pin: str


class ContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    circle_id: int
    user_id: int
    amount: float
    status: ContributionStatus
    paid_at: datetime


class MarkPayoutPaidRequest(BaseModel):
    pin: str


# =====================================================================
# Wallet / Transactions — OWNED BY: other dev
# =====================================================================

class WalletOut(BaseModel):
    balance: float
    total_savings: float = 0
    active_circles: int = 0


class FundWalletRequest(BaseModel):
    amount: float = Field(gt=0)


class FundWalletResponse(BaseModel):
    checkout_url: str
    reference: str


class WithdrawRequest(BaseModel):
    amount: float = Field(gt=0)
    pin: str
    bank_account_number: str
    bank_code: str


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: TransactionType
    amount: float
    status: TransactionStatus
    reference: Optional[str] = None
    created_at: datetime


class AlatpayWebhookPayload(BaseModel):
    reference: str
    status: str
    amount: float
    signature: Optional[str] = None


# =====================================================================
# Invites — OWNED BY: other dev
# =====================================================================

class InviteCreate(BaseModel):
    invitee_contact: Optional[str] = None


class InviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    circle_id: int
    code: str
    status: InviteStatus
    created_at: datetime


class InvitePreview(BaseModel):
    circle: CircleOut
    invited_by: UserOut


# =====================================================================
# Notifications — OWNED BY: other dev
# =====================================================================

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    body: str
    read: bool
    created_at: datetime
