"""Set Content-Security-Policy with dynamic `frame-ancestors`.

The widget route is loaded inside the partner's site. The set of partner
origins comes from the SDK-stored `partner.allowed_origins`. This middleware
aggregates all active partners' origins and emits a single CSP.

In a real deployment you'd derive this per-request based on the specific
partner identified by the widget's sso_token, but for a cookbook this
aggregate form is clearer and covers the "block arbitrary origins" goal.
"""

from __future__ import annotations

from fastapi import FastAPI, Request

from gl_iam.fastapi import get_iam_gateway

from glchat_backend.config import get_settings


async def _frame_ancestors(org_id: str) -> str:
    gateway = get_iam_gateway()
    result = await gateway.partner_registry.list_partners(organization_id=org_id, is_active=True)
    if result.is_err:
        return "'none'"
    origins: set[str] = set()
    for p in result.value:
        origins.update(p.allowed_origins or [])
    origins.add(get_settings().partner_site_origin)
    return " ".join(sorted(origins)) if origins else "'none'"


def register(app: FastAPI) -> None:
    settings = get_settings()

    @app.middleware("http")
    async def _csp(request: Request, call_next):
        response = await call_next(request)

        if request.url.path.startswith("/widget"):
            ancestors = await _frame_ancestors(settings.default_org_id)
            response.headers["Content-Security-Policy"] = f"frame-ancestors {ancestors}"
        else:
            response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
            response.headers.setdefault("X-Frame-Options", "DENY")

        return response
