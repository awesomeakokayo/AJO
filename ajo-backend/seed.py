"""
Quick demo-data seeder for sprint rehearsal. Run from ajo-backend/:
    python seed.py

Creates 3 demo users (PIN: 1234), makes the first one an admin, and one
active circle so the app isn't empty when you're testing or demoing.
"""

from app.database import Base, SessionLocal, engine
from app import models
from app.security import hash_pin

Base.metadata.create_all(bind=engine)
db = SessionLocal()

demo_users = [
    {"full_name": "Amina Okoro", "phone": "08010000001", "email": "amina@example.com", "is_admin": True},
    {"full_name": "Kunle Adebayo", "phone": "08010000002", "email": "kunle@example.com", "is_admin": False},
    {"full_name": "Sade Olawale", "phone": "08010000003", "email": "sade@example.com", "is_admin": False},
]

created = []
for u in demo_users:
    existing = db.query(models.User).filter_by(phone=u["phone"]).first()
    if existing:
        created.append(existing)
        continue
    user = models.User(
        full_name=u["full_name"],
        phone=u["phone"],
        email=u["email"],
        is_admin=u["is_admin"],
        pin_hash=hash_pin("1234"),
        trust_score=98,
        verification_status=models.VerificationStatus.verified,
    )
    db.add(user)
    db.flush()
    db.add(models.Wallet(user_id=user.id, balance=200_000))
    created.append(user)

db.commit()

amina = created[0]
circle = db.query(models.Circle).filter_by(name="Osun Savings Circle").first()
if not circle:
    circle = models.Circle(
        name="Osun Savings Circle",
        created_by=amina.id,
        contribution_amount=50_000,
        frequency=models.CircleFrequency.monthly,
        member_capacity=10,
        payout_order=models.PayoutOrderType.random,
        cycle_goal=500_000,
        status=models.CircleStatus.active,
    )
    db.add(circle)
    db.flush()
    db.add(
        models.Membership(
            circle_id=circle.id, user_id=amina.id, status=models.MembershipStatus.active, payout_position=0
        )
    )
    db.commit()

print(f"Seeded {len(created)} users (PIN: 1234, admin = {amina.phone}) and circle '{circle.name}' (id={circle.id}).")
