import asyncio
import logging
import time

import httpx

from app.integrations.nomba.config import nomba_settings
from app.integrations.nomba.schemas import NombaTokenResponse

logger = logging.getLogger(__name__)

TOKEN_REFRESH_MARGIN = 300  # refresh 5 minutes before expiry


class NombaTokenManager:
    """Single-instance OAuth2 token manager for Nomba.

    Holds tokens in memory with an asyncio.Lock to prevent concurrent
    re-authentication (Nomba's guidance: multiple concurrent auth requests
    can cause 401s). For multi-worker deployments this lock is per-process
    only — if workers are scaled horizontally, replace with a shared lock
    (Redis, etc.).
    """

    def __init__(self):
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        if self._access_token and time.time() < self._expires_at - TOKEN_REFRESH_MARGIN:
            return self._access_token

        async with self._lock:
            if self._access_token and time.time() < self._expires_at - TOKEN_REFRESH_MARGIN:
                return self._access_token

            if self._refresh_token and time.time() < self._expires_at:
                await self._refresh()
            else:
                await self._issue()

        return self._access_token

    async def _issue(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{nomba_settings.base_url}/v1/auth/token/issue",
                headers={"accountId": nomba_settings.account_id},
                json={
                    "grant_type": "client_credentials",
                    "client_id": nomba_settings.client_id,
                    "client_secret": nomba_settings.client_secret,
                },
            )
            resp.raise_for_status()
            data = NombaTokenResponse(**resp.json())
            self._store(data)

    async def _refresh(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{nomba_settings.base_url}/v1/auth/token/issue",
                headers={"accountId": nomba_settings.account_id},
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
            )
            resp.raise_for_status()
            data = NombaTokenResponse(**resp.json())
            self._store(data)

    def _store(self, data: NombaTokenResponse):
        self._access_token = data.access_token
        self._refresh_token = data.refresh_token
        self._expires_at = time.time() + data.expires_in

    async def invalidate(self):
        self._access_token = None
        self._refresh_token = None
        self._expires_at = 0.0


token_manager = NombaTokenManager()
