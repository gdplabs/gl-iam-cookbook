"""
Views for GL-IAM Agent Delegation demo.

Demonstrates three Django patterns for agent-protected endpoints:
1. Function-Based Views (FBV) with decorators
2. Class-Based Views (CBV) with mixins
3. Django REST Framework (DRF) with authentication and permission classes
"""

import os

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from gl_iam import (
    AgentRegistration,
    AgentType,
    DelegationScope,
    TaskContext,
)
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.django import (
    get_iam_gateway,
    gl_iam_login_required,
    require_agent_scope,
    require_agent_type,
    require_delegation_chain,
    run_sync,
)
from gl_iam.django.drf import (
    GLIAMAgentAuthentication,
    GLIAMAuthentication,
    HasAgentScope,
    HasAgentType,
    HasDelegationChain,
    HasResourceConstraint,
    IsGLIAMAuthenticated,
)

from .serializers import (
    AgentRegisterSerializer,
    DelegateSerializer,
    LoginSerializer,
    RegisterSerializer,
)


# ============================================================================
# Public Endpoints
# ============================================================================
def health(request):
    """Public health check endpoint."""
    return JsonResponse({"status": "healthy", "service": "agent-delegation-django"})


@csrf_exempt
def register_user(request):
    """Register a new user."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    import json
    data = json.loads(request.body)
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    user = run_sync(
        gateway.user_store.create_user(
            UserCreateInput(
                email=data["email"],
                display_name=data.get("display_name", data["email"].split("@")[0]),
            ),
            organization_id=org_id,
        )
    )

    run_sync(gateway.user_store.set_user_password(user.id, data["password"], org_id))

    return JsonResponse({"id": user.id, "email": user.email, "display_name": user.display_name})


@csrf_exempt
def login_user(request):
    """Authenticate user and return access token."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    import json
    data = json.loads(request.body)
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    result = run_sync(
        gateway.authenticate(
            credentials=PasswordCredentials(email=data["email"], password=data["password"]),
            organization_id=org_id,
        )
    )

    if result.is_ok:
        return JsonResponse({
            "access_token": result.token.access_token,
            "token_type": result.token.token_type,
        })
    else:
        return JsonResponse({"error": result.error.message}, status=401)


# ============================================================================
# Pattern 1: Function-Based Views (FBV) with Decorators
# ============================================================================
@csrf_exempt
@gl_iam_login_required
def fbv_register_agent(request):
    """Register an agent (FBV pattern)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    import json
    data = json.loads(request.body)
    gateway = get_iam_gateway()
    user = request.gl_iam_user
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    agent_type_map = {
        "orchestrator": AgentType.ORCHESTRATOR,
        "worker": AgentType.WORKER,
        "tool": AgentType.TOOL,
        "autonomous": AgentType.AUTONOMOUS,
    }
    agent_type = agent_type_map.get(data.get("agent_type", "worker").lower(), AgentType.WORKER)

    result = run_sync(
        gateway.register_agent(
            AgentRegistration(
                name=data["name"],
                agent_type=agent_type,
                owner_user_id=user.id,
                operator_org_id=org_id,
                allowed_scopes=data.get("allowed_scopes", []),
            )
        )
    )

    if result.is_ok:
        agent = result.value
        return JsonResponse({
            "id": agent.id,
            "name": agent.name,
            "agent_type": agent.agent_type.value,
            "status": agent.status.value,
        })
    else:
        return JsonResponse({"error": result.error.message}, status=400)


@csrf_exempt
@gl_iam_login_required
def fbv_delegate(request):
    """Create delegation token (FBV pattern)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    import json
    data = json.loads(request.body)
    gateway = get_iam_gateway()
    user = request.gl_iam_user

    result = run_sync(
        gateway.delegate_to_agent(
            principal_token=user.id,
            agent_id=data["agent_id"],
            task=TaskContext(id="django-task", purpose="Django delegation demo"),
            scope=DelegationScope(scopes=data.get("scopes", [])),
        )
    )

    if result.is_ok:
        delegation = result.value
        return JsonResponse({
            "delegation_token": delegation.token,
            "agent_id": delegation.agent_id,
            "scopes": delegation.scope.scopes,
        })
    else:
        return JsonResponse({"error": result.error.message}, status=400)


@require_agent_scope("docs:read")
def fbv_agent_documents(request):
    """Agent endpoint requiring docs:read scope (FBV decorator)."""
    agent = request.gl_iam_agent
    return JsonResponse({
        "pattern": "FBV",
        "agent": agent.name,
        "documents": [
            {"id": "doc-1", "title": "FBV Document"},
        ],
    })


@require_delegation_chain
def fbv_agent_chain(request):
    """Agent endpoint requiring a delegation chain (FBV decorator)."""
    chain = request.gl_iam_delegation_chain
    return JsonResponse({
        "pattern": "FBV",
        "depth": chain.depth,
        "effective_scopes": list(chain.effective_scopes()),
    })


@require_agent_type(AgentType.WORKER)
def fbv_worker_only(request):
    """Agent endpoint restricted to WORKER type (FBV decorator)."""
    agent = request.gl_iam_agent
    return JsonResponse({
        "pattern": "FBV",
        "agent": agent.name,
        "agent_type": agent.agent_type.value,
        "message": "Only WORKER agents can access this",
    })


