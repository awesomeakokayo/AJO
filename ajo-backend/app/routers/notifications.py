from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=List[schemas.NotificationOut])
def list_notifications(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(models.Notification)
        .filter_by(user_id=current_user.id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notif = db.query(models.Notification).filter_by(id=notification_id, user_id=current_user.id).first()
    if not notif:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    notif.read = True
    db.commit()
    return {"ok": True}
