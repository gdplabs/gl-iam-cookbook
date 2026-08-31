"""
Drive the whole multi-tenant story against the running server.

Each numbered act is one thing worth understanding about dynamic role
management. Deny paths are included on purpose: an example that only shows the
happy path teaches you what works, not where the boundaries are.

    uv run seed.py
    uv run main.py          # in one terminal
    uv run walkthrough.py   # in another
"""

import asyncio
import sys

import httpx

from config import settings

A = settings.tenant_a_id
B = settings.tenant_b_id


class Client:
    """A thin wrapper that prints every call and its outcome."""

    def __init__(self, http: httpx.AsyncClient, token: str, who: str) -> None:
        """Bind a token to a display name so the transcript names the actor."""
        self._http = http
        self._who = who
        self._headers = {"Authorization": f"Bearer {token}"}

    async def call(self, method: str, path: str, *, expect: int = 200, json: dict | None = None) -> dict | list:
        """Issue one request, assert the status, and narrate the result.

        Args:
            method: HTTP method.
            path: Path relative to the API base URL.
            expect: The status this step is demonstrating. A mismatch stops the
                walkthrough — a deny path that stops denying is a real problem,
                not a cosmetic one.
            json: Optional request body.

        Returns:
            The decoded response body.

        Raises:
            SystemExit: If the status doesn't match `expect`.
        """
        response = await self._http.request(method, path, headers=self._headers, json=json)
        ok = response.status_code == expect
        mark = "  ok " if ok else "FAIL "
        print(f"{mark}{self._who:<22} {method:<6} {path} -> {response.status_code} (expected {expect})")
        if not ok:
            print(f"       body: {response.text}")
            sys.exit(1)
        return response.json() if response.content else {}


async def login(http: httpx.AsyncClient, email: str, password: str, organization_id: str, who: str) -> Client:
    """Log in within one organization and return a narrating client."""
    response = await http.post(
        "/login", json={"email": email, "password": password, "organization_id": organization_id}
    )
    response.raise_for_status()
    return Client(http, response.json()["access_token"], who)


def act(number: int, title: str) -> None:
    """Print an act heading."""
    print(f"\n{'=' * 78}\n{number}. {title}\n{'=' * 78}")


