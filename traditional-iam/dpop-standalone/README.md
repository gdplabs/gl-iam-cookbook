# DPoP Without Keycloak (Standalone)

This example demonstrates **DPoP (Demonstrating Proof of Possession)** with **no Keycloak and no database** — proving that DPoP in GL-IAM is backend-agnostic. All proof validation, replay protection, and `cnf.jkt` token-binding run locally using GL-IAM's `StandaloneDPoPProvider` (PyJWT + cryptography only).

DPoP binds an access token to a client's cryptographic key pair. Even if someone steals the token, they cannot use it without the matching **private key**.

| Attack | Bearer token | DPoP-bound token |
|--------|--------------|------------------|
| Token copied from a log/repo/`.env` | Attacker can use it | Useless without the private key |
| Token replayed | Possible | Each proof is one-time (jti + replay cache) |
| Token forwarded to another endpoint | Easy | Proof is bound to method + URL |

> [!IMPORTANT]
> **Issuance note — read this.** GL-IAM now issues DPoP-bound tokens **first-party, no Keycloak**:
> ```python
> token = await gateway.create_dpop_bound_session(user, org_id, dpop_thumbprint=client.jwk_thumbprint)
> # PostgreSQLSessionMixin.create_session adds cnf.jkt and sets token_type="DPoP"
> ```
> This example ships a tiny **demo issuer** (`issue_token.py`) that mints the *same* bound token **without a database**, only so the example stays zero-infra. In a real deployment use the gateway call above (it needs a Postgres-backed provider + a real user). Both the issuance and validation halves shown here are real, shipped GL-IAM capabilities.

## Architecture

```
  generate_key.py          issue_token.py                 main.py (FastAPI)
  ---------------          --------------                 -----------------
  EC P-256 keypair   -->   mints access token       -->   StandaloneDPoPProvider
  private key (kept)       with cnf.jkt = thumbprint       - validate_dpop_proof()
  public JWK (shared)      (demo Authorization Server)     - validate_token_binding()
        |                                                        ^
        |                  create_proof.py                       |
        +----------------> signs a fresh DPoP proof  ------------+
                           per request (private key)        no Keycloak,
                                                            no DB, no introspection
```

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Access to the GDP Labs Gen AI SDK repo (request via ticket@gdplabs.id) + `gcloud auth login`
- **No Keycloak. No PostgreSQL. No Docker.**

## Quick Start

```bash
cd traditional-iam/dpop-standalone
./setup.sh                       # installs deps, creates .env

uv run generate_key.py           # 1. client key pair -> keys/
TOKEN=$(uv run issue_token.py | tail -3 | head -1)   # 2. mint a bound token
uv run main.py                   # 3. start the resource server (port 8000)
```

In a second terminal:

```bash
# 4. Generate a proof bound to this exact request + token
PROOF=$(uv run create_proof.py GET "http://localhost:8000/api/protected" "$TOKEN")

# 5. Call the protected endpoint with token + proof
curl -s http://localhost:8000/api/protected \
  -H "Authorization: DPoP $TOKEN" \
  -H "DPoP: $PROOF"
# -> 200 {"sub":"user-123","org_id":"demo-org","bound_key":"..."}
```

> Tip: export `TOKEN` in the terminal where you run the `curl`/`create_proof.py`
> commands. Each proof is single-use (replay-protected), so generate a fresh
> `PROOF` for every request.

## Testing the API

```bash
# Public — no auth
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/public

# Protected, happy path (see Quick Start) -> 200

# Negative 1: token but NO proof -> 401 (this is the whole point)
curl -i http://localhost:8000/api/protected -H "Authorization: DPoP $TOKEN"
#   401 Missing DPoP proof header

# Negative 2: replay the same proof twice -> 401 on the second call
curl -s http://localhost:8000/api/protected -H "Authorization: DPoP $TOKEN" -H "DPoP: $PROOF"
curl -i http://localhost:8000/api/protected -H "Authorization: DPoP $TOKEN" -H "DPoP: $PROOF"
#   401 DPoP proof rejected: ... replay detected

# Negative 3: proof from a DIFFERENT key -> 401 (binding mismatch)
#   Re-run generate_key.py to make a new key, create a proof with it,
#   but keep the OLD token -> "Token binding failed".
```

## Understanding the Code

| File | Role | Keycloak? |
|------|------|-----------|
| `generate_key.py` | Client creates an EC P-256 key pair via `DPoPClient`; private key stays local | No |
| `issue_token.py` | **Demo Authorization Server** — mints an HS256 access token with `cnf.jkt` | No |
| `create_proof.py` | Client signs a fresh DPoP proof per request (`DPoPClient.create_proof`) | No |
| `main.py` | Resource server validates via `StandaloneDPoPProvider` | No |

The validation core in `main.py` is ~10 lines:

```python
from gl_iam import DPoPConfig
from gl_iam.providers.dpop import StandaloneDPoPProvider

dpop = StandaloneDPoPProvider(DPoPConfig(required=True, nonce_enabled=False))

proof = await dpop.validate_dpop_proof(dpop_proof, method, uri, access_token=token)
binding = await dpop.validate_token_binding(token, proof.value.jwk_thumbprint)
# both .is_ok -> the caller holds the private key -> allow
```

Compare with [`dpop-keycloak`](../dpop-keycloak/): the *only* difference is the
provider (`StandaloneDPoPProvider` vs `KeycloakDPoPProvider`) and who reads
`cnf.jkt` (local token decode vs Keycloak introspection). Same `DPoPProvider`
protocol — swap without touching endpoint code (LSP / SIMI).

## Production notes

- **Replay/nonce state is in-memory.** For multiple server instances, back the replay cache + nonce manager with Redis.
- **Enable nonces** (`nonce_enabled=True`) for stronger replay protection; the client then retries after a `401` carrying a `DPoP-Nonce` header.
- **`htu` must match exactly.** Behind a proxy, make sure the URL the client signs equals the externally-visible URL (scheme/host/path).

## Next Steps

- [`dpop-keycloak`](../dpop-keycloak/) — the same flow with Keycloak as the issuer + binder
- [`fastapi-postgresql`](../fastapi-postgresql/) — self-managed sessions; add `create_dpop_bound_session(...)` for DB-backed first-party DPoP issuance
- [`api-key-hierarchy`](../api-key-hierarchy/) — API keys (bearer today; sender-constrained keys are on the roadmap)
- GL-IAM GitBook → Traditional IAM → DPoP → **DPoP Without Keycloak**
