"""Redis-backed one-time token store.

Provides atomic `consume` via GETDEL so a token can only ever be used once —
the replacement for the in-memory dict in `sso-token-exchange/sso_receiver.py`.
"""

from __future__ import annotations

import json
import secrets

from redis.asyncio import Redis

_PREFIX = "sso:otk:"


class OneTimeTokenStore:
    def __init__(self, redis: Redis, ttl_seconds: int):
        self._redis = redis
        self._ttl = ttl_seconds

    async def issue(self, payload: dict) -> str:
        token = secrets.token_urlsafe(32)
        await self._redis.set(_PREFIX + token, json.dumps(payload), ex=self._ttl)
        return token

    async def consume(self, token: str) -> dict | None:
        raw = await self._redis.execute_command("GETDEL", _PREFIX + token)
        if raw is None:
            return None
        return json.loads(raw)
