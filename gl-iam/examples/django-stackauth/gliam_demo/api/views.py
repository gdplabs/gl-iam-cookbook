"""
GL-IAM Django Demo Views with Stack Auth.

This module demonstrates three different Django view patterns with GL-IAM:

1. Function-Based Views (FBV) with decorators
2. Class-Based Views (CBV) with mixins
3. Django REST Framework (DRF) APIView with authentication/permission classes

All three patterns work with any GL-IAM provider (PostgreSQL, Keycloak, StackAuth).
This demonstrates the SIMI (Single Interface Multiple Implementation) pattern -
the same view code works regardless of which provider you use.
"""

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework.views import APIView

from gl_iam.django import (
    gl_iam_login_required,
    require_org_admin,
    require_org_member,
    require_platform_admin,
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


# ============================================================================
# Public Endpoints
# ============================================================================

def health(request):
    """Public health check endpoint."""
    return JsonResponse({"status": "healthy", "provider": "stackauth"})


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
        "roles": user.roles,
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
            "roles": user.roles,
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
            "roles": user.roles,
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
