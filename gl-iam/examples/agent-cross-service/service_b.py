"""
Cross-Service Delegation: Service B (Receiving Service).

This service validates delegation tokens created by Service A
and provides protected resources. It runs on port 8001.

Service B uses a minimal gateway (for_agent_auth) that only
needs the agent provider and shared secret key.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI

from gl_iam import IAMGateway
from gl_iam.core.types.agent import AgentIdentity
from gl_iam.core.types.delegation import DelegationChain
from gl_iam.fastapi import (
    get_current_agent,
    get_delegation_chain,
    require_agent_scope,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import PostgreSQLAgentProvider, PostgreSQLConfig

load_dotenv()


# ============================================================================
# Application Setup
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Service B uses a minimal setup with PostgreSQLAgentProvider and
    IAMGateway.for_agent_auth(). It only needs the agent table and
    the shared secret key to validate delegation tokens.
    """
    config = PostgreSQLConfig(
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        auto_create_tables=True,
        default_org_id=os.getenv("DEFAULT_ORGANIZATION_ID", "default"),
    )

    # Minimal provider: only agent operations
    agent_provider = PostgreSQLAgentProvider(config)

    # Minimal gateway: only agent auth (no user auth)
    gateway = IAMGateway.for_agent_auth(
        agent_provider=agent_provider,
        secret_key=os.getenv("SECRET_KEY"),
    )
    set_iam_gateway(gateway)

    yield


app = FastAPI(
    title="Service B - Receiving Service",
    description="Validates delegation tokens and provides protected resources",
    lifespan=lifespan,
)


# ============================================================================
# Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy", "service": "service-b", "port": 8001}


@app.get("/documents")
async def get_documents(
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("docs:read")),
):
    """
    Protected endpoint requiring 'docs:read' scope.

    The delegation token from Service A is validated here.
    """
    return {
        "agent": agent.name,
        "agent_type": agent.agent_type.value,
        "documents": [
            {"id": "doc-1", "title": "Cross-Service Report", "service": "B"},
            {"id": "doc-2", "title": "Shared Analytics Data", "service": "B"},
            {"id": "doc-3", "title": "Integration Guide", "service": "B"},
        ],
    }


@app.get("/agent/info")
async def agent_info(agent: AgentIdentity = Depends(get_current_agent)):
    """Get the agent identity from the delegation token."""
    return {
        "id": agent.id,
        "name": agent.name,
        "agent_type": agent.agent_type.value,
        "owner_user_id": agent.owner_user_id,
        "status": agent.status.value,
    }


@app.get("/chain")
async def get_chain(chain: DelegationChain = Depends(get_delegation_chain)):
    """Get the full delegation chain."""
    return {
        "depth": chain.depth,
        "task_id": chain.task_id,
        "root_principal": {
            "id": chain.root_principal.principal_id,
            "type": chain.root_principal.principal_type.value,
        },
        "effective_scopes": list(chain.effective_scopes()),
        "links": [
            {
                "principal_id": link.principal_id,
                "principal_type": link.principal_type.value,
                "scopes": link.scope.scopes,
            }
            for link in chain.links
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