async def main() -> None:  # noqa: PLR0915 — a linear narrative reads better unsplit
    """Run every act in order."""
    async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=30.0) as http:
        platform = await login(
            http, settings.platform_admin_email, settings.platform_admin_password, A, "platform-admin"
        )
        admin_a = await login(http, settings.org_admin_email(A), settings.org_admin_password, A, f"org-admin@{A}")
        admin_b = await login(http, settings.org_admin_email(B), settings.org_admin_password, B, f"org-admin@{B}")
        member_a = await login(http, settings.member_email(A), settings.member_password, A, f"member@{A}")

        member_a_id = (await member_a.call("GET", f"/orgs/{A}/me"))["id"]

        act(1, "Define permissions, then a role that carries them — per tenant")
        for tenant in (A, B):
            for permission in ("bookings:read", "bookings:write", "reports:read"):
                await platform.call(
                    "POST",
                    f"/orgs/{tenant}/permissions",
                    expect=201,
                    json={"name": permission, "description": f"{permission} in {tenant}"},
                )

        # Same name in both tenants, deliberately different authority. This is
        # what "organization-scoped" buys you.
        await platform.call(
            "POST",
            f"/orgs/{A}/roles",
            expect=201,
            json={
                "name": "property_manager",
                "description": f"Runs {A} end to end",
                "permissions": ["bookings:read", "bookings:write"],
            },
        )
        await platform.call(
            "POST",
            f"/orgs/{B}/roles",
            expect=201,
            json={
                "name": "property_manager",
                "description": f"Read-only oversight at {B}",
                "permissions": ["bookings:read"],
            },
        )

        act(2, "The two roles share a name and nothing else")
        role_a = await platform.call("GET", f"/orgs/{A}/roles/property_manager")
        role_b = await platform.call("GET", f"/orgs/{B}/roles/property_manager")
        print(f"       {A}: {role_a['permissions']}")
        print(f"       {B}: {role_b['permissions']}")
        assert role_a["permissions"] != role_b["permissions"], "tenant isolation broken"

        act(3, "An ORG_ADMIN can assign an existing role — this always worked")
        await admin_a.call(
            "POST", f"/orgs/{A}/roles/assign", json={"user_id": member_a_id, "role": "property_manager"}
        )
        me = await member_a.call("GET", f"/orgs/{A}/me")
        print(f"       effective roles: {me['effective_roles']}")
        print(f"       permissions:     {me['permissions']}")

        act(4, "Assigning twice is a no-op success, not an error")
        again = await admin_a.call(
            "POST", f"/orgs/{A}/roles/assign", json={"user_id": member_a_id, "role": "property_manager"}
        )
        print(f"       changed={again['changed']} — {again['detail']}")

        act(5, "An ORG_ADMIN may not define roles, or grant a standard one")
        await admin_a.call(
            "POST", f"/orgs/{A}/roles", expect=403, json={"name": "shadow_admin", "permissions": []}
        )
        # The guard that stops an org admin minting a platform admin.
        await admin_a.call(
            "POST", f"/orgs/{A}/roles/assign", expect=403, json={"user_id": member_a_id, "role": "platform_admin"}
        )

        act(6, "Tenants cannot reach into each other")
        # B's admin is not a member of A. GL-IAM's *read* operations take no
        # caller_id and enforce nothing, so this 403 comes from the app's own
        # check in deps.get_tenant_user — see its docstring for why that check
        # has to exist.
        await admin_b.call("GET", f"/orgs/{A}/roles", expect=403)
        # Writes are enforced by the SDK itself, with no help from the app.
        await admin_b.call(
            "POST", f"/orgs/{A}/roles/assign", expect=403, json={"user_id": member_a_id, "role": "property_manager"}
        )
        # And even the platform admin, who legitimately spans both tenants,
        # finds nothing under the wrong one: a role name resolves within one
        # organization, not across all of them.
        await platform.call("GET", f"/orgs/{B}/roles/front_desk", expect=404)

        act(7, "Grant one more permission without restating the set")
        await platform.call(
            "POST",
            f"/orgs/{A}/permissions/grant",
            json={"role_name": "property_manager", "permission_name": "reports:read"},
        )
        me = await member_a.call("GET", f"/orgs/{A}/me")
        print(f"       permissions now: {me['permissions']}")

        act(8, "PATCH replaces the whole grant set — the sharp edge")
        await platform.call(
            "PATCH", f"/orgs/{A}/roles/property_manager", json={"permissions": ["bookings:read"]}
        )
        me = await member_a.call("GET", f"/orgs/{A}/me")
        print(f"       permissions now: {me['permissions']}  <- write and reports were dropped")
        await platform.call(
            "PATCH",
            f"/orgs/{A}/roles/property_manager",
            json={"permissions": ["bookings:read", "bookings:write", "reports:read"]},
        )

        act(9, "Deactivate: the role stops granting, the assignment survives")
        await platform.call("POST", f"/orgs/{A}/roles/property_manager/deactivate")
        me = await member_a.call("GET", f"/orgs/{A}/me")
        print(f"       effective_roles: {me['effective_roles']}  <- gone")
        print(f"       assigned_roles:  {me['assigned_roles']}  <- retained")
        print(f"       permissions:     {me['permissions']}  <- gone with the role")
        # And it can no longer be handed to anyone new.
        await admin_a.call(
            "POST", f"/orgs/{A}/roles/assign", expect=404, json={"user_id": member_a_id, "role": "property_manager"}
        )

        act(10, "Reactivate: everything comes back, untouched")
        await platform.call("POST", f"/orgs/{A}/roles/property_manager/activate")
        me = await member_a.call("GET", f"/orgs/{A}/me")
        print(f"       effective roles: {me['effective_roles']}")
        print(f"       permissions:     {me['permissions']}")

        act(11, "System roles are immutable, and their names are reserved")
        await platform.call("DELETE", f"/orgs/{A}/roles/org_admin", expect=403)
        await platform.call("POST", f"/orgs/{A}/roles", expect=409, json={"name": "org_admin", "permissions": []})

        act(12, "Delete is the irreversible one")
        await admin_a.call(
            "POST", f"/orgs/{A}/roles/remove", json={"user_id": member_a_id, "role": "property_manager"}
        )
        await platform.call("DELETE", f"/orgs/{A}/roles/property_manager")
        await platform.call("GET", f"/orgs/{A}/roles/property_manager", expect=404)

        print("\nWalkthrough complete. Re-run `uv run seed.py` and this script to start over.")


if __name__ == "__main__":
    asyncio.run(main())
