import unittest

from fastapi.testclient import TestClient
from gl_iam.core.exceptions import AuthenticationError
from gl_iam.fastapi import get_current_user

from glchat_be import app


class AuthenticationErrorTests(unittest.TestCase):
    def test_run_agent_without_authorization_returns_401(self):
        async def missing_authorization():
            raise AuthenticationError("Missing or invalid authorization header")

        app.dependency_overrides[get_current_user] = missing_authorization
        client = TestClient(app, raise_server_exceptions=False)
        try:
            response = client.post(
                "/chat/run-agent",
                json={"agent_id": "missing-agent", "user_message": "test"},
            )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"detail": "Missing or invalid authorization header"},
        )


if __name__ == "__main__":
    unittest.main()
