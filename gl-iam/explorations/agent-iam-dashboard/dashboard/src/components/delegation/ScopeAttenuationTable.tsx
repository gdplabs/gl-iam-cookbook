import { CheckCircle2, XCircle, Minus, User, Bot } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { CREDENTIAL_ROUTING, resolveEffectiveCredential } from "@/lib/role-scopes";
import type { ScenarioRunResult, DelegationChainEntry } from "@/lib/types";

interface ScopeAttenuationTableProps {
  result: ScenarioRunResult;
}

function collectScopesByDepth(chain: DelegationChainEntry[]): Record<number, Set<string>> {
  const byDepth: Record<number, Set<string>> = { 1: new Set(), 2: new Set(), 3: new Set(), 4: new Set() };
  for (const entry of chain) {
    const d = entry.depth;
    if (d < 1 || d > 4) continue;
    const scopes = entry.scopes ?? (entry.scope ? [entry.scope] : []);
    for (const s of scopes) {
      byDepth[d]!.add(s);
    }
  }
  return byDepth;
}

function collectAllScopes(chain: DelegationChainEntry[], userScopes?: string[]): string[] {
  const all = new Set<string>();
  if (userScopes) {
    for (const s of userScopes) all.add(s);
  }
  for (const entry of chain) {
    const scopes = entry.scopes ?? (entry.scope ? [entry.scope] : []);
    for (const s of scopes) all.add(s);
  }
  return Array.from(all).sort();
}

function ScopeCell({ present, applicable }: { present: boolean; applicable: boolean }) {
  if (!applicable) {
    return <Minus className="mx-auto size-3.5 text-muted-foreground/40" />;
  }
  return present ? (
    <CheckCircle2 className="mx-auto size-3.5 text-green-400" />
  ) : (
    <XCircle className="mx-auto size-3.5 text-red-400" />
  );
}

/** Map scope name to tool name for credential routing lookup.
 *  Since scopes now use tool names directly, this is an identity mapping.
 */
function scopeToToolName(scope: string): string | null {
  // Scopes are now identical to tool names — return as-is if it exists in CREDENTIAL_ROUTING
  return CREDENTIAL_ROUTING[scope] ? scope : null;
}

function CredentialBadge({ toolName, scope, agentName, role, accessType }: {
  toolName: string | null;
  scope: string;
  agentName?: string;
  role?: string;
  accessType?: string;
}) {
  if (!toolName) return <Minus className="mx-auto size-3.5 text-muted-foreground/40" />;

  // Role-aware + access_type-aware resolution
  const effective = agentName && role
    ? resolveEffectiveCredential(agentName, role, scope, accessType)
    : null;

  // Fall back to static routing if no policy match
  const source = effective?.source ?? CREDENTIAL_ROUTING[toolName]?.source;
  const reason = effective?.reason ?? CREDENTIAL_ROUTING[toolName]?.label;

  if (!source) return <Minus className="mx-auto size-3.5 text-muted-foreground/40" />;

  if (source === "user" || source === "user_if_available") {
    return (
      <Badge variant="outline" className="text-[9px] px-1 py-0 bg-blue-500/15 text-blue-300 border-blue-500/30 cursor-help" title={reason}>
        <User className="size-2 mr-0.5" />
        User OAuth
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-[9px] px-1 py-0 bg-amber-500/15 text-amber-300 border-amber-500/30 cursor-help" title={reason}>
      <Bot className="size-2 mr-0.5" />
      Agent OAuth
    </Badge>
  );
}

export function ScopeAttenuationTable({ result }: ScopeAttenuationTableProps) {
  const aip = result.aip_response;
  if (!aip || aip.delegation_chain.length === 0) return null;

  // Add user scopes as d1
  const userScopes = result.abac?.user_scopes;
  const byDepth = collectScopesByDepth(aip.delegation_chain);
  if (userScopes) {
    byDepth[1] = new Set(userScopes);
  }

  const allScopes = collectAllScopes(aip.delegation_chain, userScopes);
  const maxDepthPresent = Math.max(...aip.delegation_chain.map((e) => e.depth));

  // Extract agent name, user role, and access_type for credential routing
  const orchestratorEntry = aip.delegation_chain.find(e => e.depth === 2);
  const agentId = orchestratorEntry?.agent_id ?? "";
  const agentName = agentId.split(":").pop() ?? "";
  const userRole = result.user?.role ?? (result.user === null ? "autonomous" : "member");
  // access_type from scenario metadata (set by backend from resource_context)
  const accessType = result.scenario?.access_type;

  if (allScopes.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">Scope Attenuation</h3>
      <Card size="sm">
        <CardContent>
          <div className="overflow-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="py-1.5 pr-4 text-left font-medium">Scope</th>
                  <th className="px-2 py-1.5 text-center font-medium">d1 User</th>
                  <th className="px-2 py-1.5 text-center font-medium">d2 Agent</th>
                  <th className="px-2 py-1.5 text-center font-medium">d3 Worker</th>
                  <th className="px-2 py-1.5 text-center font-medium">d4 Tool</th>
                  <th className="px-2 py-1.5 text-center font-medium">Credential</th>
                </tr>
              </thead>
              <tbody>
                {allScopes.map((scope) => {
                  const toolName = scopeToToolName(scope);
                  const isUsedAtD4 = byDepth[4]?.has(scope) ?? false;
                  return (
                    <tr key={scope} className="border-b border-border/50">
                      <td className="py-1.5 pr-4 font-mono">{scope}</td>
                      {[1, 2, 3, 4].map((d) => (
                        <td key={d} className="px-2 py-1.5 text-center">
                          <ScopeCell
                            present={byDepth[d]?.has(scope) ?? false}
                            applicable={d <= maxDepthPresent || (d === 1 && !!userScopes)}
                          />
                        </td>
                      ))}
                      <td className="px-2 py-1.5 text-center">
                        {isUsedAtD4 ? (
                          <CredentialBadge toolName={toolName} scope={scope} agentName={agentName} role={userRole} accessType={accessType} />
                        ) : (
                          <Minus className="mx-auto size-3.5 text-muted-foreground/40" />
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="text-[10px] text-muted-foreground mt-2">
              * User OAuth if available, falls back to Agent service token
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
