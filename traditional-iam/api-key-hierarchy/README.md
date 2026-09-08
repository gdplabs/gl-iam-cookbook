# API Key Hierarchy Example

Demonstrates GL-IAM's API key hierarchy with **SOLID architecture**.

## Use Case

This example implements the **AI Agent Platform (AIP)** pattern:

- **1 Forever Key** per organization (primary access, never expires)
- **Multiple Child Keys** with limited lifetime (CI/CD, partners, temporary access)
- **Platform Key** for cross-organization management (system bootstrap)

```
PLATFORM Key (system)
    |
    v
ORGANIZATION Key (forever, per-org)
    |
    +-- CI/CD Key (30 days)
    +-- Partner Key (7 days)
    `-- Temp Key (1 day)
```

## Architecture

This example follows **SOLID principles**:

```
main.py (Orchestrator)
|
+-- config.py              # S: Single responsibility for configuration
|
+-- providers/
|   `-- api_key_provider.py  # D: Dependency inversion via factory
|
+-- services/
|   +-- key_service.py       # I: Interface segregation (create vs validate)
|   `-- hierarchy_service.py # O: Open for extension (new visualizations)
|
`-- demo/
    +-- bootstrap_demo.py      # L: Substitutable demo modules
    +-- organization_demo.py
    +-- child_keys_demo.py
    +-- validation_demo.py
    `-- hierarchy_demo.py
```

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- uv (recommended) or pip

## Quick Start

1. **Clone and navigate**

   ```bash
   git clone https://github.com/gdplabs/gl-iam-cookbook.git
   cd gl-iam-cookbook/traditional-iam/api-key-hierarchy/
   ```

2. **Install dependencies**

   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -r requirements.txt
   ```

3. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your PostgreSQL connection
   ```

4. **Start PostgreSQL** (if not running)

   ```bash
   docker run -d --name postgres \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=gliam \
     -p 5432:5432 \
     postgres:15
   ```

5. **Run the demo**

   ```bash
   # Using uv
   uv run python main.py

   # Or directly
   python main.py
   ```

## Demo Modules

| Module | Demonstrates |
|--------|-------------|
| `bootstrap_demo.py` | PLATFORM key creation (system bootstrap) |
| `organization_demo.py` | Forever organization key creation |
| `child_keys_demo.py` | Limited-lifetime child key creation |
| `validation_demo.py` | Key validation and scope checking |
| `hierarchy_demo.py` | Key tree visualization |
| `hash_algorithm_demo.py` | What validation costs, and switching algorithms without reissuing keys<br/>_Needs an HMAC-SHA256 capable `gl-iam`; skips itself otherwise_ |

## Key Concepts

### Hash Algorithm

Validation hashes the key that was presented, and by default that hash is bcrypt, which is slow on purpose. Budget around **200 ms per validation**. On a service that authenticates every request, that is the dominant cost of the request.

The work factor exists to make guessing a *human-chosen* secret expensive. GL-IAM generates every key itself from 256 bits of randomness, and no method accepts a key you supply, so there is no weak secret for that slowness to protect. `HMAC_SHA256` is the opt-in alternative for services that need the latency back:

```python
from gl_iam.core.crypto_config import ApiKeyHashAlgorithm, CryptoConfig

config = NativeConfig(
    database_url=settings.database_url,
    crypto_config=CryptoConfig(api_key_hash_algorithm=ApiKeyHashAlgorithm.HMAC_SHA256),
)
```

Existing keys keep working and rewrite their own stored hash the first time each is used, so there is nothing to reissue and no migration step. `hash_algorithm_demo.py` shows exactly that: one key, created under bcrypt, validating through both. The switch only goes one way though. Once a key has rewritten itself into a digest, setting bcrypt back leaves that key unverifiable, so a rollback means reissuing.

bcrypt stays the default. Note that lowering `bcrypt_rounds` does **not** speed up keys you already have, because bcrypt stores its work factor inside each hash.

### API Key Tiers (3-Tier Model)

| Tier | Context | Purpose |
|------|---------|---------|
| PLATFORM | org=NULL, user=NULL | System bootstrap, cross-org |
| ORGANIZATION | org=REQUIRED, user=NULL | Per-organization access |
| PERSONAL | org=REQUIRED, user=REQUIRED | Per-user access |

### Forever vs Limited Keys

```python
# Forever key (never expires)
key, secret = await provider.create_api_key(
    name="Primary Key",
    tier=ApiKeyTier.ORGANIZATION,
    expires_at=None,  # <-- Never expires
)

# Limited key (30 days)
key, secret = await provider.create_api_key(
    name="CI/CD Key",
    expires_at=datetime.utcnow() + timedelta(days=30),
    parent_key_id=parent.id,  # <-- Linked to parent
)
```

### Scope Inheritance

Child keys cannot have scopes that parent doesn't have:

```python
# Parent has: ["agents:execute", "agents:read", "keys:create"]
# Child can have: ["agents:execute"] (subset) ✓
# Child CANNOT have: ["agents:delete"] (not in parent) ✗
```

## Expected Output

```
============================================================
GL-IAM API Key Hierarchy Demo (SOLID Architecture)
============================================================

============================================================
DEMO: Bootstrap PLATFORM Key
============================================================
Creating PLATFORM bootstrap key...

PLATFORM Key Created:
  ID:       abc12345-...
  Name:     System Bootstrap Key
  Tier:     PLATFORM
  Scopes:   ['*']

...

============================================================
DEMO: Key Hierarchy Visualization
============================================================

--- ASCII Tree Summary ---

Primary API Key (aip_abc1...) [ORGANIZATION] scopes: [agents:execute, agents:read, ...]
+-- CI/CD Pipeline Key (aip_def2...) [ORGANIZATION] scopes: [agents:execute] expires: 2024-03-01
+-- Partner Integration Key (aip_ghi3...) [ORGANIZATION] scopes: [agents:read] expires: 2024-02-15
`-- Temporary Debug Key (aip_jkl4...) [ORGANIZATION] scopes: [agents:execute, agents:read] expires: 2024-02-05

============================================================
Demo Complete!
============================================================
```

## Related Resources

- [API Keys Concept (GitBook)](https://gdplabs.gitbook.io/sdk/tutorials/identity-and-access-management/api-keys)
- [Introduction to GL-IAM](https://gdplabs.gitbook.io/sdk/gl-iam/introduction-to-gl-iam)
- [GL-IAM Quickstart](https://gdplabs.gitbook.io/sdk/tutorials/identity-and-access-management/quickstart)
