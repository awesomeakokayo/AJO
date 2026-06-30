from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import admin, auth, circles, invites, nomba_webhooks, notifications, users, wallet

# Sprint speed: create tables directly instead of running migrations.
# If you change a model's columns, drop ajo.db locally and re-run seed.py
# rather than trying to migrate it — see README for why.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="àjó API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before this goes anywhere near production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth/KYC dev's routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin.router)

# Circles/Wallet/Notifications dev's routers
app.include_router(circles.router)
app.include_router(wallet.router)
app.include_router(invites.router)
app.include_router(notifications.router)

# Nomba Payments integration router
app.include_router(nomba_webhooks.router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "ajo-api"}
