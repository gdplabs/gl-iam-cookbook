export interface ResourcePolicyRule {
  action: "ALLOW" | "DENY";
  condition: string;
  detail: string;
}

export interface WorkerConfig {
  name: string;
  scopes: string[];
  resourcePolicy?: { description: string; rules: ResourcePolicyRule[] };
}

export interface AgentConfig {
  name: string;
  type: "orchestrator" | "autonomous";
  product: string;
  allowedScopes: string[];
  workers: WorkerConfig[];
  resourceConstraints: {
    description: string;
    perRole: Record<string, Record<string, string>>;
  };
}

const calendarPolicy = {
  description: "The worker enforces target and write whitelists before connector dispatch.",
  rules: [
    { action: "ALLOW", condition: "target == user", detail: "self-access uses User OAuth" },
    { action: "ALLOW", condition: "target in target_whitelist", detail: "delegated read is permitted" },
    { action: "DENY", condition: "target not whitelisted", detail: "stop before calling the connector" },
  ] as ResourcePolicyRule[],
};

export const AGENT_CONFIGS: AgentConfig[] = [
  {
    name: "scheduling-agent", type: "orchestrator", product: "GLChat",
    allowedScopes: ["google_calendar_events_list", "google_calendar_events_insert", "slack_send_message", "notion_get_page", "directory_lookup"],
    workers: [
      { name: "calendar-worker", scopes: ["google_calendar_events_list", "google_calendar_events_insert"], resourcePolicy: calendarPolicy },
      { name: "comms-worker", scopes: ["slack_send_message", "notion_get_page"] },
      { name: "directory-worker", scopes: ["directory_lookup"] },
    ],
    resourceConstraints: {
      description: "Calendar access is narrowed per role and carried in the delegation token.",
      perRole: {
        admin: { target_whitelist: "*", write_whitelist: "*" },
        member: { target_whitelist: "[Nadia, same organization]", write_whitelist: "[Nadia]" },
        viewer: { target_whitelist: "[Nadia]", write_whitelist: "[]" },
      },
    },
  },
  {
    name: "de-pm-agent", type: "orchestrator", product: "Digital Employee",
    allowedScopes: ["meemo_get_meeting_details", "meemo_create_meeting_notes", "google_docs_get_document", "google_docs_create_document", "google_drive_share_file", "google_mail_send_email", "google_calendar_events_list", "invoice_send"],
    workers: [
      { name: "meemo-worker", scopes: ["meemo_get_meeting_details", "meemo_create_meeting_notes"] },
      { name: "docs-worker", scopes: ["google_docs_get_document", "google_docs_create_document", "google_drive_share_file"] },
      { name: "comms-worker", scopes: ["google_mail_send_email"] },
    ],
    resourceConstraints: {
      description: "Document and invoice actions remain bounded by user scopes and feature entitlements.",
      perRole: {
        admin: { features: "all configured features" },
        member: { features: "standard collaboration features" },
        viewer: { features: "read-only" },
      },
    },
  },
  {
    name: "weekly-report-agent", type: "autonomous", product: "AI Platform",
    allowedScopes: ["google_docs_get_document", "google_docs_create_document", "google_drive_share_file", "google_mail_send_email"],
    workers: [
      { name: "docs-worker", scopes: ["google_docs_get_document", "google_docs_create_document", "google_drive_share_file"] },
      { name: "comms-worker", scopes: ["google_mail_send_email"] },
    ],
    resourceConstraints: {
      description: "The scheduler is the principal and receives only the configured autonomous-agent scopes.",
      perRole: { autonomous: { principal: "scheduler service", delegation: "agent-scoped" } },
    },
  },
];
