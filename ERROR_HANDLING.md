# Adopting GL-IAM Error Handling v1.2

The migrated Traditional IAM and Agent IAM web examples follow merged SDK PR
[#7656](https://github.com/GDP-ADMIN/gl-sdk/pull/7656) at commit
[`be886b474658bab818760bef95c684e536805442`](https://github.com/GDP-ADMIN/gl-sdk/commit/be886b474658bab818760bef95c684e536805442).
Start with the [standalone error-handling example](traditional-iam/error-handling-fastapi/)
to inspect the contract without external services.

## Dependency baseline

PR #7656 merged on 2026-10-26. GitHub release
[`gl_iam-v0.3.25`](https://github.com/GDP-ADMIN/gl-sdk/releases/tag/gl_iam-v0.3.25)
points to the same commit. As of that date, PyPI does not yet list 0.3.25, so
examples using the new APIs pin this Git revision in `pyproject.toml`, retaining
their existing extras. Installing them requires Git access to `GDP-ADMIN/gl-sdk`.
Configure your normal Git credentials first, then run `uv sync`; never embed a
token in the URL or commit credentials.

These examples require **Python 3.12 or 3.13** (`>=3.12,<3.14`), matching the
merged SDK. Python 3.11 is no longer supported. Upgrade your runtime and
deployment image, recreate any Python 3.11 virtual environment, and run
`uv sync --python 3.12` (or `--python 3.13`) to resolve dependencies again.

The source package reports `0.0.0`; use the Git commit to identify this baseline.
Once 0.3.25 is available on PyPI, replace the Git requirement with
`gl-iam[YOUR_EXTRAS]>=0.3.25,<0.4.0`, keeping each example's actual extras, and
resolve dependencies and recheck the examples. Examples without this migration
note, including the explorations, retain their existing dependency and error behavior.

## FastAPI: preserve the error at the boundary

Register the policy once at app construction and convert failed Results:

```python
from fastapi import FastAPI
from gl_iam.core.error_carrier import raise_for_error
from gl_iam.fastapi import add_exception_handlers

app = FastAPI()
add_exception_handlers(app, error_policy="v1.2")

# Inside an endpoint, after an IAMGateway call:
if result.is_err:
    raise_for_error(result.error)
```

Let typed `GLIAMError` subclasses from direct provider calls reach the same
handler. Do not turn them into `HTTPException(detail=str(exc))`, infer status
from message text, or force every login failure to 401. `raise_for_error`
preserves the canonical code, private cause, and diagnostic provenance. A
failed `Result.unwrap()` raises `ValueError` and is not a substitute.

This policy handles SDK exceptions. Application-owned `HTTPException` responses,
ordinary success payloads, and framework validation responses retain their
existing formats. Deliberate denial routes in the agent lifecycle and constraint
examples now use non-2xx SDK responses instead of HTTP 200 with `status: denied`.

## Django and DRF

Keep existing middleware and REST settings, and add:

```python
GL_IAM_HTTP_ERROR_POLICY = "v1.2"

MIDDLEWARE = [
    "gl_iam.django.exceptions.GLIAMExceptionMiddleware",
    # Existing security, authentication and other middleware follow.
]

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "gl_iam.django.exceptions.gl_iam_drf_exception_handler",
    # Keep the application's other REST_FRAMEWORK entries.
}
```

Raise typed exceptions or use `raise_for_error(result.error)` in views. The
middleware handles Django views; DRF needs its registered handler to retain
the envelope and recovery headers. The cookbook configures both.

## Provider and direct SDK policies are separate

The Keycloak and Stack Auth examples also select `error_policy="typed"` in
their provider configurations. This distinguishes rejected end-user credentials
from rate limits, SDK credential misconfiguration, outages, and malformed
provider responses. An inactive token can still mean an anonymous user;
optional authentication propagates infrastructure and rate-limit failures.

The HTTP policy does not enable safe in-process SDK errors. For direct SDK
consumers, use an ordinary context manager around awaited calls:

```python
from gl_iam.core.sdk_errors import sdk_error_policy

with sdk_error_policy("safe"):
    result = await gateway.validate_session(token, organization_id=organization_id)

if result.is_err:
    public_error = result.error.to_public_dict()
```

`to_public_dict()` is an SDK projection with `code`, `message`, and safe details;
it is not the HTTP envelope. Use the HTTP handler for HTTP responses. The BOSA
migration and standalone error example scope safe SDK mode around requests.
Other examples demonstrate the HTTP and provider policies without implicitly
opting all background SDK work into safe mode. Start background tasks inside
the desired context; existing tasks do not acquire it retroactively.

## Client migration

Branch on `error_code` and display `message`. The v1.2 envelope uses
`schema_version: "1.2"` and removes framework-specific `detail`/`error` duplicates.
Treat `details`, `reference_id`, and `diagnostic_status` as optional. Do not parse
message text or reconstruct old exception messages.

| Canonical code | v1.2 status | Client action |
| --- | --- | --- |
| `invalid_credentials`, `session_expired` | 401 | Sign in again |
| `permission_denied`, `scope_escalation_denied` | 403 | Obtain permission or narrow the request |
| `user_not_found`, `role_not_found` | 404 | Check the resource identifier |
| `user_already_exists`, `role_already_exists` | 409 | Use the existing resource or another identifier |
| `validation_error`, `invalid_token_lifetime` | 400 | Correct the input |
| `rate_limited` | 429 | Honor `Retry-After` and bounded recovery |
| `configuration_error` | 500 | Contact the service operator |
| `not_supported` | 501 | Use a supported capability |
| `provider_error` | 502 | Follow the returned recovery guidance |
| `provider_unavailable` | 503 | Follow the returned recovery guidance |

Use `recovery.action` and its attempt/wait limits; `retryable` alone never
authorizes replaying a write. Require an established idempotency guarantee,
count the initial invocation in `max_attempts`, and include SDK transport retries
in the end-to-end budget. Do not shorten a server wait to fit a deadline; stop
or schedule later. A DPoP nonce challenge requires a fresh signed proof with the
issued `DPoP-Nonce` and permits at most one retry. Do not retry an unchanged proof.

## Diagnostics and verification

A 5xx response carries an occurrence `reference_id` when recording succeeds.
If recording fails, it instead reports `diagnostic_status: "unavailable"`;
the original status/code remains usable. Display a support reference only when
one is present, and never fabricate one from the request or trace ID.

The standalone example configures a JSON logger that preserves SDK extra fields.
Production exporters must retain the approved schema, including service,
operation, canonical code, occurrence reference, and separate trace ID. Never
serialize private causes or log them with raw `exc_info`.

For adoption, record the deployed SDK commit/version, verify representative
credential/rate-limit/outage failures, and look up a synthetic response reference
in the centralized diagnostic sink. Check that repeated failures have distinct
references, sensitive canary text is absent, and a failing diagnostic sink keeps
the response usable. Local cookbook probes do not establish live-provider,
staging, or centralized-exporter acceptance.

For the full contracts, see the pinned SDK's
[HTTP policy](https://github.com/GDP-ADMIN/gl-sdk/blob/be886b474658bab818760bef95c684e536805442/libs/gl-iam/docs/reference/HTTP_ERROR_POLICY_V12.md),
[provider policy](https://github.com/GDP-ADMIN/gl-sdk/blob/be886b474658bab818760bef95c684e536805442/libs/gl-iam/docs/reference/PROVIDER_ERROR_POLICY.md), and
[safe SDK errors](https://github.com/GDP-ADMIN/gl-sdk/blob/be886b474658bab818760bef95c684e536805442/libs/gl-iam/docs/reference/SAFE_SDK_ERRORS.md).
