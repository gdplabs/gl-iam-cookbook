"""Background Refresh Demo - Proactive Token Refresh Pattern.

This demo shows the background refresh pattern, ideal for:
- Long-running agents with sparse API calls
- Agents that might not call get_valid_token() for extended periods
- Scenarios where you want tokens always fresh, even during idle time

How it works:
1. Use auto_refresh_context() to start a background task
2. The background task periodically checks if tokens need refresh
3. Tokens are proactively refreshed before they expire
4. When you call get_valid_token(), the token is always fresh

Run with: uv run python background_demo.py
"""

from __future__ import annotations

import asyncio
import os
import signal
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from gl_iam import (
    AuditEvent,
    AuthToken,
    IAMGateway,
    TokenManager,
    TokenManagerConfig,
    RefreshStrategy,
    User,
)
from gl_iam.core.types.result import Result

# Load environment variables
load_dotenv()

# Configuration
MOCK_TOKEN_TTL = int(os.getenv("MOCK_TOKEN_TTL_SECONDS", "60"))
ORGANIZATION_ID = os.getenv("ORGANIZATION_ID", "org-demo-123")
VERBOSE = os.getenv("VERBOSE_LOGGING", "true").lower() == "true"


class MockUserStore:
    """Minimal mock user store to satisfy IAMGateway requirements."""

    async def get_user(self, user_id: str, organization_id: str | None = None) -> User | None:
        return None

    async def get_user_by_email(self, email: str, organization_id: str | None = None) -> User | None:
        return None


def log(message: str, prefix: str = "") -> None:
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    prefix_str = f"[{prefix}] " if prefix else ""
    print(f"[{timestamp}] {prefix_str}{message}")


def create_mock_token(ttl_seconds: int = MOCK_TOKEN_TTL) -> AuthToken:
    """Create a mock token with specified TTL."""
    now = datetime.now(timezone.utc)
    return AuthToken(
        access_token=f"mock_access_{now.timestamp()}",
        token_type="Bearer",
        expires_at=now + timedelta(seconds=ttl_seconds),
        refresh_token=f"mock_refresh_{now.timestamp()}",
        refresh_expires_at=now + timedelta(seconds=ttl_seconds * 24),
        metadata={"issued_at": now.isoformat()},
    )


async def mock_refresh_callback(
    organization_id: str,
    current_token: AuthToken | None,
) -> Result[AuthToken]:
    """Mock refresh callback."""
    log("Refreshing token...", prefix="REFRESH")
    await asyncio.sleep(0.3)
    new_token = create_mock_token()
    log(f"New token expires at: {new_token.expires_at.strftime('%H:%M:%S')}", prefix="REFRESH")
    return Result.ok(new_token)


def audit_callback(event: AuditEvent) -> None:
    """Handle audit events from TokenManager."""
    if VERBOSE:
        # event.event_type is already a string (AuditEventType enum value)
        event_type = event.event_type.value if hasattr(event.event_type, 'value') else event.event_type
        log(f"{event_type}: {event.details}", prefix="AUDIT")


def format_time_remaining(token: AuthToken) -> str:
    """Format time remaining until expiry."""
    if token.expires_at is None:
        return "no expiry"
    remaining = (token.expires_at - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        return "EXPIRED"
    return f"{remaining:.1f}s"


async def simulate_sparse_api_calls(manager: TokenManager) -> None:
    """Simulate an agent with sparse API calls.

    This represents a deep research agent that:
    1. Processes data for a while (no API calls)
    2. Makes an API call
    3. Processes more data
    4. Repeat
    """
    log("Starting sparse API call simulation...")
    log("(Notice how background refresh keeps tokens fresh even during idle periods)")
    print()

    # Simulate 3 rounds of work
    for round_num in range(1, 4):
        # Simulate long processing time (no API calls)
        processing_time = MOCK_TOKEN_TTL * 0.6  # Process for 60% of token TTL
        log(f"Round {round_num}: Processing data for {processing_time:.0f}s (no API calls)...", prefix="AGENT")

        # Check token periodically during processing
        check_interval = 10
        elapsed = 0
        while elapsed < processing_time:
            await asyncio.sleep(min(check_interval, processing_time - elapsed))
            elapsed += check_interval

            # Show current token status
            if manager.current_token:
                time_left = format_time_remaining(manager.current_token.auth_token)
                log(f"  [Status] Processing... Token: {time_left}, Background refresh: {manager.is_background_refresh_running}", prefix="AGENT")

        # Now make an API call
        result = await manager.get_valid_token()
        if result.is_err:
            log(f"ERROR: {result.error.message}", prefix="AGENT")
            break

        token = result.value
        log(f"Round {round_num}: Making API call with token ({format_time_remaining(token)})", prefix="AGENT")

        # Simulate API call
        await asyncio.sleep(0.5)
        log(f"Round {round_num}: API call successful!", prefix="AGENT")
        print()


async def main() -> None:
    """Demonstrate background token refresh pattern."""
    print("=" * 60)
    print("TokenManager Demo: Background Refresh Pattern")
    print("=" * 60)
    print()
    print("Configuration:")
    print(f"  - Token TTL: {MOCK_TOKEN_TTL} seconds")
    print(f"  - Background check interval: 10 seconds")
    print(f"  - Refresh threshold: 25%")
    print(f"  - Organization: {ORGANIZATION_ID}")
    print()

    # Create gateway and initial token
    mock_user_store = MockUserStore()
    gateway = IAMGateway(user_store=mock_user_store)
    initial_token = create_mock_token()
    log(f"Initial token expires at: {initial_token.expires_at.strftime('%H:%M:%S')}")

    # Configure for background refresh
    config = TokenManagerConfig(
        refresh_threshold_ratio=0.25,
        check_interval_seconds=10.0,  # Check every 10 seconds
        max_retry_attempts=3,
        refresh_strategy=RefreshStrategy.BACKGROUND,
    )

    # Create TokenManager
    manager = TokenManager(
        gateway=gateway,
        organization_id=ORGANIZATION_ID,
        initial_token=initial_token,
        config=config,
        refresh_callback=mock_refresh_callback,
        audit_callback=audit_callback,
    )

    print()
    print("-" * 60)

    # Use the auto_refresh_context for automatic background refresh
    try:
        async with manager.auto_refresh_context():
            log("Background refresh started", prefix="SYSTEM")
            print()

            # Run the simulation
            await simulate_sparse_api_calls(manager)

    except asyncio.CancelledError:
        log("Demo cancelled", prefix="SYSTEM")

    print("-" * 60)
    print()
    print("Demo completed!")
    print(f"Total token refreshes: {manager.refresh_count}")
    print()
    print("Key takeaway: Background refresh keeps tokens fresh even during")
    print("long processing periods when you're not making API calls.")
    print("This is ideal for deep research agents that run for hours.")


if __name__ == "__main__":
    asyncio.run(main())
