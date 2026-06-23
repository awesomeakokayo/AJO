from sqlalchemy.orm import Session

from app import models


def compute_user_stats(db: Session, user: models.User) -> dict:
    """Aggregate stats used by the Groq-generated join-request summary
    (circles dev) and could equally back a Trust Score breakdown on
    Profile (auth dev). Shared here so neither side has to recompute it."""
    completed_memberships = (
        db.query(models.Membership)
        .join(models.Circle)
        .filter(
            models.Membership.user_id == user.id,
            models.Circle.status == models.CircleStatus.completed,
        )
        .count()
    )
    contributions = db.query(models.Contribution).filter_by(user_id=user.id).all()
    total = len(contributions)
    on_time = len([c for c in contributions if c.status == models.ContributionStatus.paid])
    late = len([c for c in contributions if c.status == models.ContributionStatus.late])
    missed = len([c for c in contributions if c.status == models.ContributionStatus.missed])
    on_time_rate = round((on_time / total) * 100, 1) if total else 100.0
    total_saved = sum(c.amount for c in contributions)

    return {
        "name": user.full_name,
        "trust_score": user.trust_score,
        "circles_completed": completed_memberships,
        "on_time_rate": on_time_rate,
        "late_payments": late,
        "missed_payments": missed,
        "total_saved": total_saved,
    }
