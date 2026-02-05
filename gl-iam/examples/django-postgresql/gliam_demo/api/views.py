"""
GL-IAM Django Demo Views.

This module demonstrates three different Django view patterns with GL-IAM:

1. Function-Based Views (FBV) with decorators
2. Class-Based Views (CBV) with mixins
3. Django REST Framework (DRF) APIView with authentication/permission classes

All three patterns work with any GL-IAM provider (PostgreSQL, Keycloak, StackAuth).
"""

import os

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from gl_iam import StandardRole
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.django import (
    get_iam_gateway,
    gl_iam_login_required,
    require_org_admin,
    require_org_member,
    require_platform_admin,
    run_sync,
    GLIAMLoginRequiredMixin,
    OrgAdminRequiredMixin,
    OrgMemberRequiredMixin,
    PlatformAdminRequiredMixin,
)
from gl_iam.django.drf import (
    GLIAMAuthentication,
    IsGLIAMAuthenticated,
    IsOrgAdmin,
    IsOrgMember,
    IsPlatformAdmin,
)

from .serializers import (
    LoginSerializer,
    MessageResponseSerializer,
    RegisterSerializer,
    TokenResponseSerializer,
    UserResponseSerializer,
)


# ============================================================================
# Public Endpoints
# ============================================================================

def health(request):
    """Public health check endpoint."""
    return JsonResponse({"status": "healthy", "provider": "postgresql"})


@csrf_exempt
def register(request):
    """
    Register a new user (POST only).

    Creates a user, sets their password, and assigns the default ORG_MEMBER role.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    serializer = RegisterSerializer(data=data)
    if not serializer.is_valid():
        return JsonResponse({"errors": serializer.errors}, status=400)

    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID")

    # Create user via provider
    user = run_sync(gateway.user_store.create_user(
        UserCreateInput(
            email=serializer.validated_data["email"],
            display_name=serializer.validated_data.get("display_name")
            or serializer.validated_data["email"].split("@")[0],
        ),
        organization_id=org_id,
    ))

    # Set password
    run_sync(gateway.user_store.set_user_password(
        user.id, serializer.validated_data["password"], org_id
    ))

    # Assign default role
    run_sync(gateway.user_store.assign_role(
        user.id, StandardRole.ORG_MEMBER.value, org_id
    ))

    return JsonResponse({
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
    }, status=201)


@csrf_exempt
def login(request):
    """
    Authenticate and get access token (POST only).

    Validates credentials and returns a JWT access token on success.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    serializer = LoginSerializer(data=data)
    if not serializer.is_valid():
        return JsonResponse({"errors": serializer.errors}, status=400)

    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID")

    result = run_sync(gateway.authenticate(
        credentials=PasswordCredentials(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        ),
        organization_id=org_id,
    ))

    if result.is_ok:
        return JsonResponse({
            "access_token": result.token.access_token,
            "token_type": result.token.token_type,
        })
    else:
        return JsonResponse({"error": result.error.message}, status=401)


# ============================================================================
# Pattern 1: Function-Based Views with Decorators
# ============================================================================

@gl_iam_login_required
def me_fbv(request):
    """
    Get current user profile (FBV pattern).

    Uses @gl_iam_login_required decorator for authentication.
    The authenticated user is available via request.gl_iam_user.
    """
    user = request.gl_iam_user
    return JsonResponse({
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "pattern": "FBV with decorator",
    })


@gl_iam_login_required
@require_org_member()
def member_area_fbv(request):
    """
    Member area endpoint (FBV pattern).

    Uses @require_org_member() decorator for RBAC.
    Accessible by ORG_MEMBER, ORG_ADMIN, or PLATFORM_ADMIN.
    """
    user = request.gl_iam_user
    return JsonResponse({
        "message": f"Welcome {user.email}!",
        "access_level": "member",
        "pattern": "FBV with decorator",
    })


@gl_iam_login_required
@require_org_admin()
def admin_area_fbv(request):
    """
    Admin area endpoint (FBV pattern).

    Uses @require_org_admin() decorator for RBAC.
    Accessible by ORG_ADMIN or PLATFORM_ADMIN only.
    """
    user = request.gl_iam_user
    return JsonResponse({
        "message": f"Welcome Admin {user.email}!",
        "access_level": "admin",
        "pattern": "FBV with decorator",
    })


@gl_iam_login_required
@require_platform_admin()
def platform_admin_fbv(request):
    """
    Platform admin endpoint (FBV pattern).

    Uses @require_platform_admin() decorator for RBAC.
    Accessible by PLATFORM_ADMIN only.
    """
    user = request.gl_iam_user
    return JsonResponse({
        "message": f"Welcome Platform Admin {user.email}!",
        "access_level": "platform_admin",
        "pattern": "FBV with decorator",
    })


# ============================================================================
# Pattern 2: Class-Based Views with Mixins
# ============================================================================

@method_decorator(csrf_exempt, name="dispatch")
class MeCBV(GLIAMLoginRequiredMixin, View):
    """
    Get current user profile (CBV pattern).

    Uses GLIAMLoginRequiredMixin for authentication.
    The authenticated user is available via self.request.gl_iam_user.
    """

    def get(self, request):
        user = request.gl_iam_user
        return JsonResponse({
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "pattern": "CBV with mixin",
        })


