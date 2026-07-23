# DE Vertical Permission Gate

A Digital Employee that cannot touch Google Docs until the human says it may — and stops
being able to the moment the human changes their mind.

This example answers a specific question: **can a DE vertical enforce "tool X requires
scope Y" today, without waiting for AIP or DE Core to implement it?** The answer is yes,
and this is the smallest working version of it.

Run it with `uv run main.py` and open <http://localhost:8000>. No database, no Docker.

## What it demonstrates

| Scenario | What you see |
|----------|--------------|
| Agent has only `meemo:read` | Reads the meeting, **refuses** to create the doc or send mail |
| Human clicks *Allow* on `google_docs:write` | Same job now writes the doc, still **refuses** to send mail |
| Agent asks for every scope it owns | GL-IAM **refuses to mint the token** — no tool is ever reached |
| Human revokes `google_docs:write` | Next run is denied again, no redeploy, no restart |
| Human hits the kill switch | Every future delegation fails with `AGENT_REVOKED` |

Every one of those decisions lands in the GL-IAM audit trail with the delegation chain
traced back to the human who started it.

## Two layers of enforcement

The example enforces at two independent points, and it matters that they are separate.

**1. At mint time — GL-IAM refuses to issue authority the human never gave.**

`delegate_to_agent` caps what a token may carry by `principal_scope` (what the human
granted) and by the agent's `allowed_scopes` ceiling. Ask for more and you get
`SCOPE_ESCALATION_DENIED` and no token at all. This is cryptographic: a compromised or
confused agent cannot mint itself a wider token, because it does not hold the signing key.

**2. At call time — the tool checks the token it was handed.**

A token scoped to `meemo:read` is still a valid token. Something has to refuse to run
`google_docs_create_document_tool` while holding it. That check is the `@requires_scope`
decorator in [`scope_gate.py`](scope_gate.py), and it lives in DE-vertical code.

Layer 1 already exists in GL-IAM. Layer 2 is the missing last mile, and it is a decorator.

## Where this fits with AIP

AIP already carries most of the plumbing, dormant behind a feature flag:

- `ai-agent-platform-backend/ai_agent_platform_backend/auth/delegation_token_auth.py`
  accepts an `X-Delegation-Token` header, validates it through GL-IAM, and propagates the
  chain and scopes into the agent run's metadata.
- It builds an agent's `allowed_scopes` **from the names of the tools attached to that
  agent** plus its sub-agent names. The scope namespace is already "one scope per tool".
- All of it is gated by `GL_IAM_ENABLED` / `GL_IAM_DELEGATION_REQUIRED`, both defaulting
  to false.

What no layer does yet is check the token against the tool about to run. So a DE vertical
has two ways forward, and neither requires changing AIP or DE Core:

- **Today, standalone** — the DE mints its own delegation token per run, exactly as this
  example does. Nothing outside the DE repo has to move.
- **Later, through AIP** — turn on `GL_IAM_ENABLED`, pass the delegation token as a
  header, and populate the same `DelegationContext` from `metadata["delegation"]` instead
  of minting locally. The tool code and the decorator do not change at all.

The gate is written against a `ContextVar` precisely so that swap is a one-line change in
the runtime, not a rewrite of every tool.

## Quick Start

1. **Install dependencies**

   ```bash
   ./setup.sh        # Unix / macOS
   setup.bat         # Windows
   ```

   Or manually: `uv sync`

2. **Run**

   ```bash
   uv run main.py
   ```

3. **Open the console** at <http://localhost:8000>

   Start with only *Read meeting recordings* allowed, hit **Run the MoM job**, and watch
   the last two steps get denied. Then allow *Create and edit Google Docs* and run again.

There is nothing else to start. `delegate_to_agent` is handed the `AgentIdentity`
directly — the same hook AIP uses to keep its own agent catalog instead of dual-writing
into GL-IAM's `agents` table — and token validation is stateless JWT verification, so no
database session is ever opened.

## Testing the API

