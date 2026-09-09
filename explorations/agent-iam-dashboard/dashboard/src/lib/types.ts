export type AppPhase = "idle" | "setting-up" | "ready" | "running";

export type ServiceName = "glchat" | "aip" | "connectors";
export type ServiceHealth = Record<ServiceName, boolean | null>;

export interface ScenarioMeta {
  id: string;
  title: string;
  description: string;
  product: string;
  expected_outcome: string;
  brd_refs: string[];
  concepts: string[];
  message?: string;
  access_type?: string;
  resolved_scenario?: string;
  user_role?: string;
  [key: string]: string | string[] | undefined;
}

export type ScenariosByProduct = Record<string, ScenarioMeta[]>;

export interface SetupEntity {
  id?: string | null;
  email?: string;
  name?: string;
  role?: string;
  type?: string;
  tenant?: string;
  active?: boolean;
  allowed_scopes?: string[];
  error?: string;
}

export interface SetupResult {
  status: string;
  users: Record<string, SetupEntity>;
  agents: Record<string, SetupEntity>;
}

export interface AuditEvent {
  event: string;
  event_type?: string;
  timestamp: string;
  service: string;
  source?: string;
  message?: string;
  severity?: string;
  delegation_ref?: string;
  user_id?: string;
  organization_id?: string;
  resource_id?: string;
  [key: string]: string | undefined;
}

export interface BlockedTool {
  tool: string;
  missing_scope?: string;
  reason?: string;
}

export interface ToolResult {
  tool: string;
  status: string;
  result?: Record<string, unknown>;
  error?: string;
  warnings?: string[];
  enforcement_layer?: string;
}

export interface DelegationChainEntry {
  step?: string;
  label: string;
  depth: number;
  agent_id?: string;
  worker?: string;
  token?: string;
  scope?: string;
  scopes?: string[];
  error?: string;
}

export interface ExecutionLogEntry {
  step: string;
  status: string;
  agent_id?: string;
  scopes?: string[];
  parent_scopes: string[];
  requested_scopes?: string[];
  denied_scopes?: string[];
  rejected_scopes?: string[];
  planned_tools?: string[];
  blocked_tools?: BlockedTool[];
  error?: string;
  worker?: string;
}

export interface AipResponse {
  outcome?: string;
  user_message?: string;
  delegation_chain: DelegationChainEntry[];
  execution_log: ExecutionLogEntry[];
  tool_results: ToolResult[];
  blocked_tools?: BlockedTool[];
  effective_scopes?: string[];
}

export interface ScenarioRunResult {
  scenario_id?: string;
  scenario: ScenarioMeta;
  delegation_ref?: string;
  delegation_token?: string;
  outcome?: string;
  reason?: string;
  user: {
    email?: string;
    role?: string;
    tenant?: string;
    active?: boolean;
    features?: string[];
  } | null;
  abac?: {
    user_scopes: string[];
    agent_ceiling: string[];
    attenuated_scopes: string[];
    effective_scopes?: string[];
    rule: string;
  };
  aip_response?: AipResponse | null;
}
