"""Explore the GL-IAM v1.2 error contract without a database or identity provider."""

import logging
from typing import Literal

from fastapi import FastAPI, Request
from gl_iam.core.diagnostics import diagnostic_context
from gl_iam.core.error_carrier import raise_for_error
from gl_iam.core.sdk_errors import sdk_error_policy
from gl_iam.core.types.result import Error, ErrorCode, Result
from gl_iam.fastapi import add_exception_handlers
from pythonjsonlogger.jsonlogger import JsonFormatter

# Preserve the SDK's structured diagnostic fields, including reference_id and
# the separate trace_id. Configure your deployed collector to retain them too.
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
sdk_logger = logging.getLogger("gl_iam")
sdk_logger.addHandler(handler)
sdk_logger.setLevel(logging.INFO)
sdk_logger.propagate = False

app = FastAPI(title="GL-IAM Error Handling v1.2")
add_exception_handlers(app, error_policy="v1.2")


@app.middleware("http")
async def sdk_context(request: Request, call_next):
    """Scope SDK errors and diagnostic ownership to this request's async work."""
    with sdk_error_policy("safe"), diagnostic_context("cookbook-error-handling"):
        return await call_next(request)


Scenario = Literal[
    "invalid_credentials",
    "permission_denied",
    "user_not_found",
    "validation_error",
    "rate_limited",
    "configuration_error",
    "not_supported",
    "provider_error",
    "provider_unavailable",
]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/errors/{scenario}")
async def demonstrate_error(scenario: Scenario) -> None:
    """Generate a synthetic Result failure and pass it to the SDK HTTP handler.

    In an application, obtain the Result from an awaited gateway operation.
    Do not expose deliberate failure routes in a production service.
    """
    code = ErrorCode(scenario)
    details = {"wait_seconds": 12.2} if code == ErrorCode.RATE_LIMITED else None
    # This exception is synthetic operator context. Its prose must not appear
    # in the public response or the SDK's diagnostic record.
    error = Error.from_safe_exception(
        RuntimeError("synthetic-private-provider-payload"), code=code, details=details
    )
    result = Result.err(error)
    if result.is_err:
        # Preserve code, private cause and any existing occurrence reference.
        # Result.unwrap() raises ValueError on failure and is not an HTTP adapter.
        raise_for_error(result.error)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
