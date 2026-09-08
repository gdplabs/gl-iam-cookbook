"""Regression test for the audit-aware reactivation route."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

import main


class ReactivateAgentRouteTests(IsolatedAsyncioTestCase):
    async def test_uses_gateway_reactivate_agent(self) -> None:
        gateway = SimpleNamespace(reactivate_agent=AsyncMock(return_value=SimpleNamespace(is_ok=True)))
        original_get_gateway = main.get_iam_gateway
        main.get_iam_gateway = lambda: gateway
        try:
            response = await main.reactivate_agent("agent-123", SimpleNamespace(id="user-123"))
        finally:
            main.get_iam_gateway = original_get_gateway

        gateway.reactivate_agent.assert_awaited_once_with("agent-123", organization_id="default")
        self.assertEqual(response["status"], "active")
