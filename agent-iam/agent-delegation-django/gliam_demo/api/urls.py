"""URL configuration for GL-IAM Agent Delegation demo API."""

from django.urls import path

from . import views

urlpatterns = [
    # Public endpoints
    path("health/", views.health, name="health"),
    path("api/register/", views.register_user, name="register"),
    path("api/login/", views.login_user, name="login"),

    # User endpoints (FBV)
    path("api/fbv/agents/register/", views.fbv_register_agent, name="fbv-register-agent"),
    path("api/fbv/delegate/", views.fbv_delegate, name="fbv-delegate"),

    # Agent endpoints - FBV (decorators)
    path("api/fbv/agent/documents/", views.fbv_agent_documents, name="fbv-agent-documents"),
    path("api/fbv/agent/chain/", views.fbv_agent_chain, name="fbv-agent-chain"),
    path("api/fbv/agent/worker-only/", views.fbv_worker_only, name="fbv-worker-only"),

    # Agent endpoints - CBV (mixins)
    path("api/cbv/agent/documents/", views.CBVAgentDocuments.as_view(), name="cbv-agent-documents"),
    path("api/cbv/agent/chain/", views.CBVAgentChain.as_view(), name="cbv-agent-chain"),

    # DRF endpoints
    path("api/drf/register/", views.DRFRegisterView.as_view(), name="drf-register"),
    path("api/drf/login/", views.DRFLoginView.as_view(), name="drf-login"),
    path("api/drf/delegate/", views.DRFDelegateView.as_view(), name="drf-delegate"),
    path("api/drf/agent/documents/", views.DRFAgentDocuments.as_view(), name="drf-agent-documents"),
    path("api/drf/agent/worker-only/", views.DRFAgentWorkerOnly.as_view(), name="drf-agent-worker-only"),
    path("api/drf/agent/chain/", views.DRFAgentChain.as_view(), name="drf-agent-chain"),
    path("api/drf/agent/constraint/", views.DRFAgentConstraint.as_view(), name="drf-agent-constraint"),
]
