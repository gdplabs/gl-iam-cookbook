"""
Mock data for Agent IAM Dashboard demo scenarios.

Contains simulated users, meetings, MoMs, reports, and configuration
that connectors use for resource-level decisions.
"""

# =============================================================================
# Tenants
# =============================================================================
TENANTS = {
    "GLC": {"name": "GDP Labs", "domain": "gdplabs.id"},
    "GLAIR": {"name": "GLAIR", "domain": "gdplabs.id"},
}

# =============================================================================
# Users — with roles, features, active status
# =============================================================================
USERS = {
    # GLChat users (GLC)
    "onlee@gdplabs.id": {
        "display_name": "Pak On",
        "tenant": "GLC",
        "role": "admin",
        "active": True,
        "features": ["invoice_send"],
        "is_super_user": False,
    },
    "guest@gdplabs.id": {
        "display_name": "Guest",
        "tenant": "NONE",
        "role": "viewer",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    # DE users
    "sandy@gdplabs.id": {
        "display_name": "Sandy",
        "tenant": "GLC",
        "role": "member",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    "maylina@gdplabs.id": {
        "display_name": "Maylina",
        "tenant": "GLC",
        "role": "member",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    "dept-head@gdplabs.id": {
        "display_name": "Dept Head (CEO)",
        "tenant": "GLC",
        "role": "admin",
        "active": True,
        "features": [],
        "is_super_user": True,
    },
    "glc-pm@gdplabs.id": {
        "display_name": "GLC PM",
        "tenant": "GLC",
        "role": "member",
        "active": True,
        "features": ["invoice_send"],
        "is_super_user": False,
    },
    "other-pm@gdplabs.id": {
        "display_name": "Other Team PM",
        "tenant": "GLC",
        "role": "member",
        "active": True,
        "features": [],  # NO invoice_send
        "is_super_user": False,
    },
    # Deactivated user (for UC-GLCHAT-03.2)
    "deactivated@gdplabs.id": {
        "display_name": "Deactivated User",
        "tenant": "GLC",
        "role": "member",
        "active": False,
        "features": [],
        "is_super_user": False,
    },
    # Cross-org user (GLAIR)
    "petry@gdplabs.id": {
        "display_name": "Petry (GLAIR)",
        "tenant": "GLAIR",
        "role": "member",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
}

# =============================================================================
# Meemo Accounts — some missing for partial success scenarios
# =============================================================================
MEEMO_ACCOUNTS = {
    "sandy@gdplabs.id": {"active": True},
    "maylina@gdplabs.id": {"active": True},
    "onlee@gdplabs.id": {"active": True},
    # NOTE: "no-meemo@gdplabs.id" intentionally NOT here (UC-DE-01.2)
}

# =============================================================================
# Calendars — user-owned resources
# =============================================================================
CALENDARS = {
    "onlee@gdplabs.id": [
        {"id": "evt-1", "title": "Board Meeting", "time": "2026-04-07T10:00:00Z"},
        {"id": "evt-2", "title": "Strategy Review", "time": "2026-04-07T15:00:00Z"},
        {"id": "evt-3", "title": "1:1 with CTO", "time": "2026-04-08T10:00:00Z"},
    ],
    "sandy@gdplabs.id": [
        {"id": "evt-6", "title": "GL IAM Standup", "time": "2026-04-07T09:30:00Z"},
        {"id": "evt-7", "title": "SDK Planning", "time": "2026-04-07T11:00:00Z"},
    ],
    "petry@gdplabs.id": [
        {"id": "evt-8", "title": "External Partner Sync", "time": "2026-04-07T13:00:00Z"},
        {"id": "evt-9", "title": "Cross-Org Review", "time": "2026-04-07T16:00:00Z"},
    ],
}

# =============================================================================
# Meetings — with attendee lists
# =============================================================================
MEETINGS = {
    "meet-001": {
        "title": "GL IAM Standup",
        "organiser": "sandy@gdplabs.id",
        "attendees": [
            "sandy@gdplabs.id",
            "maylina@gdplabs.id",
            "onlee@gdplabs.id",
            "petry@gdplabs.id",  # external attendee
        ],
        "tenant": "GLC",
    },
    "meet-002": {
        "title": "GL IAM Standup (no Meemo)",
        "organiser": "no-meemo@gdplabs.id",
        "attendees": ["no-meemo@gdplabs.id", "maylina@gdplabs.id"],
        "tenant": "GLC",
    },
}

# =============================================================================
# MoM Documents
# =============================================================================
MOMS = {
    "mom-001": {
        "meeting_id": "meet-001",
        "title": "GL IAM Standup",
        "status": "shared",
        "content": "Discussed delegation token design, scope attenuation, and audit trail implementation.",
        "sensitive_fields": ["attendee_emails"],
        "organiser": "sandy@gdplabs.id",
        "attendees": ["sandy@gdplabs.id", "maylina@gdplabs.id", "onlee@gdplabs.id"],
        "tenant": "GLC",
    },
    "mom-002": {
        "meeting_id": "meet-001",
        "title": "GL IAM Standup (Draft)",
        "status": "draft",
        "content": "DRAFT: Not yet reviewed.",
        "sensitive_fields": [],
        "organiser": "sandy@gdplabs.id",
        "attendees": ["sandy@gdplabs.id", "maylina@gdplabs.id"],
        "tenant": "GLC",
    },
    "mom-003": {
        "meeting_id": "meet-003",
        "title": "Weekly Sync",
        "status": "shared",
        "content": "Sprint velocity review and next sprint planning.",
        "sensitive_fields": [],
        "organiser": "sandy@gdplabs.id",
        "attendees": ["sandy@gdplabs.id", "maylina@gdplabs.id"],
        "tenant": "GLC",
    },
    "mom-004": {
        "meeting_id": "meet-004",
        "title": "Weekly Sync",
        "status": "shared",
        "content": "Product roadmap alignment.",
        "sensitive_fields": [],
        "organiser": "sandy@gdplabs.id",
        "attendees": ["sandy@gdplabs.id"],
        "tenant": "GLC",
    },
}

# =============================================================================
# Weekly Reports (AIP use case)
# =============================================================================
WEEKLY_REPORTS = {
    "onlee@gdplabs.id": {
        "filled": True,
        "content": "Completed delegation token MVP. Started integration tests.",
        "email_active": True,
    },
    "bob@gdplabs.id": {
        "filled": False,
        "content": None,
        "email_active": True,
    },
    "resigned@gdplabs.id": {
        "filled": True,
        "content": "Final report before resignation.",
        "email_active": False,  # Email bounces
    },
}

# =============================================================================
# Directory — name to email resolution
# =============================================================================
DIRECTORY = {
    "pak on": {"email": "onlee@gdplabs.id", "display_name": "Pak On", "org": "GLC", "role": "CEO"},
    "on": {"email": "onlee@gdplabs.id", "display_name": "Pak On", "org": "GLC", "role": "CEO"},
    "onlee": {"email": "onlee@gdplabs.id", "display_name": "Pak On", "org": "GLC", "role": "CEO"},
    "sandy": {"email": "sandy@gdplabs.id", "display_name": "Sandy", "org": "GLC", "role": "Engineer"},
    "maylina": {"email": "maylina@gdplabs.id", "display_name": "Maylina", "org": "GLC", "role": "PM"},
    "petry": {"email": "petry@gdplabs.id", "display_name": "Petry", "org": "GLAIR", "role": "Partner"},
}

# =============================================================================
# Invoices (DE feature-level access)
# =============================================================================
INVOICES = {
    "inv-aws-2026-04": {
        "vendor": "AWS",
        "period": "April 2026",
        "amount": "$12,450.00",
        "status": "pending",
    },
}