@method_decorator(csrf_exempt, name="dispatch")
class MemberAreaCBV(OrgMemberRequiredMixin, View):
    """
    Member area endpoint (CBV pattern).

    Uses OrgMemberRequiredMixin for authentication + RBAC.
    Accessible by ORG_MEMBER, ORG_ADMIN, or PLATFORM_ADMIN.
    """

    def get(self, request):
        user = request.gl_iam_user
        return JsonResponse({
            "message": f"Welcome {user.email}!",
            "access_level": "member",
            "pattern": "CBV with mixin",
        })


@method_decorator(csrf_exempt, name="dispatch")
class AdminAreaCBV(OrgAdminRequiredMixin, View):
    """
    Admin area endpoint (CBV pattern).

    Uses OrgAdminRequiredMixin for authentication + RBAC.
    Accessible by ORG_ADMIN or PLATFORM_ADMIN only.
    """

    def get(self, request):
        user = request.gl_iam_user
        return JsonResponse({
            "message": f"Welcome Admin {user.email}!",
            "access_level": "admin",
            "pattern": "CBV with mixin",
        })


@method_decorator(csrf_exempt, name="dispatch")
class PlatformAdminCBV(PlatformAdminRequiredMixin, View):
    """
    Platform admin endpoint (CBV pattern).

    Uses PlatformAdminRequiredMixin for authentication + RBAC.
    Accessible by PLATFORM_ADMIN only.
    """

    def get(self, request):
        user = request.gl_iam_user
        return JsonResponse({
            "message": f"Welcome Platform Admin {user.email}!",
            "access_level": "platform_admin",
            "pattern": "CBV with mixin",
        })


# ============================================================================
# Pattern 3: Django REST Framework APIView
# ============================================================================

class MeAPIView(APIView):
    """
    Get current user profile (DRF pattern).

    Uses GLIAMAuthentication for token validation and
    IsGLIAMAuthenticated for permission checking.
    """

    authentication_classes = [GLIAMAuthentication]
    permission_classes = [IsGLIAMAuthenticated]

    def get(self, request):
        user = request.gl_iam_user
        return Response({
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "pattern": "DRF APIView",
        })


class MemberAreaAPIView(APIView):
    """
    Member area endpoint (DRF pattern).

    Uses IsOrgMember permission class for RBAC.
    Accessible by ORG_MEMBER, ORG_ADMIN, or PLATFORM_ADMIN.
    """

    authentication_classes = [GLIAMAuthentication]
    permission_classes = [IsOrgMember]

    def get(self, request):
        user = request.gl_iam_user
        return Response({
            "message": f"Welcome {user.email}!",
            "access_level": "member",
            "pattern": "DRF APIView",
        })


class AdminAreaAPIView(APIView):
    """
    Admin area endpoint (DRF pattern).

    Uses IsOrgAdmin permission class for RBAC.
    Accessible by ORG_ADMIN or PLATFORM_ADMIN only.
    """

    authentication_classes = [GLIAMAuthentication]
    permission_classes = [IsOrgAdmin]

    def get(self, request):
        user = request.gl_iam_user
        return Response({
            "message": f"Welcome Admin {user.email}!",
            "access_level": "admin",
            "pattern": "DRF APIView",
        })


class PlatformAdminAPIView(APIView):
    """
    Platform admin endpoint (DRF pattern).

    Uses IsPlatformAdmin permission class for RBAC.
    Accessible by PLATFORM_ADMIN only.
    """

    authentication_classes = [GLIAMAuthentication]
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        user = request.gl_iam_user
        return Response({
            "message": f"Welcome Platform Admin {user.email}!",
            "access_level": "platform_admin",
            "pattern": "DRF APIView",
        })


# ============================================================================
# DRF Registration and Login (for completeness)
# ============================================================================

class RegisterAPIView(APIView):
    """
    Register a new user (DRF pattern).

    Creates a user, sets their password, and assigns the default ORG_MEMBER role.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        gateway = get_iam_gateway()
        org_id = os.getenv("DEFAULT_ORGANIZATION_ID")

        # Create user via provider
        user = run_sync(gateway.user_store.create_user(
            UserCreateInput(
                email=serializer.validated_data["email"],
                display_name=serializer.validated_data.get("display_name")
                or serializer.validated_data["email"].split("@")[0],
            ),
            organization_id=org_id,
        ))

        # Set password
        run_sync(gateway.user_store.set_user_password(
            user.id, serializer.validated_data["password"], org_id
        ))

        # Assign default role
        run_sync(gateway.user_store.assign_role(
            user.id, StandardRole.ORG_MEMBER.value, org_id
        ))

        response_serializer = UserResponseSerializer({
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
        })
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    """
    Authenticate and get access token (DRF pattern).

    Validates credentials and returns a JWT access token on success.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        gateway = get_iam_gateway()
        org_id = os.getenv("DEFAULT_ORGANIZATION_ID")

        result = run_sync(gateway.authenticate(
            credentials=PasswordCredentials(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
            ),
            organization_id=org_id,
        ))

        if result.is_ok:
            response_serializer = TokenResponseSerializer({
                "access_token": result.token.access_token,
                "token_type": result.token.token_type,
            })
            return Response(response_serializer.data)
        else:
            return Response(
                {"error": result.error.message},
                status=status.HTTP_401_UNAUTHORIZED,
            )
