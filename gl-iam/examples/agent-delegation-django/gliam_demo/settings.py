"""
Django settings for GL-IAM Agent Delegation demo.

This demonstrates GL-IAM middleware configuration for agent delegation.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-change-me")

DEBUG = os.getenv("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = ["*"]

# ============================================================================
# Installed Apps
# ============================================================================
INSTALLED_APPS = [
    "rest_framework",
    "gliam_demo.api",
]

# ============================================================================
# Middleware - includes GL-IAM auth AND agent middleware
# ============================================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "gl_iam.django.middleware.GLIAMAuthenticationMiddleware",
    "gl_iam.django.agent_middleware.GLIAMAgentMiddleware",
]

ROOT_URLCONF = "gliam_demo.urls"

WSGI_APPLICATION = "gliam_demo.wsgi.application"

# ============================================================================
# Database - SQLite for Django internals only
# GL-IAM manages its own PostgreSQL tables
# ============================================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ============================================================================
# Django REST Framework
# ============================================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}

# ============================================================================
# GL-IAM Settings
# ============================================================================
GL_IAM = {
    "DEFAULT_ORGANIZATION_ID": os.getenv("DEFAULT_ORGANIZATION_ID", "org-123"),
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
