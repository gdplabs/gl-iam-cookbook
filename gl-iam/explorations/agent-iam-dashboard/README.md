# Agent IAM — Real Case Simulation

Interactive web dashboard demonstrating GL-IAM's AI Agent Identity and Access Management with real delegation flows, scope attenuation, resource constraints, credential routing, and audit trail.

**Purpose**: Convince stakeholders why AI Agents need Agent IAM — based on real BRD use cases from GLChat, Digital Employee, and AI Platform.

## Quick Start

```bash
# First time only
make setup

# Run everything (opens 4 terminal windows on macOS)
make run
```

Open **http://localhost:5173** and click **Initialize Demo**.

## What `make run` does

1. Starts PostgreSQL (Docker)
2. Opens 4 Terminal windows:
   - 🔵 **GLChat BE** (`:8000`) — user auth, ABAC, delegation token creation
   - 🟣 **AIP Backend** (`:8001`) — token validation, tool planning, worker delegation
   - 🟢 **GL Connectors** (`:8002`) — tool execution (pure transport layer)
   - 🌐 **Dashboard** (`:5173`) — React UI

## Commands

| Command | What it does |
|---------|-------------|
| `make setup` | Install Python + Node dependencies (first time) |
| `make run` | Start everything (DB + 4 services in separate terminals) |
| `make stop` | Stop all backend services |
| `make reset-db` | Drop and recreate the database |
| `make health` | Check if all services are running |
| `make clean` | Stop everything + remove DB container |

## Prerequisites

- Python 3.11+ with [uv](https://docs.astral.sh/uv/)
- Node.js 22+ with npm
- Docker (for PostgreSQL)

## Architecture

```
Browser (Dashboard :5173)
  → POST /demo/interactive-run (Agent + User + Action)
    → GLChat BE (:8000)
        ABAC scope attenuation → DelegationToken (JWT)
        Resource constraints: target_whitelist, write_whitelist
      → AIP Backend (:8001)
          Validate token → Plan tools → Dispatch workers
          Agent worker policy guard rail (before_tool_call)
        → GL Connectors (:8002)
            Execute tool via 3P API (pure transport)
```

### Three-Layer Responsibility

| Layer | What it does | Who implements |
|-------|-------------|---------------|
| **GL-IAM SDK** | DelegationToken with scopes + constraints, audit trail | SDK team (library) |
| **AIP Platform** | Token validation, tool filtering, DelegationToolManager hooks | AIP team (platform) |
| **DE / Agent Code** | Resource constraint enforcement, credential routing, guard rails | DE team (agent code) |

## Using the Dashboard

### Interactive Demo (Main Tab)

1. Pick **Agent** → **User** → **Action** from dropdowns
2. Click **Run Scenario**
3. Results panel shows (top to bottom):
   - **Chat Simulation** — hypothetical prompt + AI response
   - **Delegation Flow** — animated d1→d2→d3→d4 chain with tool inputs/outputs
   - **Scope Attenuation** — User scopes × Agent Ceiling → intersection
   - **Agent Static Config** — scope ceiling, workers, resource constraints (with layer labels)
   - **Enforcement Logic** — Python code snippet + matrix table for all 4 users
   - **Policy Decision Trace** — step-by-step PASS/FAIL evaluation
   - **Credential Routing Policy** — resource × role matrix
   - **Tool Results** — executed/denied tools with enforcement layer
   - **Delegation Token** — decoded JWT claims
   - **Audit Trail** — SDK + app events

### Comparison Tab

Run multiple scenarios → see results side by side in a grid.

### Audit Trail Tab

Timeline of all events (SDK + app level), filterable by service tag.

## Users

| Name | Role | Org | Access Level |
|------|------|-----|-------------|
| Pak On | Admin | Cross-Org | Wildcard access to any calendar, any org. Has invoice feature. |
| Maylina | Member | GLC | GLC org + Pak On (whitelisted). Can write to Pak On only. |
| Petry | Member | GLAIR | GLAIR org + Pak On (whitelisted). Can write to Pak On only. |
| Guest | Viewer | No Org | Pak On calendar only (read). No User OAuth. |

## Four Access Control Dimensions

### 1. Scope (= Tool Name)

```
"What tools can this agent use for this user?"
```

- Scopes ARE tool names: `google_calendar_events_list`, `directory_lookup`, etc.
- Agent has a scope ceiling (set at registration)
- User scopes ∩ Agent ceiling = effective delegation scopes
- Feature-gated scopes (e.g., `invoice_send`) require user entitlement

### 2. Resource Constraint

```
"On WHAT data can these tools operate?"
```

Embedded in the DelegationToken per-user:

| Role | target_whitelist | write_whitelist |
|------|-----------------|-----------------|
| Admin | `"*"` (wildcard) | `"*"` (wildcard) |
| Member | `["onlee@gdplabs.id", "org:{user.tenant}"]` | `["onlee@gdplabs.id"]` |
| Guest | `["onlee@gdplabs.id"]` | `[]` |

**Self-access**: `target == user_email` → always allowed, no constraint check.

### 3. Credential Routing

```
"With WHOSE OAuth does the tool execute?"
```

Deterministic per role + target:
- **Own resource** → User OAuth
- **Others' resource (whitelisted)** → Agent OAuth
- **Admin** → User+Agent (User first, Agent fallback)

### 4. Feature-Level Access Control

```
"Is this user entitled to use this tool?"
```

Checked at ABAC before delegation. Example: `invoice_send` requires `invoice_send` in `user.features`.

## GL-IAM SDK Audit Trail

Uses `feat/gl-iam/audit-trail-logging-tracing` branch. SDK auto-emits:
- `login_success` — user authenticated
- `delegation_created` — delegation token issued
- `agent_registered` — agent registered

Events stored in `gl_iam.audit_events` PostgreSQL table + captured via CallbackAuditHandler.

## Project Structure

```
agent-iam-dashboard/
├── backend/
│   ├── glchat_be.py           # Service 1: Auth, ABAC, delegation
│   ├── aip_backend.py         # Service 2: Tool planning, worker delegation
│   ├── connectors.py          # Service 3: Tool execution
│   ├── scenarios.py           # BRD scenario configs
│   ├── mock_data.py           # Simulated users, calendars, MoMs
│   └── shared.py              # Audit store, CORS
├── dashboard/                 # React + Vite + TypeScript + shadcn/ui
│   └── src/
│       ├── components/
│       │   ├── delegation/    # DelegationFlow, ScopeAttenuation, AgentConfig,
│       │   │                  # EnforcementMatrix, PolicyDecisionTrace, CredentialPolicy
│       │   ├── scenario/      # ScenarioBuilder (interactive picker)
│       │   ├── results/       # ChatSimulation, ToolResultCard, ExecutionLog
│       │   ├── audit/         # AuditTimeline (SDK + app events)
│       │   ├── setup/         # SetupPanel, ServiceHealth
│       │   └── token/         # TokenInspector (JWT decode)
│       └── pages/             # DemoPage, ComparisonPage, AuditPage
├── Makefile                   # make setup / make run / make stop
└── README.md
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + Vite + TypeScript + Tailwind CSS + shadcn/ui + Framer Motion |
| Backend | Python 3.11+ + FastAPI + GL-IAM SDK |
| Database | PostgreSQL (via Docker) |
| Auth | GL-IAM SDK delegation tokens (stateless JWT) |
