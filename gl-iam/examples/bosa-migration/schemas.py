"""Pydantic schemas for request/response models.

This module defines all request and response models for the BOSA migration example.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# User Schemas
# =============================================================================


class UserCreateRequest(BaseModel):
    """Request model for creating a user."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (min 8 characters)")
    display_name: str | None = Field(None, description="User display name")


class UserResponse(BaseModel):
    """Response model for user data."""

    id: str
    email: str
    display_name: str | None = None
    is_verified: bool = False
    created_at: datetime | None = None


# =============================================================================
# Authentication Schemas
# =============================================================================


class LoginRequest(BaseModel):
    """Request model for login."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """Response model for authentication tokens."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None


# =============================================================================
# API Key Schemas
# =============================================================================


class ApiKeyCreateRequest(BaseModel):
    """Request model for creating an API key."""

    name: str = Field(..., description="Human-readable name for the key")
    tier: str = Field(
        default="organization",
        description="API key tier: platform, organization, or personal",
    )
    scopes: list[str] = Field(
        default_factory=lambda: ["api:read"],
        description="Scopes to grant (e.g., ['keys:create', 'api:read', 'api:write'])",
    )
    user_id: str | None = Field(
        None,
        description="User ID (required for personal tier)",
    )
    expires_in_days: int | None = Field(
        None,
        description="Expiration in days (None = no expiry)",
    )


class ApiKeyResponse(BaseModel):
    """Response model for API key (without plain key)."""

    id: str
    name: str
    key_preview: str
    tier: str
    scopes: list[str]
    organization_id: str | None = None
    user_id: str | None = None
    is_active: bool = True
    expires_at: datetime | None = None
    created_at: datetime | None = None


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Response model for newly created API key (includes plain key)."""

    plain_key: str = Field(..., description="The plain API key (only shown once)")


# =============================================================================
# Third-Party Integration Schemas
# =============================================================================


class StoreIntegrationRequest(BaseModel):
    """Request model for storing a third-party integration."""

    connector: str = Field(
        ...,
        description="Third-party service name (e.g., 'github', 'slack', 'jira')",
    )
    auth_string: str = Field(
        ...,
        description="Authentication token/credentials (will be encrypted at rest)",
    )
    user_identifier: str = Field(
        ...,
        description="Account identifier in the third-party service (e.g., username)",
    )
    scopes: list[str] | None = Field(
        None,
        description="Granted scopes from the third-party service",
    )
    metadata: dict[str, Any] | None = Field(
        None,
        description="Additional metadata",
    )


class SetSelectedIntegrationRequest(BaseModel):
    """Request model for setting the selected integration."""

    connector: str = Field(..., description="Third-party service name")
    user_identifier: str = Field(
        ...,
        description="Account identifier to set as selected",
    )


class IntegrationResponse(BaseModel):
    """Response model for third-party integration."""

    id: str
    connector: str
    user_identifier: str
    auth_string_preview: str = Field(..., description="Masked preview of auth string")
    scopes: list[str] = Field(default_factory=list)
    is_selected: bool = False
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Health Check Schemas
# =============================================================================


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str = "healthy"
    database: bool = True
    api_key_provider: bool = True
    third_party_provider: bool = True
