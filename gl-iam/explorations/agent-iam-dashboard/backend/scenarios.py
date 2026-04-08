"""
BRD Scenario Registry — all 17+ sub-scenarios as data objects.

Each scenario configures the entire delegation flow:
- Who the user is (email, role, tenant, features)
- Which agent to invoke
- What message to send
- Resource context for tool-level decisions
- Expected outcome and BRD reference codes
"""

SCENARIOS: dict[str, dict] = {
    # =========================================================================
    # GLChat Use Cases
    # =========================================================================
    "UC-GLCHAT-01.1": {
        "product": "glchat",
        "title": "Check own calendar schedule",
        "description": "Alice checks her own meetings today. Read-only, user delegation.",
        "user_email": "onlee@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Give me a list of my meetings today",
        "tool_inputs": {},
        "resource_context": {
            "target_calendar": "onlee@gdplabs.id",
            "access_type": "user",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-02", "BR-AP-01", "BR-RB-01"],
        "concepts": ["Delegated Access", "Auto-Approval (Read-Only)"],
    },
    # --- Member variant: Petry checks own calendar (same action, different role) ---
    "UC-GLCHAT-01.1-M": {
        "product": "glchat",
        "title": "Check own calendar (Member)",
        "description": "Petry (member) checks her own meetings. Same as 01.1 but member role — uses User OAuth only.",
        "user_email": "maylina@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Give me a list of my meetings today",
        "tool_inputs": {},
        "resource_context": {
            "target_calendar": "maylina@gdplabs.id",
            "access_type": "user",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-02", "BR-AP-01", "BR-RB-01"],
        "concepts": ["Delegated Access", "User OAuth Only (Member)"],
    },
    "UC-GLCHAT-01.2": {
        "product": "glchat",
        "title": "Check Pak On (CEO) calendar (Admin)",
        "description": "Pak On (admin) checks CEO's meetings. Agent OAuth with wildcard access.",
        "user_email": "onlee@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Give me a list of Pak On's meetings today",
        "tool_inputs": {"directory_lookup": {"name": "Pak On"}},
        "resource_context": {
            "target_calendar": "onlee@gdplabs.id",
            "access_type": "agent",
            "target_whitelist": "*",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-04", "BR-AP-01", "BR-RB-06"],
        "concepts": ["Delegated Access", "Agent OAuth", "Directory Lookup"],
    },
    "UC-GLCHAT-01.2-M": {
        "product": "glchat",
        "title": "Check Pak On (CEO) calendar (Member)",
        "description": "Maylina (member) checks CEO's meetings. directory_lookup resolves name, then Agent OAuth reads calendar — Pak On is whitelisted.",
        "user_email": "maylina@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Give me a list of Pak On's meetings today",
        "tool_inputs": {"directory_lookup": {"name": "Pak On"}},
        "resource_context": {
            "target_calendar": "onlee@gdplabs.id",
            "access_type": "agent",
            "target_whitelist": ["onlee@gdplabs.id", "org:GLC"],
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-04", "BR-RB-06"],
        "concepts": ["Delegated Access", "Agent OAuth", "Directory Lookup", "Whitelisted Resource"],
    },
    # --- UC-GLCHAT-01.3: Check internal colleague's calendar ---
    "UC-GLCHAT-01.3": {
        "product": "glchat",
        "title": "Check internal colleague's calendar (Admin)",
        "description": "Pak On (admin) checks Sandy's calendar. directory_lookup resolves name, Agent OAuth with wildcard access.",
        "user_email": "onlee@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Give me a list of Sandy's meetings today",
        "tool_inputs": {"directory_lookup": {"name": "Sandy"}},
        "resource_context": {
            "target_calendar": "sandy@gdplabs.id",
            "access_type": "agent",
            "target_whitelist": "*",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-04", "BR-RB-06"],
        "concepts": ["Delegated Access", "Agent OAuth", "Directory Lookup", "Internal Org"],
    },
    "UC-GLCHAT-01.3-M": {
        "product": "glchat",
        "title": "Check internal colleague's calendar (Member)",
        "description": "Maylina (member) checks Sandy's calendar. directory_lookup resolves name, Agent OAuth allowed — same org.",
        "user_email": "maylina@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Give me a list of Sandy's meetings today",
        "tool_inputs": {"directory_lookup": {"name": "Sandy"}},
        "resource_context": {
            "target_calendar": "sandy@gdplabs.id",
            "access_type": "agent",
            "target_whitelist": ["onlee@gdplabs.id", "org:GLC"],
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-04", "BR-RB-06"],
        "concepts": ["Delegated Access", "Agent OAuth", "Directory Lookup", "Internal Org"],
    },
    # --- UC-GLCHAT-01.4: Check external org colleague's calendar ---
    "UC-GLCHAT-01.4": {
        "product": "glchat",
        "title": "Check external org colleague's calendar (Admin)",
        "description": "Pak On (admin) checks Petry's calendar. directory_lookup resolves → petry@gdplabs.id. Agent OAuth wildcard allows it.",
        "user_email": "onlee@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Give me a list of Petry's meetings today",
        "tool_inputs": {"directory_lookup": {"name": "Petry"}},
        "resource_context": {
            "target_calendar": "petry@gdplabs.id",
            "access_type": "agent",
            "target_whitelist": "*",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-04", "BR-RB-06", "BR-RB-07"],
        "concepts": ["Delegated Access", "Agent OAuth", "Directory Lookup", "Cross-Org Access"],
    },
    "UC-GLCHAT-01.4-M": {
        "product": "glchat",
        "title": "Check external org colleague's calendar (Member, rejected)",
        "description": "Maylina (member) tries Petry's calendar. directory_lookup resolves → petry@gdplabs.id. Not in member's whitelist → rejected.",
        "user_email": "maylina@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Give me a list of Petry's meetings today",
        "tool_inputs": {"directory_lookup": {"name": "Petry"}},
        "resource_context": {
            "target_calendar": "petry@gdplabs.id",
            "access_type": "agent",
            "target_whitelist": ["onlee@gdplabs.id", "org:GLC"],
        },
        "expected_outcome": "rejected",
        "brd_refs": ["BR-RB-06", "BR-RB-07"],
        "concepts": ["Resource Constraint", "Directory Lookup", "Org Boundary Enforcement"],
    },
    "UC-GLCHAT-02.1": {
        "product": "glchat",
        "title": "Schedule meeting on own calendar (Admin)",
        "description": "Alice (admin) schedules a meeting on her own calendar.",
        "user_email": "onlee@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Schedule a 1-hour sync with Sandy and Petry this Friday at 3pm",
        "tool_inputs": {
            "google_calendar_events_insert": {
                "title": "Sync with Sandy and Petry",
                "time": "2026-04-11T15:00:00Z",
            },
        },
        "resource_context": {
            "target_calendar": "onlee@gdplabs.id",
            "access_type": "user",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-02", "BR-AP-02", "BR-RB-01"],
        "concepts": ["Delegated Access", "Approval Boundary (Write)"],
    },
    # --- Member variant: Petry schedules on own calendar ---
    "UC-GLCHAT-02.1-M": {
        "product": "glchat",
        "title": "Schedule meeting on own calendar (Member)",
        "description": "Petry (member) schedules a meeting. Same action as admin but credential is strictly User OAuth — no Agent fallback.",
        "user_email": "maylina@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Schedule a 1-hour sync with Sandy this Friday at 3pm",
        "tool_inputs": {
            "google_calendar_events_insert": {
                "title": "Sync with Sandy",
                "time": "2026-04-11T15:00:00Z",
            },
        },
        "resource_context": {
            "target_calendar": "maylina@gdplabs.id",
            "access_type": "user",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-02", "BR-AP-02", "BR-RB-01"],
        "concepts": ["Delegated Access", "User OAuth Only (Member)"],
    },
    "UC-GLCHAT-02.2": {
        "product": "glchat",
        "title": "Write to colleague's calendar (Admin, success)",
        "description": "Pak On (admin) writes to Sandy's calendar. directory_lookup resolves name. Admin wildcard write access → success via Agent OAuth.",
        "user_email": "onlee@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Add a dentist appointment to Sandy's calendar tomorrow at 10am",
        "tool_inputs": {
            "directory_lookup": {"name": "Sandy"},
            "google_calendar_events_insert": {
                "title": "Dentist Appointment",
                "time": "2026-04-08T10:00:00Z",
                "target_calendar": "sandy@gdplabs.id",
            },
        },
        "resource_context": {
            "target_calendar": "sandy@gdplabs.id",
            "access_type": "agent",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-RB-02", "BR-DA-04"],
        "concepts": ["Agent OAuth", "Directory Lookup", "Admin Write to Others"],
    },
    # --- Member variant ---
    "UC-GLCHAT-02.2-M": {
        "product": "glchat",
        "title": "Write to colleague's calendar (Member, rejected)",
        "description": "Maylina (member) tries to write to Sandy's calendar. directory_lookup resolves name. Sandy not in member's write whitelist → rejected.",
        "user_email": "maylina@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Add a dentist appointment to Sandy's calendar tomorrow at 10am",
        "tool_inputs": {
            "directory_lookup": {"name": "Sandy"},
            "google_calendar_events_insert": {
                "title": "Dentist Appointment",
                "time": "2026-04-08T10:00:00Z",
                "target_calendar": "sandy@gdplabs.id",
            },
        },
        "resource_context": {
            "target_calendar": "sandy@gdplabs.id",
            "access_type": "agent",
        },
        "expected_outcome": "rejected",
        "brd_refs": ["BR-RB-02", "BR-RB-06"],
        "concepts": ["Resource Constraint", "Directory Lookup", "Write Whitelist Enforcement"],
    },
    "UC-GLCHAT-03.1": {
        "product": "glchat",
        "title": "Scheduled task - active account",
        "description": "Pre-authorized daily task fires. Alice's account is active.",
        "user_email": "onlee@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Send daily meeting list (scheduled task)",
        "tool_inputs": {},
        "resource_context": {
            "target_calendar": "onlee@gdplabs.id",
            "access_type": "user",
            "scheduled_task": True,
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-ID-03", "BR-AP-01"],
        "concepts": ["Pre-authorised Revalidation", "Delegated Access"],
    },
    "UC-GLCHAT-03.2": {
        "product": "glchat",
        "title": "Scheduled task - deactivated account",
        "description": "Pre-authorized task fires but Alice's account was deactivated.",
        "user_email": "deactivated@gdplabs.id",
        "agent": "scheduling-agent",
        "message": "Send daily meeting list (scheduled task)",
        "tool_inputs": {},
        "resource_context": {
            "target_calendar": "deactivated@gdplabs.id",
            "access_type": "user",
            "scheduled_task": True,
        },
        "expected_outcome": "rejected",
        "brd_refs": ["BR-ID-02", "BR-ID-03"],
        "concepts": ["Account Validity", "Pre-authorised Revalidation"],
    },

    # =========================================================================
    # Digital Employee Use Cases
    # =========================================================================
    "UC-DE-01.1": {
        "product": "de",
        "title": "Create MoM - Meemo account active",
        "description": "DE PM creates MoM. Organiser's Meemo account exists.",
        "user_email": "sandy@gdplabs.id",
        "agent": "de-pm-agent",
        "message": "Create minutes of meeting for GL IAM standup",
        "tool_inputs": {
            "meemo_create_meeting_notes": {"meeting_id": "meet-001"},
            "google_docs_create_document": {"title": "GL IAM Standup MoM"},
        },
        "resource_context": {
            "meeting_id": "meet-001",
            "organiser_email": "sandy@gdplabs.id",
            "access_type": "agent",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-03", "BR-DA-04", "BR-RB-03", "BR-OH-01"],
        "concepts": ["Implicit Consent", "Agent's Own Access"],
    },
    "UC-DE-01.2": {
        "product": "de",
        "title": "Create MoM - no Meemo account",
        "description": "DE PM creates MoM but organiser has no Meemo account. Partial success.",
        "user_email": "sandy@gdplabs.id",
        "agent": "de-pm-agent",
        "message": "Create minutes of meeting for GL IAM standup",
        "tool_inputs": {
            "meemo_create_meeting_notes": {"meeting_id": "meet-002"},
            "google_docs_create_document": {"title": "GL IAM Standup MoM"},
        },
        "resource_context": {
            "meeting_id": "meet-002",
            "organiser_email": "no-meemo@gdplabs.id",
            "access_type": "agent",
        },
        "expected_outcome": "partial_success",
        "brd_refs": ["BR-RB-03", "BR-OH-02"],
        "concepts": ["Target Existence Validation", "Partial Success"],
    },
    "UC-DE-02.1": {
        "product": "de",
        "title": "Share MoM - organiser requests",
        "description": "Meeting organiser asks DE PM to share MoM with all attendees.",
        "user_email": "sandy@gdplabs.id",
        "agent": "de-pm-agent",
        "message": "Share the GL IAM standup MoM with all attendees",
        "tool_inputs": {
            "google_drive_share_file": {"mom_id": "mom-001"},
            "google_mail_send_email": {"subject": "MoM: GL IAM Standup"},
        },
        "resource_context": {
            "mom_id": "mom-001",
            "requester_email": "sandy@gdplabs.id",
            "access_type": "user",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-02", "BR-AP-03", "BR-RB-01"],
        "concepts": ["Delegated Access", "Approval Boundary (Externally Visible)"],
    },
    "UC-DE-02.2": {
        "product": "de",
        "title": "Share MoM - attendee requests (rejected)",
        "description": "An attendee (not organiser) tries to share MoM. Rejected.",
        "user_email": "maylina@gdplabs.id",
        "agent": "de-pm-agent",
        "message": "Share the GL IAM standup MoM with all attendees",
        "tool_inputs": {
            "google_drive_share_file": {"mom_id": "mom-001"},
        },
        "resource_context": {
            "mom_id": "mom-001",
            "requester_email": "maylina@gdplabs.id",
            "access_type": "user",
        },
        "expected_outcome": "rejected",
        "brd_refs": ["BR-RB-01", "BR-RB-02"],
        "concepts": ["Resource Ownership", "Write Protection"],
    },
    "UC-DE-02.3": {
        "product": "de",
        "title": "Share MoM - ambiguous title",
        "description": "Organiser asks to share 'Weekly Sync' MoM but multiple exist.",
        "user_email": "sandy@gdplabs.id",
        "agent": "de-pm-agent",
        "message": "Share the Weekly Sync MoM with all attendees",
        "tool_inputs": {
            "google_drive_share_file": {"mom_title": "Weekly Sync"},
        },
        "resource_context": {
            "mom_title": "Weekly Sync",
            "requester_email": "sandy@gdplabs.id",
            "access_type": "user",
        },
        "expected_outcome": "approval_required",
        "brd_refs": ["BR-AP-04"],
        "concepts": ["Ambiguity Resolution", "Human-in-the-Loop"],
    },
    "UC-DE-02.4": {
        "product": "de",
        "title": "Share MoM - external recipient (partial)",
        "description": "Organiser shares MoM but includes an external recipient. External blocked.",
        "user_email": "sandy@gdplabs.id",
        "agent": "de-pm-agent",
        "message": "Share the GL IAM standup MoM with all attendees and external@external.com",
        "tool_inputs": {
            "google_drive_share_file": {
                "mom_id": "mom-001",
                "recipients": ["maylina@gdplabs.id", "external@external.com"],
            },
        },
        "resource_context": {
            "mom_id": "mom-001",
            "requester_email": "sandy@gdplabs.id",
            "recipients": ["maylina@gdplabs.id", "external@external.com"],
            "access_type": "user",
        },
        "expected_outcome": "partial_success",
        "brd_refs": ["BR-RB-04", "BR-OH-02"],
        "concepts": ["External Recipient Boundary", "Partial Success"],
    },
    "UC-DE-03.1": {
        "product": "de",
        "title": "Access MoM - attendee",
        "description": "An attendee asks to summarize the MoM. Access granted.",
        "user_email": "maylina@gdplabs.id",
        "agent": "de-pm-agent",
        "message": "Summarize yesterday's GL IAM standup",
        "tool_inputs": {
            "meemo_get_meeting_details": {"mom_id": "mom-001"},
        },
        "resource_context": {
            "mom_id": "mom-001",
            "requester_email": "maylina@gdplabs.id",
            "access_type": "user",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-02", "BR-AP-01", "BR-RB-01"],
        "concepts": ["Delegated Access", "Resource Access"],
    },
    "UC-DE-03.2": {
        "product": "de",
        "title": "Access MoM - non-attendee super user",
        "description": "Dept head (non-attendee, super user) accesses MoM. Elevated access.",
        "user_email": "dept-head@gdplabs.id",
        "agent": "de-pm-agent",
        "message": "Summarize yesterday's GL IAM standup",
        "tool_inputs": {
            "meemo_get_meeting_details": {"mom_id": "mom-001"},
        },
        "resource_context": {
            "mom_id": "mom-001",
            "requester_email": "dept-head@gdplabs.id",
            "access_type": "agent",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-RB-06", "BR-DA-04"],
        "concepts": ["Hierarchical Access", "Agent Authorization"],
    },
    "UC-DE-04.1": {
        "product": "de",
        "title": "Cross-tenant agent invocation (rejected)",
        "description": "Bob from GLAIR tries to invoke DE PM Agent in GLC.",
        "user_email": "bob@gdplabs.id",
        "agent": "de-pm-agent",
        "message": "Summarize yesterday's GL IAM standup",
        "tool_inputs": {},
        "resource_context": {
            "access_type": "user",
        },
        "expected_outcome": "rejected",
        "brd_refs": ["BR-ID-05", "BR-RB-07"],
        "concepts": ["Tenant Boundary", "Agent Tenant Binding"],
    },
    "UC-DE-06.1": {
        "product": "de",
        "title": "Send Invoice - GLC PM (success)",
        "description": "GLC PM has invoice_send feature entitlement. Invoice sent.",
        "user_email": "glc-pm@gdplabs.id",
        "agent": "de-pm-agent",
        "message": "Send all AWS invoices April 2026",
        "tool_inputs": {
            "invoice_send": {"invoice_id": "inv-aws-2026-04"},
        },
        "resource_context": {
            "access_type": "user",
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-SA-04"],
        "concepts": ["Feature-Level Access Control", "Scope Attenuation"],
    },
    "UC-DE-06.2": {
        "product": "de",
        "title": "Send Invoice - Other PM (rejected)",
        "description": "Other Team PM does NOT have invoice_send. Request rejected.",
        "user_email": "other-pm@gdplabs.id",
        "agent": "de-pm-agent",
        "message": "Send all AWS invoices April 2026",
        "tool_inputs": {
            "invoice_send": {"invoice_id": "inv-aws-2026-04"},
        },
        "resource_context": {
            "access_type": "user",
        },
        "expected_outcome": "rejected",
        "brd_refs": ["BR-SA-04"],
        "concepts": ["Feature-Level Access Control", "Scope Attenuation"],
    },

    # =========================================================================
    # AIP Use Cases
    # =========================================================================
    "UC-AIP-01.1": {
        "product": "aip",
        "title": "Weekly report - employee filled",
        "description": "Autonomous agent sends final weekly report. Employee has filled it.",
        "user_email": None,  # Autonomous agent - no user
        "agent": "weekly-report-agent",
        "message": "Send final weekly report for onlee@gdplabs.id",
        "tool_inputs": {
            "google_docs_get_document": {"report_email": "onlee@gdplabs.id"},
            "google_mail_send_email": {"to": "manager@gdplabs.id"},
        },
        "resource_context": {
            "report_email": "onlee@gdplabs.id",
            "access_type": "agent",
            "autonomous": True,
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-03", "BR-ID-04"],
        "concepts": ["Agent's Own Identity", "Autonomous Execution"],
    },
    "UC-AIP-01.2": {
        "product": "aip",
        "title": "Weekly report - employee NOT filled",
        "description": "Autonomous agent sends report but employee hasn't filled it. Still succeeds.",
        "user_email": None,
        "agent": "weekly-report-agent",
        "message": "Send final weekly report for bob@gdplabs.id",
        "tool_inputs": {
            "google_docs_get_document": {"report_email": "bob@gdplabs.id"},
            "google_mail_send_email": {"to": "manager@gdplabs.id"},
        },
        "resource_context": {
            "report_email": "bob@gdplabs.id",
            "access_type": "agent",
            "autonomous": True,
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-03", "BR-OH-01"],
        "concepts": ["Agent's Own Identity", "Graceful Handling"],
    },
    "UC-AIP-02.1": {
        "product": "aip",
        "title": "Draft report - active email",
        "description": "Agent sends draft weekly report. Employee email is active.",
        "user_email": None,
        "agent": "weekly-report-agent",
        "message": "Send draft weekly report to onlee@gdplabs.id",
        "tool_inputs": {
            "google_docs_create_document": {"title": "Draft Weekly Report"},
            "google_mail_send_email": {"to": "onlee@gdplabs.id"},
        },
        "resource_context": {
            "report_email": "onlee@gdplabs.id",
            "access_type": "agent",
            "autonomous": True,
        },
        "expected_outcome": "success",
        "brd_refs": ["BR-DA-03"],
        "concepts": ["Agent's Own Identity", "Agent Resource Access"],
    },
    "UC-AIP-02.2": {
        "product": "aip",
        "title": "Draft report - resigned employee (warning)",
        "description": "Agent sends draft but employee has resigned. Email bounces.",
        "user_email": None,
        "agent": "weekly-report-agent",
        "message": "Send draft weekly report to resigned@gdplabs.id",
        "tool_inputs": {
            "google_docs_create_document": {"title": "Draft Weekly Report"},
            "google_mail_send_email": {"to": "resigned@gdplabs.id"},
        },
        "resource_context": {
            "report_email": "resigned@gdplabs.id",
            "access_type": "agent",
            "autonomous": True,
        },
        "expected_outcome": "success_with_warning",
        "brd_refs": ["BR-OH-03"],
        "concepts": ["Graceful Failure with Warning", "Agent Resource Access"],
    },
}


def get_scenarios_by_product() -> dict[str, list[dict]]:
    """Group scenarios by product for dashboard display."""
    grouped: dict[str, list[dict]] = {"glchat": [], "de": [], "aip": []}
    for scenario_id, scenario in SCENARIOS.items():
        summary = {
            "id": scenario_id,
            "product": scenario["product"],
            "title": scenario["title"],
            "description": scenario["description"],
            "expected_outcome": scenario["expected_outcome"],
            "brd_refs": scenario["brd_refs"],
            "concepts": scenario["concepts"],
        }
        grouped[scenario["product"]].append(summary)
    return grouped
