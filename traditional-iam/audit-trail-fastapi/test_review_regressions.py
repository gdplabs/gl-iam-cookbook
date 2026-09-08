"""Regression tests for audit-aware example routes."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from fastapi import HTTPException

import main


class ChangePasswordRouteTests(IsolatedAsyncioTestCase):
    async def test_uses_gateway_change_password_and_reports_success(self) -> None:
        gateway = SimpleNamespace(change_password=AsyncMock(return_value=SimpleNamespace(is_err=False)))
        original_get_gateway = main.get_iam_gateway
        main.get_iam_gateway = lambda: gateway
        try:
            response = await main.change_password(
                main.ChangePasswordRequest(current_password="OldPass123!", new_password="NewPass456!"),
                SimpleNamespace(id="user-123"),
            )
        finally:
            main.get_iam_gateway = original_get_gateway

        gateway.change_password.assert_awaited_once_with(
            "user-123",
            "OldPass123!",
            "NewPass456!",
            organization_id="default",
        )
        self.assertIn("sign in again", response["message"].lower())

    async def test_does_not_report_success_when_gateway_rejects_change(self) -> None:
        gateway = SimpleNamespace(
            change_password=AsyncMock(
                return_value=SimpleNamespace(
                    is_err=True,
                    error=SimpleNamespace(message="Current password is incorrect"),
                )
            )
        )
        original_get_gateway = main.get_iam_gateway
        main.get_iam_gateway = lambda: gateway
        try:
            with self.assertRaises(HTTPException) as raised:
                await main.change_password(
                    main.ChangePasswordRequest(current_password="wrong", new_password="NewPass456!"),
                    SimpleNamespace(id="user-123"),
                )
        finally:
            main.get_iam_gateway = original_get_gateway

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "Current password is incorrect")
