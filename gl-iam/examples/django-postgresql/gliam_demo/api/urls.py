"""
URL configuration for GL-IAM Demo API.

This demonstrates three different routing patterns corresponding to
the three view patterns (FBV, CBV, DRF).
"""

from django.urls import path

from . import views

urlpatterns = [
    # Public endpoints
    path("health/", views.health, name="health"),

    # Registration and Login (FBV - simple functions)
    path("api/register/", views.register, name="register"),
    path("api/login/", views.login, name="login"),

    # Pattern 1: Function-Based Views with Decorators
    path("api/fbv/me/", views.me_fbv, name="me-fbv"),
    path("api/fbv/member-area/", views.member_area_fbv, name="member-area-fbv"),
    path("api/fbv/admin-area/", views.admin_area_fbv, name="admin-area-fbv"),
    path("api/fbv/platform-admin/", views.platform_admin_fbv, name="platform-admin-fbv"),

    # Pattern 2: Class-Based Views with Mixins
    path("api/cbv/me/", views.MeCBV.as_view(), name="me-cbv"),
    path("api/cbv/member-area/", views.MemberAreaCBV.as_view(), name="member-area-cbv"),
    path("api/cbv/admin-area/", views.AdminAreaCBV.as_view(), name="admin-area-cbv"),
    path("api/cbv/platform-admin/", views.PlatformAdminCBV.as_view(), name="platform-admin-cbv"),

    # Pattern 3: Django REST Framework APIView
    path("api/drf/me/", views.MeAPIView.as_view(), name="me-drf"),
    path("api/drf/member-area/", views.MemberAreaAPIView.as_view(), name="member-area-drf"),
    path("api/drf/admin-area/", views.AdminAreaAPIView.as_view(), name="admin-area-drf"),
    path("api/drf/platform-admin/", views.PlatformAdminAPIView.as_view(), name="platform-admin-drf"),

    # DRF versions of register/login (alternative)
    path("api/drf/register/", views.RegisterAPIView.as_view(), name="register-drf"),
    path("api/drf/login/", views.LoginAPIView.as_view(), name="login-drf"),

    # Convenience aliases (use FBV pattern by default)
    path("api/me/", views.me_fbv, name="me"),
    path("api/member-area/", views.member_area_fbv, name="member-area"),
    path("api/admin-area/", views.admin_area_fbv, name="admin-area"),
    path("api/platform-admin/", views.platform_admin_fbv, name="platform-admin"),
]