# ============================================================================
# Pattern 2: Class-Based Views (CBV) with Mixins
# ============================================================================
from gl_iam.django import AgentScopeRequiredMixin, DelegationChainRequiredMixin


@method_decorator(csrf_exempt, name="dispatch")
class CBVAgentDocuments(AgentScopeRequiredMixin, View):
    """Agent endpoint requiring docs:read scope (CBV mixin)."""

    agent_scope = "docs:read"

    def get(self, request):
        """Get documents for the agent."""
        agent = request.gl_iam_agent
        return JsonResponse({
            "pattern": "CBV",
            "agent": agent.name,
            "documents": [
                {"id": "doc-1", "title": "CBV Document"},
            ],
        })


@method_decorator(csrf_exempt, name="dispatch")
class CBVAgentChain(DelegationChainRequiredMixin, View):
    """Agent endpoint requiring a delegation chain (CBV mixin)."""

    def get(self, request):
        """Get delegation chain info."""
        chain = request.gl_iam_delegation_chain
        return JsonResponse({
            "pattern": "CBV",
            "depth": chain.depth,
            "effective_scopes": list(chain.effective_scopes()),
        })


# ============================================================================
# Pattern 3: Django REST Framework (DRF)
# ============================================================================
class DRFRegisterView(APIView):
    """User registration (DRF)."""

    def post(self, request):
        """Register a new user."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        gateway = get_iam_gateway()
        org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

        user = run_sync(
            gateway.user_store.create_user(
                UserCreateInput(
                    email=serializer.validated_data["email"],
                    display_name=serializer.validated_data.get("display_name")
                    or serializer.validated_data["email"].split("@")[0],
                ),
                organization_id=org_id,
            )
        )

        run_sync(
            gateway.user_store.set_user_password(
                user.id, serializer.validated_data["password"], org_id
            )
        )

        return Response(
            {"id": user.id, "email": user.email, "display_name": user.display_name},
            status=status.HTTP_201_CREATED,
        )


class DRFLoginView(APIView):
    """User login (DRF)."""

    def post(self, request):
        """Authenticate and return token."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        gateway = get_iam_gateway()
        org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

        result = run_sync(
            gateway.authenticate(
                credentials=PasswordCredentials(
                    email=serializer.validated_data["email"],
                    password=serializer.validated_data["password"],
                ),
                organization_id=org_id,
            )
        )

        if result.is_ok:
            return Response({
                "access_token": result.token.access_token,
                "token_type": result.token.token_type,
            })
        else:
            return Response({"error": result.error.message}, status=status.HTTP_401_UNAUTHORIZED)


class DRFDelegateView(APIView):
    """Create delegation token (DRF with user auth)."""

    authentication_classes = [GLIAMAuthentication]
    permission_classes = [IsGLIAMAuthenticated]

    def post(self, request):
        """Create a delegation token."""
        serializer = DelegateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        gateway = get_iam_gateway()
        user = request.user

        result = run_sync(
            gateway.delegate_to_agent(
                principal_token=user.id,
                agent_id=serializer.validated_data["agent_id"],
                task=TaskContext(id="drf-task", purpose="DRF delegation demo"),
                scope=DelegationScope(scopes=serializer.validated_data.get("scopes", [])),
            )
        )

        if result.is_ok:
            delegation = result.value
            return Response({
                "delegation_token": delegation.token,
                "agent_id": delegation.agent_id,
                "scopes": delegation.scope.scopes,
            })
        else:
            return Response({"error": result.error.message}, status=status.HTTP_400_BAD_REQUEST)


class DRFAgentDocuments(APIView):
    """Agent endpoint with scope permission (DRF)."""

    authentication_classes = [GLIAMAgentAuthentication]
    permission_classes = [HasAgentScope.with_scope("docs:read")]

    def get(self, request):
        """Get documents for the agent."""
        agent = request.user.agent
        return Response({
            "pattern": "DRF",
            "agent": agent.name,
            "documents": [
                {"id": "doc-1", "title": "DRF Document"},
            ],
        })


class DRFAgentWorkerOnly(APIView):
    """Agent endpoint restricted to WORKER type (DRF)."""

    authentication_classes = [GLIAMAgentAuthentication]
    permission_classes = [HasAgentType.with_type(AgentType.WORKER)]

    def get(self, request):
        """Worker-only endpoint."""
        agent = request.user.agent
        return Response({
            "pattern": "DRF",
            "agent": agent.name,
            "agent_type": agent.agent_type.value,
            "message": "Only WORKER agents can access this",
        })


class DRFAgentChain(APIView):
    """Agent endpoint requiring delegation chain (DRF)."""

    authentication_classes = [GLIAMAgentAuthentication]
    permission_classes = [HasDelegationChain]

    def get(self, request):
        """Get delegation chain info."""
        chain = request.user.chain
        return Response({
            "pattern": "DRF",
            "depth": chain.depth,
            "effective_scopes": list(chain.effective_scopes()),
        })


class DRFAgentConstraint(APIView):
    """Agent endpoint with resource constraint (DRF)."""

    authentication_classes = [GLIAMAgentAuthentication]
    permission_classes = [HasResourceConstraint.with_constraint("tenant_id", "acme")]

    def get(self, request):
        """Constraint-protected endpoint."""
        agent = request.user.agent
        return Response({
            "pattern": "DRF",
            "agent": agent.name,
            "tenant_id": "acme",
            "message": "Resource constraint validated",
        })
