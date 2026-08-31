# Agent Asymmetric Signing (ES256)

Two services, one key pair. The **issuer** holds the private key and mints delegation tokens. The **verifier** holds only the public key: it can check any token the issuer produced, and it cannot produce one.

## Overview

GL-IAM signs delegation tokens with the value you pass as `secret_key`. Historically that was a shared HMAC secret, which has one consequence worth stating plainly:

> With HMAC, signing and verification use the same key. **Every service you give the secret to so it can verify tokens can also mint them** — for any agent, with any scopes.

That is fine while issuing and validating happen inside one trust boundary. It stops being fine the moment a second service has to validate independently — a connector gateway holding third-party credentials, say, or anything at a boundary where a compromise should not become the ability to forge authority for every agent in the fleet.

Since 0.3.15, `secret_key` also accepts a `SigningConfig`. Configure it with a private key and the service signs; configure it from the issuer's published JWKS and the service verifies and nothing more.

This example demonstrates:

- Generating an ES256 key pair and loading it into a `SigningConfig`
- Publishing the public half at `/.well-known/jwks.json`
- Building a verification-only gateway with `SigningConfig.from_jwks()`
- **Algorithm pinning** — an HS256 token is rejected by an ES256 verifier
- **Key identification (`kid`)** — how key rotation works without a synchronised cutover
- **Audience binding** — a connector-audience verifier cannot validate a runner-audience token
- Proof that the verifier cannot mint, via `GET /can-i-mint`

**No database is required.** Neither service opens a connection: minting and validating a delegation token is stateless JWT work, and the `AgentIdentity` is handed to `delegate_to_agent()` directly.

## Prerequisites

- Python 3.11–3.13
- [uv](https://docs.astral.sh/uv/)
- No PostgreSQL, no Keycloak, no Stack Auth

## Quick Start

```bash
cd agent-iam/agent-asymmetric-signing
./setup.sh          # installs deps, copies .env, generates the key pair
```

Then start both services, in two terminals:

```bash
uv run issuer.py     # http://localhost:8000  — holds the private key
```

```bash
uv run verifier.py   # http://localhost:8001  — holds only the public key
```

The verifier prints what it loaded on startup:

```
Loaded 1 public key(s) from http://localhost:8000
Pinned algorithms: ['ES256']
Can this service mint tokens? False
```

## Testing the API

### The issuer publishes its public key

```bash
curl -s http://localhost:8000/.well-known/jwks.json
```

```json
{"keys":[{"kty":"EC","crv":"P-256","x":"eb7woknt9S-...","y":"oBwFZU4YYqVfaPK...","alg":"ES256","use":"sig","kid":"issuer-2026-08"}]}
```

`to_jwks()` never exports private key material, and it omits HMAC keys entirely — publishing an HMAC secret would hand out minting ability, which is the failure mode this whole mechanism exists to remove.

### The issuer mints a delegation token

```bash
curl -s -X POST http://localhost:8000/delegate \
  -H 'Content-Type: application/json' \
  -d '{"scopes":["reports:read","email:send"],"task_purpose":"Draft and send the Q3 summary"}'
```

```json
{
  "token": "eyJhbGciOiJFUzI1NiIsImtpZCI6Imlzc3Vlci0yMDI2LTA4IiwidHlwIjoiSldUIn0...",
  "agent_id": "agent:report-writer",
  "scopes": ["reports:read", "email:send"],
  "audience": "gl-connectors",
  "expires_at": "2026-08-31T05:28:26+00:00"
}
```

The header carries both the algorithm and the key id:

```json
{ "alg": "ES256", "kid": "issuer-2026-08", "typ": "JWT" }
```

### The verifier accepts it

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/delegate \
  -H 'Content-Type: application/json' \
  -d '{"scopes":["reports:read","email:send"]}' | jq -r .token)

curl -s -X POST http://localhost:8001/tools/send-email \
  -H 'Content-Type: application/json' \
  -d "{\"token\":\"$TOKEN\"}"
```

```json
{
  "sent_to": "finance@example.com",
  "on_behalf_of": "user:alice",
  "agent": "agent:report-writer",
  "scopes": ["reports:read", "email:send"],
  "task": "Draft and send the Q3 summary"
}
```

### The verifier cannot mint

This is the property the whole recipe exists for.

```bash
curl -s http://localhost:8001/can-i-mint
```

```json
{
  "can_mint": false,
  "error_code": "ErrorCode.CONFIGURATION_ERROR",
  "detail": "This SigningConfig is verification-only: no configured key carries private key material, so it cannot mint tokens. That is the intended posture for a pure verifier."
}
```

Under a shared HMAC secret this endpoint would have returned a freshly signed token for `user:mallory`.

### What the verifier rejects

Each of these is a real request against the running services.

**A token that is authentic but does not carry the scope** — validation and authorization are separate steps, and the second one is always your service's job:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/delegate \
  -H 'Content-Type: application/json' -d '{"scopes":["reports:read"]}' | jq -r .token)
curl -s -X POST http://localhost:8001/tools/send-email \
  -H 'Content-Type: application/json' -d "{\"token\":\"$TOKEN\"}"
```

```json
{ "detail": "Token is authentic but carries ['reports:read'], not 'email:send'." }
```

**An HS256 token presented to an ES256-pinned verifier.** Verification uses the algorithm recorded on the *configured key*, never the one advertised in the token header, which closes the classic HS/RS confusion downgrade:

```json
{ "detail": "ErrorCode.DELEGATION_TOKEN_INVALID: Invalid delegation token: The specified alg value is not allowed" }
```

**An ES256 token signed with an attacker's own key pair, carrying the right `kid`.** The `kid` only selects which configured key to try — it never stands in for a signature check:

```json
{ "detail": "ErrorCode.DELEGATION_TOKEN_INVALID: Invalid delegation token: Signature verification failed" }
```

**A genuine token from this issuer, minted for a different audience.** Same key, same algorithm, different `aud`:

```json
{ "detail": "ErrorCode.DELEGATION_TOKEN_INVALID: Invalid delegation token: Audience doesn't match" }
```

## Understanding the Code

### The issuer signs

`issuer.py` builds a `SigningConfig` around the private key. That object goes into the same `secret_key` slot a shared HMAC string used to occupy:

```python
signing_config = SigningConfig(
    keys=[
        JWTKey(
            kid="issuer-2026-08",
            algorithm=SigningAlgorithm.ES256,
            private_key=PRIVATE_KEY_PATH.read_text(),
            audience="gl-connectors",
        )
    ]
)
gateway = IAMGateway(agent_provider=provider, secret_key=signing_config)
```

Passing `audience=` on the mint selects the audience-bound key and stamps the value as `aud`:

```python
result = await gateway.delegate_to_agent(
    principal_token=principal.value,
    agent_id=AGENT_ID,
    task=task,
    scope=DelegationScope(scopes=request.scopes, expires_in_seconds=300),
    agent=demo_agent(),
    audience="gl-connectors",
)
```

### The verifier only verifies

`verifier.py` never sees a private key. It reads the issuer's JWKS at startup and builds its config from that:

```python
document = (await client.get(f"{ISSUER_URL}/.well-known/jwks.json")).json()
verification_config = SigningConfig.from_jwks(document, audience="gl-connectors")

gateway = IAMGateway.for_agent_auth(
    agent_provider=provider,
    secret_key=verification_config,
)
```

Every key imported from a JWKS is public-only — you do not have to remember to ask for that.

The `audience=` argument is worth a note. JWKS is a standard public-key document and has no audience member, so `to_jwks()` cannot export the binding and `from_jwks()` cannot restore it. **Expecting a particular audience is the verifier's own local policy**, declared where the verifier is configured.

### Why `enable_auth_hosting=False`

Both services configure the provider with:

```python
NativeConfig(
    database_url=...,
    default_org_id=ORG_ID,
    enable_third_party_provider=False,
    enable_auth_hosting=False,
)
```

`NativeConfig` requires a production-grade `secret_key` whenever it hosts user login, because that key signs session access tokens. Neither service here hosts login — they only handle agents — and this example deliberately has no shared secret anywhere, so auth hosting is switched off. Leave it on and `NativeConfig` will demand an HMAC secret it would never use.

### Key rotation

Put the retiring and the current key in one config, both with a `kid`, and name the one that should sign:

```python
SigningConfig(
    keys=[
        JWTKey(kid="issuer-2026-08", algorithm=SigningAlgorithm.ES256, private_key=new_pem),
        JWTKey(kid="issuer-2026-05", algorithm=SigningAlgorithm.ES256, private_key=old_pem),
    ],
    active_kid="issuer-2026-08",
)
```

New tokens are signed with `issuer-2026-08`; tokens still in flight under `issuer-2026-05` keep validating until they expire. Verifiers pick this up on their next JWKS fetch — publish the new key, wait longer than your token TTL, then drop the old one.

Every key in a multi-key config must set a `kid`. Without one a token cannot name the key it was signed with, and verification would degrade to trying keys in order.

## Migrating from a shared secret

Nothing about the string form was removed. A `secret_key="..."` produces byte-identical tokens to earlier releases, so a mixed fleet keeps working while you roll this out.

A workable order:

1. Generate the key pair; keep the HMAC secret in place.
2. Stand up the JWKS endpoint on the issuer, still signing HS256.
3. Point verifiers at the JWKS **in addition to** their existing secret, in whatever way your deployment allows (two gateways, or a config flag).
4. Switch the issuer's `secret_key` to the `SigningConfig`. Tokens now carry `alg: ES256` and a `kid`.
5. Remove the HMAC secret from every verifier. From this point on, none of them can mint.

Step 5 is the one that actually buys you anything — until it happens, the shared secret is still out there.

## Choosing an algorithm

ES256 is the default here: for the same security level the keys and signatures are markedly smaller than RSA's, and a delegation token travels on every agent call. RS256 is the right choice where RSA infrastructure already exists. Both are supported, along with RS384/512, PS256/384/512, ES384/512 and EdDSA.

Asymmetric algorithms need `cryptography`, which arrives with the `asymmetric` extra:

```toml
dependencies = ["gl-iam[fastapi,native,asymmetric]>=0.3.15,<0.4.0"]
```

Configure one without it and GL-IAM raises a `ConfigurationError` at construction, with the install hint — rather than an opaque PyJWT error at the first mint.

## Next Steps

- [agent-cross-service](../agent-cross-service/) — the same two-service split under a shared HMAC secret
- [agent-delegation-chain](../agent-delegation-chain/) — multi-hop delegation and scope attenuation
- [de-vertical-permission-gate](../de-vertical-permission-gate/) — enforcing scopes per tool inside a Digital Employee
- [Asymmetric Signing guide](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/guides/agent-iam/agent-authentication/asymmetric-signing) — the full reference