```bash
# Current state: agent, tools, grants, audit trail, last run
curl -s http://localhost:8000/api/state | jq

# Run the DE's job under a fresh delegation token
curl -s -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{"escalate": false}' | jq '.effective_scopes, [.steps[] | {step, allowed: .decision.allowed}]'

# Grant a scope
curl -s -X POST http://localhost:8000/api/permissions/grant \
  -H "Content-Type: application/json" -d '{"scope": "google_docs:write"}' | jq

# Revoke it again — takes effect on the next delegation
curl -s -X POST http://localhost:8000/api/permissions/revoke \
  -H "Content-Type: application/json" -d '{"scope": "google_docs:write"}' | jq

# Ask for every scope the agent owns, regardless of grants -> refused at mint time
curl -s -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" -d '{"escalate": true}' | jq '{minted, error_code, error}'

# Kill switch
curl -s -X POST "http://localhost:8000/api/agent/status?active=false" | jq
curl -s -X POST "http://localhost:8000/api/agent/status?active=true"  | jq
```

> The escalation run only fails while at least one scope is ungranted. Grant everything
> and it legitimately succeeds — the ceiling is the human's grant, not a fixed list.

## Understanding the code

| File | Role |
|------|------|
| [`scope_gate.py`](scope_gate.py) | The reusable piece: `@requires_scope` plus the `DelegationContext` it reads |
| [`tools.py`](tools.py) | The DE's tools, shaped like the real ones in `digital-employee-pm` |
| [`de_runtime.py`](de_runtime.py) | Grant store, agent identity, and the mint → delegate → run loop |
| [`main.py`](main.py) | FastAPI app and the permission console |

### The diff a DE vertical actually makes

One line per tool:

```python
@requires_scope("google_docs:write")
class GoogleDocsCreateDocumentTool(BaseTool):
    name: str = "google_docs_create_document_tool"
    ...                                    # everything else unchanged
```

On denial the tool returns a structured refusal rather than raising, so the agent can
degrade gracefully — skip the step, tell the user what it needs — instead of the whole
run crashing:

```json
{
  "status": "permission_denied",
  "tool": "google_docs_create_document_tool",
  "required_scope": "google_docs:write",
  "reason": "Scope 'google_docs:write' was never delegated by user:sam.",
  "remediation": "Ask the user to grant 'google_docs:write' to this agent, then retry."
}
```

### The runtime, in five calls

```python
# 1. The agent's ceiling comes from the tools attached to it.
TOOL_SCOPES = [get_required_scope(t) for t in DE_TOOLS]

# 2. A cron-driven DE has no user session, so mint a short-lived principal JWT.
principal = gateway.mint_principal_jwt(sub="user:sam", ttl_seconds=300)

# 3. Exchange it for a delegation token capped by what the human granted.
delegation = await gateway.delegate_to_agent(
    principal_token=principal.value,
    agent_id=AGENT_ID,
    task=TaskContext(id=task_id, purpose="Write up the minutes"),
    scope=DelegationScope(scopes=requested, expires_in_seconds=300),
    principal_scope=DelegationScope(scopes=sorted(permissions.granted)),  # <- the cap
    agent=current_agent(),
)

# 4. Install it for the run. Every gated tool reads it.
set_delegation_context(DelegationContext(token=delegation.value))

# 5. Run the plan. Denials are decisions, not exceptions.
```

### How revocation actually takes effect

Revoking does not reach into tokens already issued — it cannot, they are signed and
stateless. It works because **every run mints a fresh, short-lived token** against the
current grants. Revoke `google_docs:write` and the next run's token simply does not carry
it. The 300-second TTL bounds the blast radius of a token already in flight; the kill
switch (`AgentStatus.REVOKED`) stops new tokens entirely.

That is the honest trade: revocation is not instantaneous, it is bounded. Shorten the TTL
if you need a tighter bound.

## What is faked, and what is real

Real: the delegation tokens, the chain, the scope attenuation, the ceiling checks, the
gate decisions, the audit events. All of it is GL-IAM doing the work.

Faked: the three tool backends return canned payloads so the example runs offline, and the
plan is a fixed three-step sequence rather than an LLM deciding what to call. The demo is
about the authorization behaviour, so nothing else is allowed to be a variable.

## Next steps

- [`agent-delegation-fastapi`](../agent-delegation-fastapi/) — delegation basics
- [`agent-scope-constraints`](../agent-scope-constraints/) — narrowing by tenant, region, budget
- [`agent-lifecycle`](../agent-lifecycle/) — suspend, revoke, reactivate
- [`aip-server-integration`](../aip-server-integration/) — adding GL-IAM to an existing AIP server
