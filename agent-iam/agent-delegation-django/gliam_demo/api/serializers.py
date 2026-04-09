"""Serializers for GL-IAM Agent Delegation demo."""

from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration."""

    email = serializers.EmailField()
    password = serializers.CharField()
    display_name = serializers.CharField(required=False, allow_null=True)


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""

    email = serializers.EmailField()
    password = serializers.CharField()


class TokenResponseSerializer(serializers.Serializer):
    """Serializer for token response."""

    access_token = serializers.CharField()
    token_type = serializers.CharField()


class UserResponseSerializer(serializers.Serializer):
    """Serializer for user response."""

    id = serializers.CharField()
    email = serializers.CharField()
    display_name = serializers.CharField(allow_null=True)


class MessageResponseSerializer(serializers.Serializer):
    """Serializer for message response."""

    message = serializers.CharField()


class AgentRegisterSerializer(serializers.Serializer):
    """Serializer for agent registration."""

    name = serializers.CharField()
    agent_type = serializers.CharField(default="worker")
    allowed_scopes = serializers.ListField(child=serializers.CharField(), default=[])


class DelegateSerializer(serializers.Serializer):
    """Serializer for delegation."""

    agent_id = serializers.CharField()
    scopes = serializers.ListField(child=serializers.CharField(), default=[])
