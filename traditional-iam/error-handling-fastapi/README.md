# Error Handling with FastAPI

Explore the opt-in GL-IAM v1.2 response envelope, canonical error codes,
recovery guidance, and occurrence references. This example generates synthetic
failures; it needs no database, account, token, or running identity provider.

## Prerequisites

- Python 3.12 or 3.13 and [UV](https://docs.astral.sh/uv/).
- [GL-IAM 0.3.25](https://pypi.org/project/gl-iam/0.3.25/) or a later compatible
  0.3.x release. `uv sync` installs it from PyPI with the required FastAPI extra.

## Quick Start

```bash
cd traditional-iam/error-handling-fastapi
uv sync
uv run main.py
```

Open <http://localhost:8000/docs> to explore the routes.

## Testing the API

```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8000/errors/invalid_credentials
curl -i http://localhost:8000/errors/permission_denied
curl -i http://localhost:8000/errors/user_not_found
curl -i http://localhost:8000/errors/validation_error
curl -i http://localhost:8000/errors/rate_limited
curl -i http://localhost:8000/errors/configuration_error
curl -i http://localhost:8000/errors/not_supported
curl -i http://localhost:8000/errors/provider_error
curl -i http://localhost:8000/errors/provider_unavailable
```

| Scenario | HTTP status | What to observe |
| --- | --- | --- |
| `invalid_credentials` | 401 | Canonical code and `WWW-Authenticate: Bearer` |
| `permission_denied` | 403 | Safe message; no automatic replay |
| `user_not_found` | 404 | Missing resource remains distinguishable from an outage |
| `validation_error` | 400 | Correct the request before retrying |
| `rate_limited` | 429 | `Retry-After: 13`, numeric wait, bounded recovery |
| `configuration_error` | 500 | Support reference and non-retryable guidance |
| `not_supported` | 501 | Unsupported capability; no automatic replay |
| `provider_error` | 502 | Provider failure stays distinct from bad credentials |
| `provider_unavailable` | 503 | Transient failure with bounded recovery |

Each error has `schema_version: "1.2"`, `error_code`, `message`, `retryable`, and
`recovery`. The v1.2 envelope has no legacy `detail` or `error` alias. The health
route returns the normal success payload, and FastAPI request validation retains
its own response format.

Call `/errors/provider_unavailable` twice. Each response should have a different
`reference_id`, matching a JSON diagnostic in the server console. The reference
identifies an occurrence; it is not a trace ID. Neither the response nor the
diagnostic should contain `synthetic-private-provider-payload`. If recording
fails, the SDK keeps the error response, omits the reference, and reports
`diagnostic_status: "unavailable"`.

## Understanding the Code

`add_exception_handlers(app, error_policy="v1.2")` installs the HTTP policy.
The middleware separately selects `sdk_error_policy("safe")` for SDK-owned
errors and `diagnostic_context(...)` for service-owned diagnostic records.

`Error.from_safe_exception(...)` creates a safe SDK error with a private cause.
The route wraps it in a `Result` to demonstrate the same conversion needed after
a gateway call:

```python
if result.is_err:
    raise_for_error(result.error)
```

The registered handler selects status and public fields. Returning
`result.error.message`, reflecting the exception object, or calling `unwrap()`
on a failed Result bypasses this contract.

The example publishes recovery guidance without automatically retrying requests.
Clients must enforce the attempt budget, honor server waits, and establish
idempotency before replaying a write. See the [migration guide](../../ERROR_HANDLING.md)
for Django/DRF configuration, provider policy, and deployment verification.

## Next Steps

- Apply the pattern to [Native authentication](../fastapi-postgresql/).
- Compare [Django and DRF](../django-postgresql/).
- Try [agent delegation](../../agent-iam/agent-delegation-fastapi/).
- Remove these synthetic failure routes before adapting the example for production.
