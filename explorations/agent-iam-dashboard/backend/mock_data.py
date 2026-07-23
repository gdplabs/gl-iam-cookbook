"""
Mock data for Agent IAM Dashboard demo scenarios.

Contains simulated users, meetings, MoMs, reports, and configuration
that connectors use for resource-level decisions.
"""

# =============================================================================
# Tenants
# =============================================================================
TENANTS = {
    "Acme": {"name": "Acme Corp", "domain": "example.com"},
    "Globex": {"name": "Globex", "domain": "example.com"},
}

# =============================================================================
# Users — with roles, features, active status
# =============================================================================
USERS = {
    # GLChat users (Acme)
    "nadia@example.com": {
        "display_name": "Nadia",
        "tenant": "Acme",
        "role": "admin",
        "active": True,
        "features": ["invoice_send"],
        "is_super_user": False,
    },
    "guest@example.com": {
        "display_name": "Guest",
        "tenant": "NONE",
        "role": "viewer",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    # DE users
    "sam@example.com": {
        "display_name": "Sam",
        "tenant": "Acme",
        "role": "member",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    "maya@example.com": {
        "display_name": "Maya",
        "tenant": "Acme",
        "role": "member",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    "dept-head@example.com": {
        "display_name": "Dept Head (CEO)",
        "tenant": "Acme",
        "role": "admin",
        "active": True,
        "features": [],
        "is_super_user": True,
    },
    "acme-pm@example.com": {
        "display_name": "Acme PM",
        "tenant": "Acme",
        "role": "member",
        "active": True,
        "features": ["invoice_send"],
        "is_super_user": False,
    },
    "other-pm@example.com": {
        "display_name": "Other Team PM",
        "tenant": "Acme",
        "role": "member",
        "active": True,
        "features": [],  # NO invoice_send
        "is_super_user": False,
    },
    # Deactivated user (for UC-GLCHAT-03.2)
    "deactivated@example.com": {
        "display_name": "Deactivated User",
        "tenant": "Acme",
        "role": "member",
        "active": False,
        "features": [],
        "is_super_user": False,
    },
    # Cross-org user (Globex)
    "priya@example.com": {
        "display_name": "Priya (Globex)",
        "tenant": "Globex",
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
    "sam@example.com": {"active": True},
    "maya@example.com": {"active": True},
    "nadia@example.com": {"active": True},
    # NOTE: "no-meemo@example.com" intentionally NOT here (UC-DE-01.2)
}

# =============================================================================
# Calendars — user-owned resources
# =============================================================================
CALENDARS = {
    "nadia@example.com": [
        {"id": "evt-1", "title": "Board Meeting", "time": "2026-04-07T10:00:00Z"},
        {"id": "evt-2", "title": "Strategy Review", "time": "2026-04-07T15:00:00Z"},
        {"id": "evt-3", "title": "1:1 with CTO", "time": "2026-04-08T10:00:00Z"},
    ],
    "sam@example.com": [
        {"id": "evt-6", "title": "GL IAM Standup", "time": "2026-04-07T09:30:00Z"},
        {"id": "evt-7", "title": "SDK Planning", "time": "2026-04-07T11:00:00Z"},
    ],
    "priya@example.com": [
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
        "organiser": "sam@example.com",
        "attendees": [
            "sam@example.com",
            "maya@example.com",
            "nadia@example.com",
            "priya@example.com",  # external attendee
        ],
        "tenant": "Acme",
    },
    "meet-002": {
        "title": "GL IAM Standup (no Meemo)",
        "organiser": "no-meemo@example.com",
        "attendees": ["no-meemo@example.com", "maya@example.com"],
        "tenant": "Acme",
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
        "organiser": "sam@example.com",
        "attendees": ["sam@example.com", "maya@example.com", "nadia@example.com"],
        "tenant": "Acme",
    },
    "mom-002": {
        "meeting_id": "meet-001",
        "title": "GL IAM Standup (Draft)",
        "status": "draft",
        "content": "DRAFT: Not yet reviewed.",
        "sensitive_fields": [],
        "organiser": "sam@example.com",
        "attendees": ["sam@example.com", "maya@example.com"],
        "tenant": "Acme",
    },
    "mom-003": {
        "meeting_id": "meet-003",
        "title": "Weekly Sync",
        "status": "shared",
        "content": "Sprint velocity review and next sprint planning.",
        "sensitive_fields": [],
        "organiser": "sam@example.com",
        "attendees": ["sam@example.com", "maya@example.com"],
        "tenant": "Acme",
    },
    "mom-004": {
        "meeting_id": "meet-004",
        "title": "Weekly Sync",
        "status": "shared",
        "content": "Product roadmap alignment.",
        "sensitive_fields": [],
        "organiser": "sam@example.com",
        "attendees": ["sam@example.com"],
        "tenant": "Acme",
    },
}

# =============================================================================
# Weekly Reports (AIP use case)
# =============================================================================
WEEKLY_REPORTS = {
    "nadia@example.com": {
        "filled": True,
        "content": "Completed delegation token MVP. Started integration tests.",
        "email_active": True,
    },
    "bob@example.com": {
        "filled": False,
        "content": None,
        "email_active": True,
    },
    "resigned@example.com": {
        "filled": True,
        "content": "Final report before resignation.",
        "email_active": False,  # Email bounces
    },
}

# =============================================================================
# Directory — name to email resolution
# =============================================================================
DIRECTORY = {
    "nadia": {"email": "nadia@example.com", "display_name": "Nadia", "org": "Acme", "role": "CEO"},
    "sam": {"email": "sam@example.com", "display_name": "Sam", "org": "Acme", "role": "Engineer"},
    "maya": {"email": "maya@example.com", "display_name": "Maya", "org": "Acme", "role": "PM"},
    "priya": {"email": "priya@example.com", "display_name": "Priya", "org": "Globex", "role": "Partner"},
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
