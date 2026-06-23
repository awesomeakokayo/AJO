import random
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_user
from app.security import verify_pin
from app.services.groq_service import generate_join_summary
from app.services.user_stats import compute_user_stats

router = APIRouter(prefix="/circles", tags=["circles"])


def _require_admin(circle: models.Circle, user: models.User):
    if circle.created_by != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the circle creator can do this")


def _get_circle_or_404(db: Session, circle_id: int) -> models.Circle:
    circle = db.get(models.Circle, circle_id)
    if not circle:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Circle not found")
    return circle


@router.get("", response_model=List[schemas.CircleOut])
def list_circles(
    filter: Optional[str] = Query(None, description="weekly|monthly|near_me"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(models.Circle).filter(models.Circle.status != models.CircleStatus.completed)
    if filter == "weekly":
        query = query.filter(models.Circle.frequency == models.CircleFrequency.weekly)
    elif filter == "monthly":
        query = query.filter(models.Circle.frequency == models.CircleFrequency.monthly)
    # "near_me" stubbed: no real geo-matching for MVP, returns all circles.
    if search:
        query = query.filter(models.Circle.name.ilike(f"%{search}%"))
    return query.all()


@router.post("", response_model=schemas.CircleOut, status_code=status.HTTP_201_CREATED)
def create_circle(
    payload: schemas.CircleCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    circle = models.Circle(
        name=payload.name,
        created_by=current_user.id,
        contribution_amount=payload.contribution_amount,
        frequency=payload.frequency,
        member_capacity=payload.member_capacity,
        payout_order=payload.payout_order,
        open_join=payload.open_join,
        cycle_goal=payload.contribution_amount * payload.member_capacity,
    )
    db.add(circle)
    db.flush()

    creator_membership = models.Membership(
        circle_id=circle.id,
        user_id=current_user.id,
        status=models.MembershipStatus.active,
        payout_position=0 if payload.payout_order == models.PayoutOrderType.sequential else None,
    )
    db.add(creator_membership)
    db.commit()
    db.refresh(circle)
    return circle


@router.get("/{circle_id}", response_model=schemas.CircleOut)
def get_circle(circle_id: int, db: Session = Depends(get_db)):
    return _get_circle_or_404(db, circle_id)


@router.get("/{circle_id}/members", response_model=List[schemas.MembershipOut])
def list_members(circle_id: int, db: Session = Depends(get_db)):
    _get_circle_or_404(db, circle_id)
    return (
        db.query(models.Membership)
        .filter_by(circle_id=circle_id, status=models.MembershipStatus.active)
        .all()
    )


@router.post("/{circle_id}/join", response_model=schemas.MembershipOut, status_code=status.HTTP_201_CREATED)
def request_to_join(
    circle_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    circle = _get_circle_or_404(db, circle_id)

    existing = db.query(models.Membership).filter_by(circle_id=circle_id, user_id=current_user.id).first()
    if existing and existing.status in (models.MembershipStatus.active, models.MembershipStatus.pending):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Already a member or already requested")

    active_count = (
        db.query(models.Membership)
        .filter_by(circle_id=circle_id, status=models.MembershipStatus.active)
        .count()
    )
    if active_count >= circle.member_capacity:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This circle is already full")

    if circle.open_join:
        membership = models.Membership(
            circle_id=circle_id, user_id=current_user.id, status=models.MembershipStatus.active
        )
        db.add(membership)
        db.commit()
        db.refresh(membership)
        return membership

    # Default path: pending + Groq-generated track record summary for the admin.
    stats = compute_user_stats(db, current_user)
    summary = generate_join_summary(stats)

    membership = models.Membership(
        circle_id=circle_id,
        user_id=current_user.id,
        status=models.MembershipStatus.pending,
        ai_summary=summary,
        ai_summary_generated_at=datetime.utcnow(),
    )
    db.add(membership)
    db.flush()

    db.add(
        models.Notification(
            user_id=circle.created_by,
            type="new_join_request",
            title="New Join Request",
            body=f"{current_user.full_name} requested to join '{circle.name}'.",
        )
    )
    db.commit()
    db.refresh(membership)
    return membership


@router.get("/{circle_id}/join-requests", response_model=List[schemas.JoinRequestOut])
def list_join_requests(
    circle_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    circle = _get_circle_or_404(db, circle_id)
    _require_admin(circle, current_user)

    pending = db.query(models.Membership).filter_by(circle_id=circle_id, status=models.MembershipStatus.pending).all()
    return [
        schemas.JoinRequestOut(
            membership_id=m.id,
            user=schemas.UserOut.model_validate(m.user),
            ai_summary=m.ai_summary,
            requested_at=m.joined_at,
        )
        for m in pending
    ]


def _maybe_finalize_payout_order(db: Session, circle: models.Circle):
    active_memberships = (
        db.query(models.Membership).filter_by(circle_id=circle.id, status=models.MembershipStatus.active).all()
    )
    if len(active_memberships) < circle.member_capacity or circle.status != models.CircleStatus.forming:
        return

    if circle.payout_order == models.PayoutOrderType.random:
        random.shuffle(active_memberships)
    else:
        active_memberships.sort(key=lambda m: m.payout_position or 0)

    for i, m in enumerate(active_memberships):
        m.payout_position = i

    circle.status = models.CircleStatus.active
    db.commit()


@router.post("/{circle_id}/join-requests/{user_id}/approve", response_model=schemas.MembershipOut)
def approve_join_request(
    circle_id: int,
    user_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    circle = _get_circle_or_404(db, circle_id)
    _require_admin(circle, current_user)

    membership = (
        db.query(models.Membership)
        .filter_by(circle_id=circle_id, user_id=user_id, status=models.MembershipStatus.pending)
        .first()
    )
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending request for this user")

    active_count = (
        db.query(models.Membership).filter_by(circle_id=circle_id, status=models.MembershipStatus.active).count()
    )
    membership.status = models.MembershipStatus.active
    if circle.payout_order == models.PayoutOrderType.sequential:
        membership.payout_position = active_count

    db.add(
        models.Notification(
            user_id=user_id,
            type="join_approved",
            title="You're in!",
            body=f"Your request to join '{circle.name}' was approved.",
        )
    )
    db.commit()

    _maybe_finalize_payout_order(db, circle)

    db.refresh(membership)
    return membership


@router.post("/{circle_id}/join-requests/{user_id}/deny")
def deny_join_request(
    circle_id: int,
    user_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    circle = _get_circle_or_404(db, circle_id)
    _require_admin(circle, current_user)

    membership = (
        db.query(models.Membership)
        .filter_by(circle_id=circle_id, user_id=user_id, status=models.MembershipStatus.pending)
        .first()
    )
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending request for this user")

    membership.status = models.MembershipStatus.denied
    db.commit()
    return {"ok": True}


@router.get("/{circle_id}/contributions", response_model=List[schemas.ContributionOut])
def list_contributions(circle_id: int, db: Session = Depends(get_db)):
    _get_circle_or_404(db, circle_id)
    return (
        db.query(models.Contribution)
        .filter_by(circle_id=circle_id)
        .order_by(models.Contribution.paid_at.desc())
        .all()
    )


@router.post("/{circle_id}/contributions", response_model=schemas.ContributionOut, status_code=status.HTTP_201_CREATED)
def make_contribution(
    circle_id: int,
    payload: schemas.ContributionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    circle = _get_circle_or_404(db, circle_id)

    if not verify_pin(payload.pin, current_user.pin_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect PIN")

    membership = (
        db.query(models.Membership)
        .filter_by(circle_id=circle_id, user_id=current_user.id, status=models.MembershipStatus.active)
        .first()
    )
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You're not an active member of this circle")

    wallet = current_user.wallet
    if wallet.balance < circle.contribution_amount:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Insufficient wallet balance — fund your wallet first")

    wallet.balance -= circle.contribution_amount
    circle.total_saved += circle.contribution_amount

    contribution = models.Contribution(
        circle_id=circle_id,
        user_id=current_user.id,
        amount=circle.contribution_amount,
        status=models.ContributionStatus.paid,
    )
    db.add(contribution)
    db.add(
        models.Transaction(
            wallet_id=wallet.id,
            type=models.TransactionType.contribution,
            amount=-circle.contribution_amount,
            status=models.TransactionStatus.success,
            reference=f"CONTRIB-{circle_id}-{current_user.id}",
        )
    )
    db.commit()
    db.refresh(contribution)
    return contribution


@router.post("/{circle_id}/payouts/{user_id}/mark-paid")
def mark_payout_paid(
    circle_id: int,
    user_id: int,
    payload: schemas.MarkPayoutPaidRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    circle = _get_circle_or_404(db, circle_id)
    _require_admin(circle, current_user)

    if not verify_pin(payload.pin, current_user.pin_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect PIN")

    recipient = db.get(models.User, user_id)
    if not recipient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient not found")

    payout = models.Payout(
        circle_id=circle_id,
        user_id=user_id,
        amount=circle.cycle_goal,
        status=models.PayoutStatus.paid,
        paid_at=datetime.utcnow(),
    )
    db.add(payout)

    recipient.wallet.balance += circle.cycle_goal
    db.add(
        models.Transaction(
            wallet_id=recipient.wallet.id,
            type=models.TransactionType.payout,
            amount=circle.cycle_goal,
            status=models.TransactionStatus.success,
            reference=f"PAYOUT-{circle_id}-{user_id}",
        )
    )
    circle.current_turn_index += 1
    circle.total_saved = 0  # new cycle begins

    db.add(
        models.Notification(
            user_id=user_id,
            type="payout_available",
            title="Payout Available",
            body=f"Your payout of NGN {circle.cycle_goal:,.0f} from '{circle.name}' has been sent.",
        )
    )
    db.commit()
    return {"ok": True}
