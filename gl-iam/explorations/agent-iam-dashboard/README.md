# Agent IAM Dashboard

Interactive web dashboard demonstrating GL-IAM's AI Agent Identity and Access Management.

Covers all BRD use cases from GLChat, Digital Employee, and AI Platform with visual delegation flow, scope attenuation, audit trail, and token inspection.

## Quick Start

### Prerequisites

- Python 3.11+ with [uv](https://docs.astral.sh/uv/)
- Node.js 22+ with npm
- Docker (for PostgreSQL)

### Setup

```bash
# 1. Install dependencies
make setup

# 2. Start PostgreSQL
make start-db

# 3. Start backend services (3 terminals)
cd backend && uv run python glchat_be.py   # Terminal 1 - port 8000
cd backend && uv run python aip_backend.py  # Terminal 2 - port 8001
cd backend && uv run python connectors.py   # Terminal 3 - port 8002

# 4. Start dashboard
make start-dashboard   # http://localhost:5173
```

### Using the Dashboard

1. **Check service health** - Green dots indicate all 3 backend services are running
2. **Click "Initialize Demo"** - Registers demo users and agents automatically
3. **Pick a scenario** - Select from GLChat, DE, or AIP use cases
4. **Run it** - Watch the delegation flow animate with scope attenuation
5. **Inspect** - Click on tokens, view audit trail, compare roles

## Architecture

```
Browser (Dashboard :5173)
    |
    +-- GET /health              --> GLChat BE (:8000)
    +-- GET /health              --> AIP Backend (:8001)
    +-- GET /health              --> Connectors (:8002)
    |
    +-- POST /demo/setup         --> GLChat BE (register users + agents)
    +-- GET /scenarios           --> GLChat BE (list BRD scenarios)
    +-- POST /scenarios/{id}/run --> GLChat BE --> AIP --> Connectors
    |
    +-- GET /audit/events        --> All 3 services (audit trail)
```

### 3-Service Delegation Flow

```
User (d1) --> GLChat BE (ABAC) --> delegate_to_agent() --> JWT
                |
                v
         AIP Backend (d2: validate token, plan tools)
                |
                v
         Worker Sub-Agents (d3: scope attenuation)
                |
                v
         GL Connectors (d4: tool execution with scope enforcement)
```

## BRD Scenarios

| Product | Use Cases | Count |
|---------|-----------|-------|
| GLChat | Calendar check, meeting scheduling, task scheduler | 6 |
| Digital Employee | MoM creation/sharing/access, cross-tenant, feature-level | 10 |
| AI Platform | Weekly reports (autonomous agent) | 4 |

### Key Concepts Demonstrated

- **Delegation Tokens** - Stateless JWT carrying user identity through agent chain
- **Scope Attenuation** - Authority narrows at each hop (user > agent > worker > tool)
- **ABAC** - Role-based scope enforcement (admin/member/viewer)
- **Tenant Isolation** - Cross-tenant requests rejected
- **Feature-Level Access** - Per-user feature entitlements in delegation token
- **Audit Trail** - Cross-service correlation via delegation_ref
- **Defense in Depth** - 4 independent enforcement points

## Project Structure

```
agent-iam-dashboard/
+-- backend/
|   +-- glchat_be.py       # Service 1: User auth, ABAC, delegation
|   +-- aip_backend.py     # Service 2: Token validation, tool routing
|   +-- connectors.py      # Service 3: Tool execution, scope enforcement
|   +-- scenarios.py       # 17 BRD scenario configurations
|   +-- mock_data.py       # Simulated users, meetings, MoMs, reports
|   +-- shared.py          # Audit store, CORS, helpers
+-- dashboard/             # React SPA
|   +-- src/
|       +-- components/    # UI components (delegation flow, token inspector, etc.)
|       +-- pages/         # Demo, Comparison, Audit Trail pages
|       +-- hooks/         # State management
|       +-- lib/           # API client, types, JWT decoder
+-- pyproject.toml         # Python dependencies
+-- Makefile               # Development commands
```
