"""
DRF Serializers for request/response validation.
"""

from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    """Request serializer for user registration."""

    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    display_name = serializers.CharField(max_length=100, required=False, allow_blank=True)


class LoginSerializer(serializers.Serializer):
    """Request serializer for user login."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TokenResponseSerializer(serializers.Serializer):
    """Response serializer containing access token."""

    access_token = serializers.CharField()
    token_type = serializers.CharField()


class UserResponseSerializer(serializers.Serializer):
    """Response serializer for user data."""

    id = serializers.CharField()
    email = serializers.EmailField()
    display_name = serializers.CharField(allow_null=True)


class MessageResponseSerializer(serializers.Serializer):
    """Response serializer for simple messages."""

    message = serializers.CharField()
