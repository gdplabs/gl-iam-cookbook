"""Per-consumer_key rate limiting.

SlowAPI's decorator-based API doesn't play well with FastAPI pydantic body
binding (the decorator's `*args, **kwargs` signature causes FastAPI to
misclassify body params as query params). We use slowapi's underlying
`limits` library directly with an async MovingWindowRateLimiter keyed
on `consumer_key` (fallback: client IP).
"""

from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException, Request
from limits import parse
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter

from glchat_backend import audit

_storage = MemoryStorage()
_strategy = MovingWindowRateLimiter(_storage)


async def _key(request: Request) -> str:
    if request.method == "POST":
        try:
            raw = await request.body()
            if raw:
                data = json.loads(raw)
                if (ck := data.get("consumer_key")):
                    # cache body so route handler can still read it
                    async def receive_cached(_r=raw):
                        return {"type": "http.request", "body": _r, "more_body": False}
                    request._receive = receive_cached  # type: ignore[assignment]
                    return f"ck:{ck}"
        except (ValueError, KeyError):
            pass
    return f"ip:{request.client.host if request.client else 'unknown'}"


def _check_rate_limit_sync(limit_str: str, key: str) -> bool:
    """Synchronous convenience — not used; see _check_rate_limit."""
    raise NotImplementedError


async def check(request: Request, limit_str: str) -> None:
    from gl_iam.core.types.audit import AuditEventType, AuditSeverity

    key = await _key(request)
    limit = parse(limit_str)
    if not await _strategy.hit(limit, key):
        audit.emit(
            event_type=AuditEventType.LOGIN_ERROR_LIMIT_EXCEED,
            severity=AuditSeverity.WARNING,
            sso_event="rate_limited",
            message=f"Rate limit {limit_str} hit on {request.url.path}",
            error_code="RATE_LIMITED",
            key=key,
            path=request.url.path,
        )
        raise HTTPException(429, f"Rate limit exceeded: {limit_str}")


def register(app: FastAPI) -> None:
    @app.middleware("http")
    async def _noop(request: Request, call_next):
        return await call_next(request)
