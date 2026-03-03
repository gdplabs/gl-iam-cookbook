"""URL configuration for GL-IAM Agent Delegation demo."""

from django.urls import include, path

urlpatterns = [
    path("", include("gliam_demo.api.urls")),
]
