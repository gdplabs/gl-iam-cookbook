"""
The demo agent and task, shared by the issuer and the verifier.

Both services need to agree on which agent they are talking about. In a real
deployment the issuer would look the agent up in its own registry (or in
GL-IAM's ``agents`` table); here it is a constant so the example runs with no
database at all.
"""

from gl_iam import AgentIdentity, AgentStatus, AgentType

ORG_ID = "demo-org"
USER_ID = "user:alice"
AGENT_ID = "agent:report-writer"

#: Every scope this agent is allowed to hold, ever. A delegation may narrow
#: this, never widen it.
ALLOWED_SCOPES = ["reports:read", "email:send"]

#: The audience the verifier is configured for. The token is minted for it and
#: is rejected by a verifier configured for any other audience.
CONNECTOR_AUDIENCE = "gl-connectors"

#: Identifies which key signed a token, so the issuer can rotate keys without
#: every verifier having to cut over at the same instant.
ISSUER_KID = "issuer-2026-08"


def demo_agent() -> AgentIdentity:
    """The agent both services reason about.

    Returns:
        AgentIdentity: A worker agent owned by ``USER_ID``.
    """
    return AgentIdentity(
        id=AGENT_ID,
        name="Quarterly Report Writer",
        agent_type=AgentType.WORKER,
        model="claude-opus-5",
        owner_user_id=USER_ID,
        operator_org_id=ORG_ID,
        status=AgentStatus.ACTIVE,
        max_delegation_depth=3,
        allowed_scopes=ALLOWED_SCOPES,
    )
