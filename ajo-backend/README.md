# àjó Backend

FastAPI backend for àjó, split into two clearly-owned slices in one shared repo.

## Who owns what

| Area | Files | Owner |
|---|---|---|
| Signup, login, PIN | `app/routers/auth.py` | Auth/KYC dev |
| Profile, NIN/BVN/selfie submission | `app/routers/users.py` | Auth/KYC dev |
| Verification queue (approve/reject) | `app/routers/admin.py` | Auth/KYC dev |
| Circles, join review, contributions, payouts | `app/routers/circles.py` | Circles/Wallet dev |
| Wallet, ALATPay funding/withdrawal | `app/routers/wallet.py` | Circles/Wallet dev |
| Invites | `app/routers/invites.py` | Circles/Wallet dev |
| Notifications | `app/routers/notifications.py` | Circles/Wallet dev |
| `app/models.py` | shared file — split into two clearly-commented sections (`User`/`VerificationDoc` vs. everything else). Coordinate before changing the other person's section. |

The only thing connecting the two slices is `user_id` (a plain foreign key — the circles/wallet tables never modify `users`) and the shared `JWT_SECRET` (auth issues tokens, everything else just verifies them via `app/deps.py`).

## Running locally

```bash
python -m venv venv
source venv/bin/activate          # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env              # defaults to a local SQLite file, no setup needed
python seed.py                    # creates 3 demo users (PIN: 1234) + 1 demo circle
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/docs` — every endpoint is testable from there. Log in via `/auth/login`, click "Authorize" in the top right with the returned token, and you've got an authenticated session for every other endpoint, regardless of who owns it.

## Demo admin account

`seed.py` makes `08010000001` (Amina Okoro, PIN `1234`) an admin. Set `ADMIN_PHONES` in `.env` to add your own real test number — any phone number in that comma-separated list is auto-promoted to admin on signup.

## Why no Alembic (yet)

For a sprint this short, migrations between two people editing the same models file will cost more time than they save. `Base.metadata.create_all()` runs on every startup and creates any tables that don't exist yet — it does **not** alter existing tables. If you change a column on a model, the simplest fix during the sprint is:

```bash
rm ajo.db && python seed.py
```

This only matters for local dev. The shared Render Postgres environment should get reset/reseeded the same way whenever a schema change merges to `main`, since all the data in it is synthetic demo data anyway. Move to Alembic once this is past the buildathon and holding real user data.

## Deployment (shared environment)

1. One Render Postgres instance.
2. One Render Web Service running this repo (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
3. Env vars on that service: `DATABASE_URL` (from the Render Postgres), `JWT_SECRET`, `ADMIN_PHONES`, `GROQ_API_KEY` (optional), `ALATPAY_API_KEY`.
4. The Expo app points `EXPO_PUBLIC_API_URL` at that Render service's URL. Anything merged to `main` is live there for both of you and for the frontend.

## AI feature

`app/services/groq_service.py` generates the join-request track record summary an admin sees when reviewing a request to join a circle. If `GROQ_API_KEY` isn't set (or the call fails), it falls back to a deterministic template — the feature never breaks the demo even with no network or no key configured.

## What's stubbed vs. real

- **KYC verification** is a real manual admin-approval flow (queue → approve/reject), not auto-approved. NIN/BVN/selfie values are stored but not checked against a real government API — that's the explicitly-deferred piece per the PRD.
- **ALATPay** (`app/services/alatpay_service.py`) returns fake checkout URLs/references. Swap the function bodies for real ALATPay API calls when sandbox credentials are ready — nothing else in the app needs to change.
- **Contributions and payouts** are internal wallet ledger movements only — no ALATPay call needed for those, since the money's already inside the platform.
