"""
DRF Serializers for request/response validation.
"""

from rest_framework import serializers


class UserResponseSerializer(serializers.Serializer):
    """Response serializer for user data with roles."""

    id = serializers.CharField()
    email = serializers.EmailField()
    display_name = serializers.CharField(allow_null=True)
    roles = serializers.ListField(child=serializers.CharField())


class MessageResponseSerializer(serializers.Serializer):
    """Response serializer for simple messages."""

    message = serializers.CharField()
    access_level = serializers.CharField()
