"""Deep Research Agent Demo - Full Production-Like Simulation.

This demo simulates a complete deep research AI agent that:
- Runs for extended periods (hours in production, compressed in demo)
- Performs multiple research phases (gathering, analyzing, synthesizing)
- Uses audit logging for observability
- Handles errors with force_refresh()
- Demonstrates graceful shutdown

This represents how you would use TokenManager in a real AI agent
that performs long-running tasks like deep research, data processing,
or continuous monitoring.

Run with: uv run python deep_research_agent.py
"""

from __future__ import annotations

import asyncio
import os
import random
import signal
import sys
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from dotenv import load_dotenv

from gl_iam import (
    AuditEvent,
    AuditEventType,
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
MOCK_API_ENDPOINT = os.getenv("MOCK_API_ENDPOINT", "https://api.example.com/v1")


class MockUserStore:
    """Minimal mock user store to satisfy IAMGateway requirements."""

    async def get_user(self, user_id: str, organization_id: str | None = None) -> User | None:
        return None

    async def get_user_by_email(self, email: str, organization_id: str | None = None) -> User | None:
        return None


class ResearchPhase(str, Enum):
    """Phases of a deep research task."""
    GATHERING = "gathering"
    ANALYZING = "analyzing"
    SYNTHESIZING = "synthesizing"
    REPORTING = "reporting"


class DeepResearchAgent:
    """A simulated deep research AI agent using TokenManager.

    This agent demonstrates best practices for:
    - Long-running operations with automatic token refresh
    - Audit logging for observability
    - Error handling and recovery
    - Graceful shutdown
    """

    def __init__(
        self,
        token_manager: TokenManager,
        task_id: str = "research-001",
    ) -> None:
        self.token_manager = token_manager
        self.task_id = task_id
        self.current_phase = ResearchPhase.GATHERING
        self.api_calls_made = 0
        self.errors_handled = 0
        self._shutdown_event = asyncio.Event()
        self._running = False

    def log(self, message: str, level: str = "INFO") -> None:
        """Log a message with context."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        phase_str = f"[{self.current_phase.value.upper():^12}]"
        print(f"[{timestamp}] [{level:^5}] {phase_str} {message}")

    async def make_api_call(self, endpoint: str, description: str) -> dict[str, Any]:
        """Make an API call with automatic token management.

        This demonstrates the pattern for API calls in a long-running agent.
        """
        # Get valid token (automatically refreshes if needed)
        result = await self.token_manager.get_valid_token()

        if result.is_err:
            self.log(f"Token error: {result.error.message}", level="ERROR")
            # Try force refresh on token error
            self.log("Attempting force refresh...", level="WARN")
            result = await self.token_manager.force_refresh()
            if result.is_err:
                raise RuntimeError(f"Cannot get valid token: {result.error.message}")
            self.errors_handled += 1

        token = result.value
        self.api_calls_made += 1

        # Simulate API call
        headers = {"Authorization": f"{token.token_type} {token.access_token}"}

        if VERBOSE:
            time_remaining = self._format_time_remaining(token)
            self.log(f"API Call #{self.api_calls_made}: {description} (token: {time_remaining})")

        # Simulate network latency
        await asyncio.sleep(random.uniform(0.1, 0.5))

        # Simulate occasional API errors (5% chance)
        if random.random() < 0.05:
            self.log(f"API returned 401 - forcing token refresh", level="WARN")
            await self.token_manager.force_refresh()
            self.errors_handled += 1

        return {"status": "success", "data": f"response_{self.api_calls_made}"}

    def _format_time_remaining(self, token: AuthToken) -> str:
        """Format time remaining until token expiry."""
        if token.expires_at is None:
            return "no expiry"
        remaining = (token.expires_at - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            return "EXPIRED"
        return f"{remaining:.1f}s"

    async def _run_gathering_phase(self) -> list[str]:
        """Phase 1: Gather research data from multiple sources."""
        self.current_phase = ResearchPhase.GATHERING
        self.log("Starting data gathering phase...")

        sources = ["web_search", "academic_db", "news_api", "social_media"]
        gathered_data = []

        for source in sources:
            if self._shutdown_event.is_set():
                break

            self.log(f"Fetching data from {source}...")
            await self.make_api_call(f"/data/{source}", f"Fetch from {source}")

            # Simulate processing time
            await asyncio.sleep(random.uniform(2, 5))
            gathered_data.append(f"data_from_{source}")

        self.log(f"Gathering complete. Sources: {len(gathered_data)}")
        return gathered_data

    async def _run_analyzing_phase(self, data: list[str]) -> dict[str, Any]:
        """Phase 2: Analyze gathered data."""
        self.current_phase = ResearchPhase.ANALYZING
        self.log(f"Starting analysis of {len(data)} data sources...")

        analysis_results = {}

        for i, item in enumerate(data):
            if self._shutdown_event.is_set():
                break

            self.log(f"Analyzing {item} ({i+1}/{len(data)})...")
            await self.make_api_call("/analyze", f"Analyze {item}")

            # Simulate CPU-intensive analysis
            await asyncio.sleep(random.uniform(3, 7))
            analysis_results[item] = {"sentiment": random.uniform(-1, 1), "relevance": random.uniform(0, 1)}

        self.log(f"Analysis complete. Results: {len(analysis_results)}")
        return analysis_results

    async def _run_synthesizing_phase(self, analysis: dict[str, Any]) -> str:
        """Phase 3: Synthesize findings into coherent insights."""
        self.current_phase = ResearchPhase.SYNTHESIZING
        self.log("Starting synthesis phase...")

        # Multiple synthesis iterations
        for iteration in range(3):
            if self._shutdown_event.is_set():
                break

            self.log(f"Synthesis iteration {iteration + 1}/3...")
            await self.make_api_call("/synthesize", f"Synthesis iteration {iteration + 1}")

            # Simulate LLM processing
            await asyncio.sleep(random.uniform(5, 10))

        self.log("Synthesis complete")
        return "synthesized_insights"

    async def _run_reporting_phase(self, insights: str) -> str:
        """Phase 4: Generate final report."""
        self.current_phase = ResearchPhase.REPORTING
        self.log("Generating final report...")

        # Generate report sections
        sections = ["executive_summary", "methodology", "findings", "recommendations"]

        for section in sections:
            if self._shutdown_event.is_set():
                break

            self.log(f"Writing {section}...")
            await self.make_api_call("/generate", f"Generate {section}")
            await asyncio.sleep(random.uniform(2, 4))

        self.log("Report generation complete")
        return f"research_report_{self.task_id}"

    async def run_research(self) -> str | None:
        """Execute the complete research workflow."""
        self._running = True
        self.log("=" * 50)
        self.log(f"Deep Research Agent Started - Task: {self.task_id}")
        self.log("=" * 50)

        try:
            # Phase 1: Gathering
            data = await self._run_gathering_phase()
            if self._shutdown_event.is_set():
                return None

            # Phase 2: Analysis
            analysis = await self._run_analyzing_phase(data)
            if self._shutdown_event.is_set():
                return None

            # Phase 3: Synthesis
            insights = await self._run_synthesizing_phase(analysis)
            if self._shutdown_event.is_set():
                return None

            # Phase 4: Reporting
            report = await self._run_reporting_phase(insights)

            self.log("=" * 50)
            self.log("Research completed successfully!")
            self.log(f"Final report: {report}")
            self.log("=" * 50)

            return report

        except Exception as e:
            self.log(f"Research failed: {e}", level="ERROR")
            raise
        finally:
            self._running = False

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        self.log("Shutdown requested - will stop after current operation", level="WARN")
        self._shutdown_event.set()


def create_mock_token(ttl_seconds: int = MOCK_TOKEN_TTL, show_tokens: bool = False) -> AuthToken:
    """Create a mock token with specified TTL."""
    now = datetime.now(timezone.utc)
    # Generate shorter, more readable token IDs
    token_id = f"{int(now.timestamp()) % 10000:04d}"
    token = AuthToken(
        access_token=f"agent_access_{token_id}",
        token_type="Bearer",
        expires_at=now + timedelta(seconds=ttl_seconds),
        refresh_token=f"agent_refresh_{token_id}",
        refresh_expires_at=now + timedelta(seconds=ttl_seconds * 24),
        metadata={"issued_at": now.isoformat()},
    )
    if show_tokens:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [TOKEN  ] Created new token pair:")
        print(f"[{timestamp}] [TOKEN  ]   access_token:  {token.access_token}")
        print(f"[{timestamp}] [TOKEN  ]   refresh_token: {token.refresh_token}")
        print(f"[{timestamp}] [TOKEN  ]   expires_at:    {token.expires_at.strftime('%H:%M:%S')}")
    return token


async def mock_refresh_callback(
    organization_id: str,
    current_token: AuthToken | None,
) -> Result[AuthToken]:
    """Mock refresh callback."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [TOKENMGR] Token refresh triggered for org: {organization_id}")
    if current_token:
        print(f"[{timestamp}] [TOKENMGR] Old access_token:  {current_token.access_token}")
        print(f"[{timestamp}] [TOKENMGR] Old refresh_token: {current_token.refresh_token}")
    await asyncio.sleep(0.3)
    new_token = create_mock_token(show_tokens=True)
    return Result.ok(new_token)


