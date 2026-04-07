"""
Mock data for Agent IAM Dashboard demo scenarios.

Contains simulated users, meetings, MoMs, reports, and configuration
that connectors use for resource-level decisions.
"""

# =============================================================================
# Tenants
# =============================================================================
TENANTS = {
    "tenantA": {"name": "GDP Labs", "domain": "tenantA.com"},
    "tenantB": {"name": "External Corp", "domain": "tenantB.com"},
}

# =============================================================================
# Users — with roles, features, active status
# =============================================================================
USERS = {
    # GLChat users (tenantA)
    "alice@tenantA.com": {
        "display_name": "Alice",
        "tenant": "tenantA",
        "role": "admin",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    "bob@tenantA.com": {
        "display_name": "Bob",
        "tenant": "tenantA",
        "role": "member",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    "carol@tenantA.com": {
        "display_name": "Carol",
        "tenant": "tenantA",
        "role": "viewer",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    # DE users
    "organiser@tenantA.com": {
        "display_name": "Organiser (Sandy)",
        "tenant": "tenantA",
        "role": "member",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    "attendee@tenantA.com": {
        "display_name": "Attendee (Petry)",
        "tenant": "tenantA",
        "role": "member",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    "dept-head@tenantA.com": {
        "display_name": "Dept Head (CEO)",
        "tenant": "tenantA",
        "role": "admin",
        "active": True,
        "features": [],
        "is_super_user": True,
    },
    "glc-pm@tenantA.com": {
        "display_name": "GLC PM",
        "tenant": "tenantA",
        "role": "member",
        "active": True,
        "features": ["invoice:send"],
        "is_super_user": False,
    },
    "other-pm@tenantA.com": {
        "display_name": "Other Team PM",
        "tenant": "tenantA",
        "role": "member",
        "active": True,
        "features": [],  # NO invoice:send
        "is_super_user": False,
    },
    # Deactivated user (for UC-GLCHAT-03.2)
    "deactivated@tenantA.com": {
        "display_name": "Deactivated User",
        "tenant": "tenantA",
        "role": "member",
        "active": False,
        "features": [],
        "is_super_user": False,
    },
    # Cross-tenant user (tenantB)
    "bob@tenantB.com": {
        "display_name": "Bob (External)",
        "tenant": "tenantB",
        "role": "member",
        "active": True,
        "features": [],
        "is_super_user": False,
    },
    "charlie@tenantB.com": {
        "display_name": "Charlie (External Attendee)",
        "tenant": "tenantB",
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
    "organiser@tenantA.com": {"active": True},
    "attendee@tenantA.com": {"active": True},
    "alice@tenantA.com": {"active": True},
    # NOTE: "no-meemo@tenantA.com" intentionally NOT here (UC-DE-01.2)
}

# =============================================================================
# Calendars — user-owned resources
# =============================================================================
CALENDARS = {
    "alice@tenantA.com": [
        {"id": "evt-1", "title": "Sprint Planning", "time": "2026-04-07T09:00:00Z"},
        {"id": "evt-2", "title": "Design Review", "time": "2026-04-07T14:00:00Z"},
        {"id": "evt-3", "title": "1:1 with Manager", "time": "2026-04-08T10:00:00Z"},
    ],
    "pakon@tenantA.com": [
        {"id": "evt-4", "title": "Board Meeting", "time": "2026-04-07T10:00:00Z"},
        {"id": "evt-5", "title": "Strategy Review", "time": "2026-04-07T15:00:00Z"},
    ],
    "organiser@tenantA.com": [
        {"id": "evt-6", "title": "GL IAM Standup", "time": "2026-04-07T09:30:00Z"},
    ],
}

# =============================================================================
# Meetings — with attendee lists
# =============================================================================
MEETINGS = {
    "meet-001": {
        "title": "GL IAM Standup",
        "organiser": "organiser@tenantA.com",
        "attendees": [
            "organiser@tenantA.com",
            "attendee@tenantA.com",
            "alice@tenantA.com",
            "charlie@tenantB.com",  # external attendee
        ],
        "tenant": "tenantA",
    },
    "meet-002": {
        "title": "GL IAM Standup (no Meemo)",
        "organiser": "no-meemo@tenantA.com",
        "attendees": ["no-meemo@tenantA.com", "attendee@tenantA.com"],
        "tenant": "tenantA",
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
        "organiser": "organiser@tenantA.com",
        "attendees": ["organiser@tenantA.com", "attendee@tenantA.com", "alice@tenantA.com"],
        "tenant": "tenantA",
    },
    "mom-002": {
        "meeting_id": "meet-001",
        "title": "GL IAM Standup (Draft)",
        "status": "draft",
        "content": "DRAFT: Not yet reviewed.",
        "sensitive_fields": [],
        "organiser": "organiser@tenantA.com",
        "attendees": ["organiser@tenantA.com", "attendee@tenantA.com"],
        "tenant": "tenantA",
    },
    "mom-003": {
        "meeting_id": "meet-003",
        "title": "Weekly Sync",
        "status": "shared",
        "content": "Sprint velocity review and next sprint planning.",
        "sensitive_fields": [],
        "organiser": "organiser@tenantA.com",
        "attendees": ["organiser@tenantA.com", "attendee@tenantA.com"],
        "tenant": "tenantA",
    },
    "mom-004": {
        "meeting_id": "meet-004",
        "title": "Weekly Sync",
        "status": "shared",
        "content": "Product roadmap alignment.",
        "sensitive_fields": [],
        "organiser": "organiser@tenantA.com",
        "attendees": ["organiser@tenantA.com"],
        "tenant": "tenantA",
    },
}

# =============================================================================
# Weekly Reports (AIP use case)
# =============================================================================
WEEKLY_REPORTS = {
    "alice@tenantA.com": {
        "filled": True,
        "content": "Completed delegation token MVP. Started integration tests.",
        "email_active": True,
    },
    "bob@tenantA.com": {
        "filled": False,
        "content": None,
        "email_active": True,
    },
    "resigned@tenantA.com": {
        "filled": True,
        "content": "Final report before resignation.",
        "email_active": False,  # Email bounces
    },
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
