"""Redis-backed nonce store for HMAC replay protection.

The partner includes a `nonce` in the signed payload. This store uses SETNX
with TTL to reject any second appearance of the same (consumer_key, nonce).
"""

from __future__ import annotations

from redis.asyncio import Redis

_PREFIX = "sso:nonce:"


class NonceStore:
    def __init__(self, redis: Redis, ttl_seconds: int):
        self._redis = redis
        self._ttl = ttl_seconds

    async def claim(self, consumer_key: str, nonce: str) -> bool:
        """Return True if the nonce is fresh; False if already seen."""
        ok = await self._redis.set(
            f"{_PREFIX}{consumer_key}:{nonce}",
            "1",
            ex=self._ttl,
            nx=True,
        )
        return bool(ok)
