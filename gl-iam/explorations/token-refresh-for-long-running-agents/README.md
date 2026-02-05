# TokenManager for Long-Running AI Agents

This exploration demonstrates how to use `TokenManager` from GL-IAM for automatic token refresh in long-running AI agents. TokenManager handles authentication token lifecycle automatically, so your agent code can focus on its primary task without worrying about token expiration.

## Overview

### The Problem

Long-running AI agents (like deep research agents) face a unique challenge:

- **Authentication tokens expire** (typically in 1-24 hours)
- **Agents can run for hours or days** without human intervention
- **Manual token refresh** adds complexity and potential points of failure
- **Token expiration mid-task** can cause data loss or incomplete work

### The Solution: TokenManager

TokenManager provides automatic token lifecycle management:

- **On-demand refresh**: Checks and refreshes tokens when you call `get_valid_token()`
- **Background refresh**: Proactively refreshes tokens for agents with sparse API calls
- **Thread-safe**: Uses double-checked locking to prevent concurrent refresh operations
- **Retry logic**: Configurable retry with exponential backoff
- **Audit events**: Full observability into token lifecycle

## Prerequisites

- **Python 3.11+** (3.12 recommended)
- **UV package manager** ([Install UV](https://docs.astral.sh/uv/getting-started/installation/))

## Installation

### Unix/macOS

```bash
# Clone or navigate to this directory
cd gl-iam-cookbook/gl-iam/explorations/token-refresh-for-long-running-agents

# Run setup script
chmod +x setup.sh
./setup.sh
```

### Windows

```batch
cd gl-iam-cookbook\gl-iam\explorations\token-refresh-for-long-running-agents
setup.bat
```

### Manual Installation

```bash
# Install dependencies with UV
uv sync
```

### Development Note

The `pyproject.toml` is configured to use the **git branch** for gl-iam:

```toml
# For remote usage (branch pushed to remote):
gl-iam = { git = "https://github.com/GDP-ADMIN/gl-sdk.git", subdirectory = "libs/gl-iam", branch = "feature/token-refresh-for-long-running-agents" }

# For local development (uncomment if needed):
# gl-iam = { path = "../../../../gl-sdk/libs/gl-iam", editable = true }
```

For local development, you can switch to the local path by uncommenting the path source.

## Configuration

The setup script already creates `.env` from `.env.example`. To customize, edit the `.env` file.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MOCK_TOKEN_TTL_SECONDS` | 60 | Simulated token TTL (production: 3600-86400) |
| `ORGANIZATION_ID` | org-demo-123 | Multi-tenancy organization context |
| `VERBOSE_LOGGING` | true | Enable detailed logging output |

## Running the Examples

### 1. Simple On-Demand Refresh (`simple_demo.py`)

**Best for:** Most applications with frequent API calls

```bash
uv run python simple_demo.py
```

This demo shows the basic pattern:
- Create TokenManager with an initial token
- Call `get_valid_token()` before each API call
- Watch automatic refresh happen when token approaches expiry

**Output example:**
```
[14:30:00] Created initial token, expires at: 14:31:00
[14:30:00] API Call #1: Using token (60.0s remaining)
[14:30:05] API Call #2: Using token (55.0s remaining)
...
[14:30:45]   [REFRESH] Refreshing token for org: org-demo-123
[14:30:45]   [REFRESH] New token obtained, expires at: 14:31:45
[14:30:45] API Call #10: Using token (60.0s remaining)
```

### 2. Background Refresh (`background_demo.py`)

**Best for:** Agents with long gaps between API calls

```bash
uv run python background_demo.py
```

This demo shows the background refresh pattern:
- Use `auto_refresh_context()` context manager
- Background task periodically checks token status
- Tokens stay fresh even during long processing periods

**Output example:**
```
[14:30:00] Background refresh started
[14:30:00] Round 1: Processing data for 36s (no API calls)...
[14:30:10]   [Status] Processing... Token: 50.0s, Background refresh: True
...
[14:30:30] [REFRESH] Token refresh triggered...
[14:30:36] Round 1: Making API call with token (54.0s)
```

### 3. Deep Research Agent (`deep_research_agent.py`)

**Best for:** Production-like agent simulation

```bash
uv run python deep_research_agent.py
```

This demo simulates a complete AI research agent:
- Multiple research phases (gathering, analyzing, synthesizing, reporting)
- Audit event logging for observability
- Error handling with `force_refresh()`
- Graceful shutdown with Ctrl+C

**Output example:**
```
[GATHERING ] Starting data gathering phase...
[GATHERING ] Fetching data from web_search...
[TOKENMGR  ] Token refresh triggered for org: org-demo-123
[AUDIT     ] token_refresh_success
[ANALYZING ] Starting analysis of 4 data sources...
...
Summary:
  API calls made: 15
  Token refreshes: 3
  Errors handled: 1
```

## How It Works

### Refresh Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `ON_DEMAND` | Refresh when `get_valid_token()` called | Frequent API calls |
| `BACKGROUND` | Proactive refresh in background loop | Sparse API calls |
| `DISABLED` | Manual `force_refresh()` only | Full control needed |

### TTL Threshold

TokenManager uses a **threshold-based refresh** (default: 25% TTL remaining):

```
Token TTL: 1 hour (3600 seconds)
Refresh threshold: 25%

Timeline:
0:00 ─────────────────────────────── 1:00
     [─────── valid ─────][─ refresh zone ─]
                          ^
                     0:45 (75% consumed)
```

When `get_valid_token()` is called in the refresh zone, it automatically refreshes.

### Configuration Options

```python
from gl_iam import TokenManagerConfig, RefreshStrategy

config = TokenManagerConfig(
    refresh_threshold_ratio=0.25,    # Refresh at 25% TTL remaining
    check_interval_seconds=30.0,     # Background check frequency
    max_retry_attempts=3,            # Retries on failure
    retry_delay_seconds=5.0,         # Delay between retries
    refresh_strategy=RefreshStrategy.BACKGROUND,
)
```

## API Reference

### TokenManager

```python
from gl_iam import TokenManager, TokenManagerConfig, AuthToken

# Create manager
manager = TokenManager(
    gateway=gateway,                 # IAMGateway instance
    organization_id="org-123",       # Multi-tenancy context
    initial_token=token,             # Starting token (optional)
    config=config,                   # Configuration (optional)
    refresh_callback=callback,       # Custom refresh function (optional)
    audit_callback=audit_cb,         # Audit event handler (optional)
)

# Get valid token (auto-refreshes if needed)
result = await manager.get_valid_token()
if result.is_ok:
    token = result.value
    headers = {"Authorization": f"Bearer {token.access_token}"}

# Get headers directly
result = await manager.get_headers()
if result.is_ok:
    response = await client.get(url, headers=result.value)

# Force immediate refresh (after 401 error)
result = await manager.force_refresh()

# Background refresh context
async with manager.auto_refresh_context():
    # Tokens stay fresh automatically
    for task in long_running_tasks:
        result = await manager.get_valid_token()
        await process(task, result.value)

# Check status
print(f"Refresh count: {manager.refresh_count}")
print(f"Background running: {manager.is_background_refresh_running}")
```

### Custom Refresh Callback

```python
async def my_refresh_callback(
    organization_id: str,
    current_token: AuthToken | None,
) -> Result[AuthToken]:
    """Custom refresh logic for external auth service."""
    response = await external_auth.refresh(
        org_id=organization_id,
        refresh_token=current_token.refresh_token if current_token else None,
    )
    return Result.ok(AuthToken(
        access_token=response.access_token,
        expires_at=response.expires_at,
        refresh_token=response.refresh_token,
    ))

manager = TokenManager(
    gateway=gateway,
    organization_id="org-123",
    refresh_callback=my_refresh_callback,
)
```

### Audit Events

```python
from gl_iam import AuditEvent, AuditEventType

def audit_handler(event: AuditEvent) -> None:
    """Handle audit events for observability."""
    if event.event_type == AuditEventType.TOKEN_REFRESH_SUCCESS:
        logger.info(f"Token refreshed: {event.details}")
    elif event.event_type == AuditEventType.TOKEN_REFRESH_FAILED:
        logger.error(f"Refresh failed: {event.details}")
    # Send to monitoring system
    metrics.increment("token_refresh", tags={"status": event.event_type.value})

manager = TokenManager(
    gateway=gateway,
    organization_id="org-123",
    audit_callback=audit_handler,
)
```

## Troubleshooting

### "No refresh token available"

The token doesn't have a refresh token. Ensure your auth provider returns refresh tokens:

```python
token = AuthToken(
    access_token="...",
    refresh_token="...",  # Required for refresh
    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
)
```

### "Token refresh failed after all retries"

Check:
1. Network connectivity to auth provider
2. Refresh token validity (hasn't expired)
3. Increase `max_retry_attempts` if transient failures

### Background refresh not working

Ensure you're using the context manager:

```python
# Correct - background task runs
async with manager.auto_refresh_context():
    await do_work()

# Wrong - background task never starts
await do_work()
```

### High token refresh frequency

Adjust the threshold ratio:

```python
config = TokenManagerConfig(
    refresh_threshold_ratio=0.1,  # Refresh only at 10% TTL remaining
)
```

## Best Practices

1. **Use on-demand refresh** for most applications
2. **Use background refresh** only for sparse API calls
3. **Always handle Result errors** - don't assume tokens are valid
4. **Set up audit callbacks** for production observability
5. **Use force_refresh()** after receiving 401 errors
6. **Implement graceful shutdown** for long-running agents

## Related Documentation

- [GL-IAM SDK Documentation](https://gdplabs.gitbook.io/sdk)
- [TokenManager Implementation](https://github.com/GDP-ADMIN/gl-sdk/tree/feature/token-refresh-for-long-running-agents/libs/gl-iam)
- [Stack Auth Documentation](https://stack-auth.com/docs)
