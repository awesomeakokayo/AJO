import asyncio
import logging

import httpx

from app.integrations.nomba.auth import token_manager
from app.integrations.nomba.config import nomba_settings

logger = logging.getLogger(__name__)


class NombaClientError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Nomba API {status_code}: {message}")


class NombaClient:
    """Thin httpx.AsyncClient wrapper that injects auth and accountId headers."""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)

    async def request(self, method: str, path: str, json: dict | None = None) -> dict:
        url = f"{nomba_settings.base_url}{path}"
        token = await token_manager.get_token()

        for attempt in range(2):
            resp = await self._client.request(
                method,
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "accountId": nomba_settings.account_id,
                    "Content-Type": "application/json",
                },
                json=json,
            )

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "1"))
                logger.warning("Nomba rate-limited, retrying after %ds", retry_after)
                await asyncio.sleep(retry_after)
                continue

            if resp.status_code == 401 and attempt == 0:
                logger.info("Nomba returned 401, invalidating token and retrying")
                await token_manager.invalidate()
                token = await token_manager.get_token()
                continue

            if resp.status_code >= 400:
                logger.error(
                    "Nomba API error: %s %s -> %s %s",
                    method, path, resp.status_code, resp.text[:500],
                )
                raise NombaClientError(resp.status_code, resp.text[:500])

            return resp.json()

        raise NombaClientError(429, "Exceeded max retries after rate-limit")

    async def get(self, path: str) -> dict:
        return await self.request("GET", path)

    async def post(self, path: str, json: dict) -> dict:
        return await self.request("POST", path, json=json)

    async def close(self):
        await self._client.aclose()


nomba_client = NombaClient()
