"""Authentication endpoints (login/logout).

BOSA Migration Mapping:
- authenticate_user() -> POST /api/auth/login
- create_token() -> POST /api/auth/login (returns JWT)
- revoke_token() -> POST /api/auth/logout
"""

from fastapi import APIRouter, HTTPException, status

from gl_iam.core.types import PasswordCredentials

from config import settings
from deps import CurrentUserDep, provider
from schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate user and get access token.

    BOSA Equivalent: authenticate_user() + create_token()

    This endpoint:
    1. Validates user credentials (authenticate_user)
    2. Creates a JWT session (create_token)
    3. Returns the access token

    Args:
        request: Login request with email and password.

    Returns:
        TokenResponse with JWT access token.
    """
    try:
        # 1. Authenticate user (BOSA: authenticate_user)
        external_identity = await provider.authenticate(
            credentials=PasswordCredentials(
                email=request.email,
                password=request.password,
            ),
            organization_id=settings.default_organization_id,
        )

        # 2. Get full user object
        user = await provider.get_user_by_id(
            external_identity.external_id,
            settings.default_organization_id,
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        # 3. Create session (BOSA: create_token)
        auth_token = await provider.create_session(
            user=user,
            organization_id=settings.default_organization_id,
        )

        # Calculate expires_in from expires_at if available
        expires_in = None
        if auth_token.expires_at:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            expires_at = auth_token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            expires_in = int((expires_at - now).total_seconds())

        return TokenResponse(
            access_token=auth_token.access_token,
            token_type=auth_token.token_type,
            expires_in=expires_in,
        )

    except Exception as e:
        error_msg = str(e).lower()
        if "invalid" in error_msg or "credentials" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(user: CurrentUserDep):
    """Logout and revoke current session.

    BOSA Equivalent: revoke_token()

    Requires Bearer token authentication. The current session will be
    invalidated and cannot be used again.

    Args:
        user: Current authenticated user (validates token exists).
    """
    # Note: In a real implementation, we would need access to the token
    # to revoke it. For this example, we'll revoke all sessions for the user.
    await provider.revoke_all_sessions(
        user_id=user.id,
        organization_id=settings.default_organization_id,
    )


@router.get("/sessions")
async def get_active_sessions(user: CurrentUserDep):
    """Get all active sessions for the current user.

    Requires Bearer token authentication.

    Args:
        user: Current authenticated user.

    Returns:
        List of active sessions.
    """
    sessions = await provider.get_active_sessions(
        user_id=user.id,
        organization_id=settings.default_organization_id,
    )
    return {"sessions": sessions}
