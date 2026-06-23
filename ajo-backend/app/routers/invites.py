from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_user
from app.services.groq_service import generate_join_summary
from app.services.user_stats import compute_user_stats

router = APIRouter(tags=["invites"])


@router.post("/circles/{circle_id}/invites", response_model=schemas.InviteOut, status_code=status.HTTP_201_CREATED)
def create_invite(
    circle_id: int,
    payload: schemas.InviteCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    circle = db.get(models.Circle, circle_id)
    if not circle:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Circle not found")

    is_member = (
        db.query(models.Membership)
        .filter_by(circle_id=circle_id, user_id=current_user.id, status=models.MembershipStatus.active)
        .first()
    )
    if not is_member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only active members can invite to this circle")

    invite = models.Invite(circle_id=circle_id, invited_by=current_user.id, invitee_contact=payload.invitee_contact)
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


@router.get("/invites/{code}", response_model=schemas.InvitePreview)
def preview_invite(code: str, db: Session = Depends(get_db)):
    invite = db.query(models.Invite).filter_by(code=code).first()
    if not invite or invite.status == models.InviteStatus.expired:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found or expired")
    inviter = db.get(models.User, invite.invited_by)
    return schemas.InvitePreview(circle=invite.circle, invited_by=inviter)


@router.post("/invites/{code}/accept", response_model=schemas.MembershipOut, status_code=status.HTTP_201_CREATED)
def accept_invite(code: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    invite = db.query(models.Invite).filter_by(code=code).first()
    if not invite or invite.status == models.InviteStatus.expired:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found or expired")

    circle = invite.circle
    existing = db.query(models.Membership).filter_by(circle_id=circle.id, user_id=current_user.id).first()
    if existing and existing.status in (models.MembershipStatus.active, models.MembershipStatus.pending):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Already a member or already requested")

    if circle.open_join:
        membership = models.Membership(circle_id=circle.id, user_id=current_user.id, status=models.MembershipStatus.active)
    else:
        stats = compute_user_stats(db, current_user)
        summary = generate_join_summary(stats)
        membership = models.Membership(
            circle_id=circle.id,
            user_id=current_user.id,
            status=models.MembershipStatus.pending,
            ai_summary=summary,
            ai_summary_generated_at=datetime.utcnow(),
        )

    invite.status = models.InviteStatus.accepted
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership
