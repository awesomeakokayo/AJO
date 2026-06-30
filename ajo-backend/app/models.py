import enum
import secrets
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


def _generate_invite_code() -> str:
    return f"AJO-{secrets.token_hex(2).upper()}"


# =====================================================================
# OWNED BY: Auth/KYC dev — User, VerificationDoc.
# If you're touching anything below this block, you're probably the
# other dev and should be editing the section further down instead.
# =====================================================================

class VerificationStatus(str, enum.Enum):
    unverified = "unverified"
    submitted = "submitted"
    verified = "verified"
    rejected = "rejected"


class VerificationDocType(str, enum.Enum):
    nin = "nin"
    bvn = "bvn"
    selfie = "selfie"


class VerificationDocStatus(str, enum.Enum):
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(120), nullable=True)
    pin_hash = Column(String(255), nullable=False)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.unverified)
    is_admin = Column(Boolean, default=False)
    trust_score = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)

    verification_docs = relationship(
        "VerificationDoc", back_populates="user", foreign_keys="VerificationDoc.user_id"
    )

    # Reverse relationships into the other dev's tables — declared here so
    # `user.wallet`, `user.memberships`, etc. work, but the tables
    # themselves live in the section below.
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    memberships = relationship("Membership", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    circles_created = relationship("Circle", back_populates="creator")


class VerificationDoc(Base):
    __tablename__ = "verification_docs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(Enum(VerificationDocType), nullable=False)
    value_or_url = Column(String(255), nullable=False)
    status = Column(Enum(VerificationDocStatus), default=VerificationDocStatus.submitted)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # admin user id
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="verification_docs", foreign_keys=[user_id])


# =====================================================================
# OWNED BY: Circles/Wallet/Notifications dev — everything below.
# Only references User by user_id; never edits the User table itself.
# =====================================================================

class CircleFrequency(str, enum.Enum):
    weekly = "weekly"
    monthly = "monthly"
    biweekly = "biweekly"


class PayoutOrderType(str, enum.Enum):
    random = "random"
    sequential = "sequential"


class CircleStatus(str, enum.Enum):
    forming = "forming"
    active = "active"
    completed = "completed"


class MembershipStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    denied = "denied"
    left = "left"


class ContributionStatus(str, enum.Enum):
    paid = "paid"
    late = "late"
    missed = "missed"


class PayoutStatus(str, enum.Enum):
    scheduled = "scheduled"
    paid = "paid"


class TransactionType(str, enum.Enum):
    funding = "funding"
    withdrawal = "withdrawal"
    contribution = "contribution"
    payout = "payout"


class TransactionStatus(str, enum.Enum):
    success = "success"
    pending = "pending"
    failed = "failed"


class InviteStatus(str, enum.Enum):
    waiting = "waiting"
    accepted = "accepted"
    expired = "expired"


class NombaTransactionStatus(str, enum.Enum):
    pending = "PENDING"
    successful = "SUCCESSFUL"
    failed = "FAILED"


class NombaTransactionType(str, enum.Enum):
    contribution = "contribution"
    payout = "payout"


class Circle(Base):
    __tablename__ = "circles"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    contribution_amount = Column(Float, nullable=False)
    frequency = Column(Enum(CircleFrequency), nullable=False, default=CircleFrequency.weekly)
    member_capacity = Column(Integer, nullable=False, default=4)
    payout_order = Column(Enum(PayoutOrderType), nullable=False, default=PayoutOrderType.random)
    open_join = Column(Boolean, default=False)  # True skips AI-reviewed approval, auto-joins
    status = Column(Enum(CircleStatus), default=CircleStatus.forming)
    cycle_goal = Column(Float, default=0)
    current_turn_index = Column(Integer, default=0)
    total_saved = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    nomba_account_ref = Column(String(120), nullable=True)
    nomba_account_number = Column(String(20), nullable=True)

    creator = relationship("User", back_populates="circles_created")
    memberships = relationship("Membership", back_populates="circle")
    contributions = relationship("Contribution", back_populates="circle")
    payouts = relationship("Payout", back_populates="circle")
    invites = relationship("Invite", back_populates="circle")


class Membership(Base):
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True)
    circle_id = Column(Integer, ForeignKey("circles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(MembershipStatus), default=MembershipStatus.pending)
    payout_position = Column(Integer, nullable=True)
    ai_summary = Column(Text, nullable=True)
    ai_summary_generated_at = Column(DateTime, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

    circle = relationship("Circle", back_populates="memberships")
    user = relationship("User", back_populates="memberships")


class Contribution(Base):
    __tablename__ = "contributions"

    id = Column(Integer, primary_key=True)
    circle_id = Column(Integer, ForeignKey("circles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Enum(ContributionStatus), default=ContributionStatus.paid)
    paid_at = Column(DateTime, default=datetime.utcnow)

    circle = relationship("Circle", back_populates="contributions")
    user = relationship("User")


class Payout(Base):
    __tablename__ = "payouts"

    id = Column(Integer, primary_key=True)
    circle_id = Column(Integer, ForeignKey("circles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Enum(PayoutStatus), default=PayoutStatus.scheduled)
    scheduled_for = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)

    circle = relationship("Circle", back_populates="payouts")
    user = relationship("User")


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Float, default=0)

    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.pending)
    reference = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    wallet = relationship("Wallet", back_populates="transactions")


class Invite(Base):
    __tablename__ = "invites"

    id = Column(Integer, primary_key=True)
    circle_id = Column(Integer, ForeignKey("circles.id"), nullable=False)
    code = Column(String(20), unique=True, nullable=False, default=_generate_invite_code)
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    invitee_contact = Column(String(120), nullable=True)
    status = Column(Enum(InviteStatus), default=InviteStatus.waiting)
    created_at = Column(DateTime, default=datetime.utcnow)

    circle = relationship("Circle", back_populates="invites")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(40), nullable=False)
    title = Column(String(120), nullable=False)
    body = Column(Text, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")


class NombaTransaction(Base):
    """Ledger for all Nomba-side money movements — the reconciliation
    source of truth. Every contribution and payout that touches Nomba
    gets a row here before the call, and the webhook updates the status."""

    __tablename__ = "nomba_transactions"

    id = Column(Integer, primary_key=True)
    merchant_tx_ref = Column(String(120), unique=True, nullable=False, index=True)
    nomba_transaction_id = Column(String(120), nullable=True)
    type = Column(Enum(NombaTransactionType), nullable=False)
    circle_id = Column(Integer, ForeignKey("circles.id"), nullable=True)
    amount = Column(Float, nullable=False)
    status = Column(Enum(NombaTransactionStatus), default=NombaTransactionStatus.pending)
    raw_response = Column(Text, nullable=True)  # JSON dump of Nomba's response
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
