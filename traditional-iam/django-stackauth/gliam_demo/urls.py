"""
Root URL configuration for GL-IAM Demo project with Stack Auth.
"""

from django.urls import include, path

urlpatterns = [
    path("", include("gliam_demo.api.urls")),
]
