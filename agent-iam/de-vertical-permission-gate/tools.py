"""The DE vertical's tools -- the file a DE team would actually copy.

These are deliberately shaped like the real tools in
``digital-employee/common/applications/digital-employee-pm/digital_employee_pm/connectors/custom_tools/``:
a pydantic input schema, a ``BaseTool`` subclass with ``name`` /
``description`` / ``args_schema``, and an ``_arun`` that calls a backend.

The only difference from the production tools is the single decorator line
above each class. That line is the whole proposal:

    @requires_scope("google_docs:write")

The backends are stubbed so the example runs offline. In a real DE these
bodies stay exactly as they are today -- GL Connectors calls, MCP calls,
whatever. The gate does not care what the tool does; it only decides whether
the tool is allowed to do it.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from scope_gate import requires_scope

SYNC_NOT_SUPPORTED = "This example drives tools asynchronously; use ainvoke()."


# ---------------------------------------------------------------------------
# 1. Read a meeting summary  ->  requires meemo:read
# ---------------------------------------------------------------------------
class MeemoGetMeetingSummaryInput(BaseModel):
    """Input schema for fetching a meeting summary."""

    meeting_id: str = Field(..., description="Meemo meeting identifier.")


@requires_scope("meemo:read")
class MeemoGetMeetingSummaryTool(BaseTool):
    """Fetch a meeting summary from Meemo."""

    name: str = "meemo_get_meeting_summary_tool"
    description: str = "Retrieve the transcript summary for a recorded meeting."
    args_schema: type[BaseModel] = MeemoGetMeetingSummaryInput

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Not used -- see module docstring."""
        raise NotImplementedError(SYNC_NOT_SUPPORTED)

    async def _arun(self, meeting_id: str, **_kwargs: Any) -> dict[str, Any]:
        """Return the meeting summary (stubbed backend)."""
        return {
            "status": "ok",
            "meeting_id": meeting_id,
            "title": "GL IAM Weekly Sync",
            "attendees": ["Pak On", "Afif", "Ridwan", "Maylina", "Sandy"],
            "summary": (
                "Discussed agent scope enforcement. Action item: demonstrate "
                "delegation + scope attenuation from the DE vertical layer."
            ),
        }


# ---------------------------------------------------------------------------
# 2. Create a Google Doc  ->  requires google_docs:write
# ---------------------------------------------------------------------------
class GoogleDocsCreateDocumentInput(BaseModel):
    """Input schema for creating a Google Doc."""

    title: str = Field(..., description="Title for the Google Doc.")
    body: str = Field(default="", description="Markdown body to write into the doc.")


@requires_scope("google_docs:write")
class GoogleDocsCreateDocumentTool(BaseTool):
    """Create a Google Docs document via GL Connectors."""

    name: str = "google_docs_create_document_tool"
    description: str = "Create a Google Docs document and write the minutes into it."
    args_schema: type[BaseModel] = GoogleDocsCreateDocumentInput

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Not used -- see module docstring."""
        raise NotImplementedError(SYNC_NOT_SUPPORTED)

    async def _arun(self, title: str, body: str = "", **_kwargs: Any) -> dict[str, Any]:
        """Create the document (stubbed backend)."""
        return {
            "status": "ok",
            "document_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
            "title": title,
            "url": "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit",
            "characters_written": len(body),
        }


# ---------------------------------------------------------------------------
# 3. Email the minutes  ->  requires gmail:send
# ---------------------------------------------------------------------------
class SendEmailInput(BaseModel):
    """Input schema for sending the minutes by email."""

    recipients: list[str] = Field(..., description="Recipient email addresses.")
    subject: str = Field(..., description="Email subject line.")
    body: str = Field(default="", description="Email body.")


@requires_scope("gmail:send")
class SendEmailTool(BaseTool):
    """Send an email via GL Connectors."""

    name: str = "send_email_tool"
    description: str = "Email the meeting minutes to the attendees."
    args_schema: type[BaseModel] = SendEmailInput

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Not used -- see module docstring."""
        raise NotImplementedError(SYNC_NOT_SUPPORTED)

    async def _arun(
        self,
        recipients: list[str],
        subject: str,
        body: str = "",
        **_kwargs: Any,
    ) -> dict[str, Any]:
        """Send the email (stubbed backend)."""
        return {
            "status": "ok",
            "message_id": "18f2c9a41b7d3e5f",
            "recipients": recipients,
            "subject": subject,
        }


meemo_get_meeting_summary_tool = MeemoGetMeetingSummaryTool()
google_docs_create_document_tool = GoogleDocsCreateDocumentTool()
send_email_tool = SendEmailTool()

# The DE's full toolbelt. Its scopes become the agent's allowed_scopes
# ceiling -- exactly how AIP already derives allowed_scopes from an agent's
# attached tool names in delegation_token_auth.py.
DE_TOOLS: list[BaseTool] = [
    meemo_get_meeting_summary_tool,
    google_docs_create_document_tool,
    send_email_tool,
]


__all__ = [
    "DE_TOOLS",
    "google_docs_create_document_tool",
    "meemo_get_meeting_summary_tool",
    "send_email_tool",
]
