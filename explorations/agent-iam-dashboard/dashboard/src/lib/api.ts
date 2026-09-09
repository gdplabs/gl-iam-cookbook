import type {
  AuditEvent,
  ScenarioRunResult,
  ScenariosByProduct,
  ServiceName,
  SetupResult,
} from "./types";

export interface DemoUser {
  email: string;
  display_name: string;
  role: string;
  tenant: string;
  features: string[];
  scopes: string[];
  is_super_user: boolean;
}

export interface DemoOrchestrator {
  id: string;
  name: string;
  type: string;
  product: string;
  allowed_scopes: string[];
}

export interface DemoAction {
  id: string;
  title: string;
  message: string;
  description: string;
  concepts: string[];
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const body = await response.json().catch(() => null) as { detail?: string } | null;
  if (!response.ok) {
    throw new Error(body?.detail ?? `${response.status} ${response.statusText}`);
  }
  return body as T;
}

export async function checkHealth(service: ServiceName): Promise<boolean> {
  try {
    const health = await requestJson<{ status?: string }>(`/api/${service}/health`);
    return health.status === undefined || ["ok", "healthy"].includes(health.status);
  } catch {
    return false;
  }
}

export function demoSetup(): Promise<SetupResult> {
  return requestJson("/api/glchat/demo/setup", { method: "POST" });
}

export function demoReset(): Promise<{ status: string }> {
  return requestJson("/api/glchat/demo/reset", { method: "POST" });
}

export function getScenarios(): Promise<ScenariosByProduct> {
  return requestJson("/api/glchat/scenarios");
}

export function runScenario(scenarioId: string): Promise<ScenarioRunResult> {
  return requestJson(`/api/glchat/scenarios/${encodeURIComponent(scenarioId)}/run`, {
    method: "POST",
  });
}

export function getDemoUsers(): Promise<DemoUser[]> {
  return requestJson("/api/glchat/demo/users");
}

export function getDemoOrchestrators(): Promise<DemoOrchestrator[]> {
  return requestJson("/api/glchat/demo/orchestrators");
}

export function getDemoActions(): Promise<Record<string, DemoAction[]>> {
  return requestJson("/api/glchat/demo/actions");
}

export function interactiveRun(
  userEmail: string,
  agentName: string,
  actionId: string,
): Promise<ScenarioRunResult> {
  return requestJson("/api/glchat/demo/interactive-run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_email: userEmail,
      agent_name: agentName,
      scenario_id: actionId,
    }),
  });
}

export async function getAllAuditEvents(delegationRef?: string): Promise<AuditEvent[]> {
  const query = delegationRef
    ? `?delegation_ref=${encodeURIComponent(delegationRef)}`
    : "";
  const appRequests = (["glchat", "aip", "connectors"] as ServiceName[]).map(
    async (service) => {
      const events = await requestJson<AuditEvent[]>(`/api/${service}/audit/events${query}`);
      return events.map((event) => ({ ...event, service: event.service ?? service, source: event.source ?? "app" }));
    },
  );
  const sdkRequest = requestJson<AuditEvent[]>("/api/glchat/audit/sdk-events")
    .then((events) => events.map((event) => ({ ...event, source: event.source ?? "sdk" })));

  const batches = await Promise.allSettled([...appRequests, sdkRequest]);
  return batches
    .flatMap((batch) => batch.status === "fulfilled" ? batch.value : [])
    .filter((event) => !delegationRef || event.delegation_ref === delegationRef)
    .sort((left, right) => Date.parse(left.timestamp) - Date.parse(right.timestamp));
}