def create_audit_callback() -> tuple[list[AuditEvent], callable]:
    """Create an audit callback with event storage."""
    events: list[AuditEvent] = []

    def callback(event: AuditEvent) -> None:
        events.append(event)
        if VERBOSE:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            # event.event_type may be enum or string depending on serialization
            event_type = event.event_type.value if hasattr(event.event_type, 'value') else event.event_type
            print(f"[{timestamp}] [AUDIT   ] {event_type}")

    return events, callback


async def main() -> None:
    """Run the deep research agent demo."""
    print("=" * 70)
    print("Deep Research Agent - TokenManager Production Simulation")
    print("=" * 70)
    print()
    print("This demo simulates a production deep research AI agent:")
    print("  - Multiple research phases (gathering → analyzing → synthesizing → reporting)")
    print("  - Automatic token refresh in background")
    print("  - Audit logging for observability")
    print("  - Error handling with force_refresh()")
    print()
    print("Configuration:")
    print(f"  - Token TTL: {MOCK_TOKEN_TTL}s (production would be 1-24 hours)")
    print(f"  - Organization: {ORGANIZATION_ID}")
    print(f"  - API Endpoint: {MOCK_API_ENDPOINT}")
    print()

    # Create gateway and initial token
    mock_user_store = MockUserStore()
    gateway = IAMGateway(user_store=mock_user_store)
    print()
    print("Creating initial token...")
    initial_token = create_mock_token(show_tokens=True)

    # Create audit callback
    audit_events, audit_callback = create_audit_callback()

    # Configure TokenManager for background refresh
    config = TokenManagerConfig(
        refresh_threshold_ratio=0.25,
        check_interval_seconds=10.0,
        max_retry_attempts=3,
        retry_delay_seconds=2.0,
        refresh_strategy=RefreshStrategy.BACKGROUND,
    )

    # Create TokenManager
    token_manager = TokenManager(
        gateway=gateway,
        organization_id=ORGANIZATION_ID,
        initial_token=initial_token,
        config=config,
        refresh_callback=mock_refresh_callback,
        audit_callback=audit_callback,
    )

    # Create agent
    agent = DeepResearchAgent(token_manager)

    # Handle SIGINT for graceful shutdown
    def signal_handler(sig, frame):
        agent.request_shutdown()

    signal.signal(signal.SIGINT, signal_handler)

    print("Press Ctrl+C at any time for graceful shutdown")
    print()
    print("-" * 70)

    try:
        # Run agent with background token refresh
        async with token_manager.auto_refresh_context():
            result = await agent.run_research()

    except asyncio.CancelledError:
        print("\nAgent cancelled")
    except Exception as e:
        print(f"\nAgent error: {e}")

    print("-" * 70)
    print()

    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"  API calls made: {agent.api_calls_made}")
    print(f"  Token refreshes: {token_manager.refresh_count}")
    print(f"  Errors handled: {agent.errors_handled}")
    print(f"  Audit events: {len(audit_events)}")
    print()

    # Audit event breakdown
    if audit_events:
        print("Audit Event Breakdown:")
        event_counts: dict[str, int] = {}
        for event in audit_events:
            event_type = event.event_type.value if hasattr(event.event_type, 'value') else event.event_type
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        for event_type, count in sorted(event_counts.items()):
            print(f"  - {event_type}: {count}")

    print()
    print("Key takeaways:")
    print("  1. TokenManager handled all token refreshes automatically")
    print("  2. The agent focused on research logic, not authentication")
    print("  3. Audit events provide full observability into token lifecycle")
    print("  4. Background refresh kept tokens fresh during long operations")


if __name__ == "__main__":
    asyncio.run(main())
