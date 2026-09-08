export const ROLE_SCOPES: Record<string, { scopes: string[]; description: string }> = {
  admin: {
    scopes: [
      "google_calendar_events_list", "google_calendar_events_insert", "slack_send_message",
      "notion_get_page", "google_mail_send_email", "meemo_get_meeting_details",
      "meemo_create_meeting_notes", "google_docs_get_document", "google_docs_create_document",
      "google_drive_share_file", "invoice_send", "directory_lookup",
    ],
    description: "Full access - all platform scopes",
  },
  member: {
    scopes: [
      "google_calendar_events_list", "google_calendar_events_insert", "notion_get_page",
      "meemo_get_meeting_details", "meemo_create_meeting_notes", "google_docs_get_document",
      "google_docs_create_document", "google_drive_share_file", "google_mail_send_email",
      "directory_lookup",
    ],
    description: "Standard access - no Slack or invoice by default",
  },
  viewer: {
    scopes: ["google_calendar_events_list", "notion_get_page", "meemo_get_meeting_details", "google_docs_get_document", "directory_lookup"],
    description: "Read-only access",
  },
};

type CredentialSource = "user" | "user_if_available" | "agent";

export const CREDENTIAL_ROUTING: Record<string, { source: CredentialSource; label: string }> = {
  google_calendar_events_list: { source: "user_if_available", label: "User OAuth for own resources; agent OAuth for approved delegated resources" },
  google_calendar_events_insert: { source: "user_if_available", label: "User OAuth for own resources; agent OAuth only for approved write targets" },
  directory_lookup: { source: "agent", label: "Agent service credential" },
  google_mail_send_email: { source: "user_if_available", label: "User OAuth preferred" },
  slack_send_message: { source: "agent", label: "Agent service credential" },
  notion_get_page: { source: "agent", label: "Agent service credential" },
  meemo_get_meeting_details: { source: "agent", label: "Agent service credential" },
  meemo_create_meeting_notes: { source: "agent", label: "Agent service credential" },
  google_docs_get_document: { source: "user_if_available", label: "User OAuth preferred" },
  google_docs_create_document: { source: "user_if_available", label: "User OAuth preferred" },
  google_drive_share_file: { source: "user_if_available", label: "User OAuth preferred" },
  invoice_send: { source: "agent", label: "Agent service credential with admin entitlement" },
};

export function resolveEffectiveCredential(
  _agentName: string,
  role: string,
  scope: string,
  accessType?: string,
): { source: CredentialSource; reason: string } | null {
  if (!ROLE_SCOPES[role]?.scopes.includes(scope) && role !== "autonomous") return null;
  if (accessType === "user") return { source: "user", reason: "The request targets the user's own resource" };
  if (accessType === "agent") return { source: "agent", reason: "The request targets an approved delegated resource" };
  return CREDENTIAL_ROUTING[scope]
    ? { source: CREDENTIAL_ROUTING[scope].source, reason: CREDENTIAL_ROUTING[scope].label }
    : null;
}

export const CALENDAR_ACCESS_POLICY = [
  {
    resource: "Own calendar", scope: "google_calendar_events_list / insert", constraintKey: "self-access",
    admin: "User+Agent", member: "User", guest: "User",
    adminConstraint: "User first, agent fallback", memberConstraint: "Own OAuth only", guestConstraint: "Read only",
  },
  {
    resource: "Nadia's calendar", scope: "google_calendar_events_list / insert", constraintKey: "target_whitelist / write_whitelist",
    admin: "User+Agent", member: "Agent", guest: "Agent",
    adminConstraint: "Wildcard", memberConstraint: "Explicitly whitelisted", guestConstraint: "Read only",
  },
  {
    resource: "Same-organization colleague", scope: "google_calendar_events_list", constraintKey: "target_whitelist",
    admin: "Agent", member: "Agent", guest: "Denied",
    adminConstraint: "Wildcard", memberConstraint: "org:{user.tenant}", guestConstraint: "Not whitelisted",
  },
  {
    resource: "External-organization colleague", scope: "google_calendar_events_list", constraintKey: "target_whitelist",
    admin: "Agent", member: "Denied", guest: "Denied",
    adminConstraint: "Wildcard", memberConstraint: "Organization boundary", guestConstraint: "Not whitelisted",
  },
] as const;
