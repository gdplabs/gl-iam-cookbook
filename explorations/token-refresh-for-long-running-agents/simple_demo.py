"""Simple TokenManager Demo - On-Demand Refresh Pattern.

This demo shows the basic usage of TokenManager with on-demand token refresh.
It's the recommended pattern for most applications that make frequent API calls.

How it works:
1. TokenManager wraps your auth token
2. When you call get_valid_token(), it checks if refresh is needed
3. If token is in the "refresh zone" (default: 25% TTL remaining), it refreshes
4. Otherwise, it returns the current valid token

Run with: uv run python simple_demo.py
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv

from gl_iam import (
    AuthToken,
    IAMGateway,
    TokenManager,
    TokenManagerConfig,
    User,
)
from gl_iam.core.types.result import Result

# Load environment variables
load_dotenv()

# Configuration from environment
MOCK_TOKEN_TTL = int(os.getenv("MOCK_TOKEN_TTL_SECONDS", "60"))
ORGANIZATION_ID = os.getenv("ORGANIZATION_ID", "org-demo-123")
VERBOSE = os.getenv("VERBOSE_LOGGING", "true").lower() == "true"


class MockUserStore:
    """Minimal mock user store to satisfy IAMGateway requirements.

    In production, you would use a real provider like StackAuthProvider,
    KeycloakProvider, or PostgreSQLProvider.
    """

    async def get_user(self, user_id: str, organization_id: str | None = None) -> User | None:
        """Mock get_user - not used in this demo."""
        return None

    async def get_user_by_email(self, email: str, organization_id: str | None = None) -> User | None:
        """Mock get_user_by_email - not used in this demo."""
        return None


def log(message: str) -> None:
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def create_mock_token(ttl_seconds: int = MOCK_TOKEN_TTL, show_tokens: bool = False) -> AuthToken:
    """Create a mock token with specified TTL for demonstration."""
    now = datetime.now(timezone.utc)
    # Generate shorter, more readable token IDs
    token_id = f"{int(now.timestamp()) % 10000:04d}"
    token = AuthToken(
        access_token=f"access_tok_{token_id}",
        token_type="Bearer",
        expires_at=now + timedelta(seconds=ttl_seconds),
        refresh_token=f"refresh_tok_{token_id}",
        refresh_expires_at=now + timedelta(seconds=ttl_seconds * 24),  # Refresh token lasts longer
        metadata={"issued_at": now.isoformat()},
    )
    if show_tokens:
        log(f"  [TOKEN] Created new token pair:")
        log(f"          access_token:  {token.access_token}")
        log(f"          refresh_token: {token.refresh_token}")
        log(f"          expires_at:    {token.expires_at.strftime('%H:%M:%S')}")
    return token


async def mock_refresh_callback(
    organization_id: str,
    current_token: AuthToken | None,
) -> Result[AuthToken]:
    """Mock refresh callback that simulates token refresh.

    In production, this would call your auth provider (Stack Auth, Keycloak, etc.)
    """
    log(f"  [REFRESH] Refreshing token for org: {organization_id}")
    if current_token:
        log(f"  [REFRESH] Old access_token:  {current_token.access_token}")
        log(f"  [REFRESH] Old refresh_token: {current_token.refresh_token}")

    # Simulate network delay
    await asyncio.sleep(0.5)

    # Create new token
    new_token = create_mock_token(show_tokens=True)

    return Result.ok(new_token)


def format_time_remaining(token: AuthToken) -> str:
    """Format the time remaining until token expiry."""
    if token.expires_at is None:
        return "no expiry"

    remaining = (token.expires_at - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        return "EXPIRED"
    return f"{remaining:.1f}s remaining"


async def main() -> None:
    """Demonstrate on-demand token refresh pattern."""
    print("=" * 60)
    print("TokenManager Demo: On-Demand Refresh Pattern")
    print("=" * 60)
    print()
    print(f"Configuration:")
    print(f"  - Token TTL: {MOCK_TOKEN_TTL} seconds")
    print(f"  - Refresh threshold: 25% (refreshes when ~{MOCK_TOKEN_TTL * 0.25:.0f}s remaining)")
    print(f"  - Organization: {ORGANIZATION_ID}")
    print()

    # Create a mock gateway (in production, use a real provider like StackAuthProvider)
    # The gateway requires at least one provider - we use a minimal mock here
    # since we're using a custom refresh_callback for token refresh
    mock_user_store = MockUserStore()
    gateway = IAMGateway(user_store=mock_user_store)

    # Create initial token
    log("Creating initial token...")
    initial_token = create_mock_token(show_tokens=True)

    # Configure TokenManager
    config = TokenManagerConfig(
        refresh_threshold_ratio=0.25,  # Refresh when 25% TTL remains
        max_retry_attempts=3,
        retry_delay_seconds=1.0,
    )

    # Create TokenManager with mock refresh callback
    manager = TokenManager(
        gateway=gateway,
        organization_id=ORGANIZATION_ID,
        initial_token=initial_token,
        config=config,
        refresh_callback=mock_refresh_callback,
    )

    print()
    print("Starting API call simulation...")
    print("(Watch how the token automatically refreshes when approaching expiry)")
    print("-" * 60)

    # Simulate API calls over time
    call_interval = 5  # seconds between API calls
    total_calls = 20

    for i in range(1, total_calls + 1):
        # Get a valid token (this is what you'd do before every API call)
        result = await manager.get_valid_token()

        if result.is_err:
            log(f"ERROR: {result.error.message}")
            break

        token = result.value
        time_remaining = format_time_remaining(token)

        # Show token status
        log(f"API Call #{i}: Using token ({time_remaining})")

        if VERBOSE:
            print(f"         Token: {token.access_token[:20]}...")
            print(f"         Refreshes so far: {manager.refresh_count}")

        # Wait before next call
        if i < total_calls:
            await asyncio.sleep(call_interval)

    print("-" * 60)
    print()
    print("Demo completed!")
    print(f"Total API calls: {total_calls}")
    print(f"Total token refreshes: {manager.refresh_count}")
    print()
    print("Key takeaway: You just call get_valid_token() before each API call.")
    print("TokenManager handles all the refresh logic automatically!")


if __name__ == "__main__":
    asyncio.run(main())
