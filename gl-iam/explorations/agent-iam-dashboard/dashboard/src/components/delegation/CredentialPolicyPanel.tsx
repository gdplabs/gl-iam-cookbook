import { useState } from "react";
import { Key, User, Bot, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AGENT_CREDENTIAL_POLICIES } from "@/lib/role-scopes";
import type { CredentialSource } from "@/lib/role-scopes";

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  member: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  viewer: "bg-gray-500/20 text-gray-300 border-gray-500/30",
  autonomous: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
};

function SourceBadge({ source }: { source: CredentialSource }) {
  if (source === "user") {
    return (
      <Badge variant="outline" className="text-[9px] px-1 py-0 bg-blue-500/15 text-blue-300 border-blue-500/30">
        <User className="size-2 mr-0.5" />User
      </Badge>
    );
  }
  if (source === "agent") {
    return (
      <Badge variant="outline" className="text-[9px] px-1 py-0 bg-amber-500/15 text-amber-300 border-amber-500/30">
        <Bot className="size-2 mr-0.5" />Agent
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-[9px] px-1 py-0 bg-emerald-500/15 text-emerald-300 border-emerald-500/30">
      <User className="size-2 mr-0.5" />User*
    </Badge>
  );
}

interface CredentialPolicyPanelProps {
  agentName?: string;
}

export function CredentialPolicyPanel({ agentName }: CredentialPolicyPanelProps) {
  const [expanded, setExpanded] = useState(true);

  // Show all orchestrator agents or just the selected one
  const agentsToShow = agentName
    ? { [agentName]: AGENT_CREDENTIAL_POLICIES[agentName] }
    : Object.fromEntries(
        Object.entries(AGENT_CREDENTIAL_POLICIES).filter(
          ([, p]) => p && Object.keys(p.rules).length > 1 // skip autonomous-only
        )
      );

  if (Object.keys(agentsToShow).length === 0) return null;

  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-semibold hover:text-foreground transition-colors w-full"
      >
        <Key className="size-4" />
        Credential Routing Policy
        {expanded ? <ChevronUp className="size-3.5 ml-auto" /> : <ChevronDown className="size-3.5 ml-auto" />}
      </button>

      {expanded && (
        <Card size="sm">
          <CardContent>
            <p className="text-[10px] text-muted-foreground mb-3">
              Deterministic rules that decide which OAuth credential (User vs Agent) is used per tool, based on user role.
              The same agent produces different credential routing depending on who invokes it.
            </p>

            {Object.entries(agentsToShow).map(([name, policy]) => {
              if (!policy) return null;
              // Collect all scopes across all roles
              const allScopes = new Set<string>();
              for (const roleRules of Object.values(policy.rules)) {
                for (const scope of Object.keys(roleRules)) {
                  allScopes.add(scope);
                }
              }
              const roles = Object.keys(policy.rules);

              return (
                <div key={name} className="mb-4 last:mb-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-medium text-foreground">{name}</span>
                    <span className="text-[10px] text-muted-foreground">— {policy.description}</span>
                  </div>

                  <div className="overflow-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-border text-muted-foreground">
                          <th className="py-1 pr-3 text-left font-medium text-[10px]">Scope</th>
                          {roles.map((role) => (
                            <th key={role} className="px-2 py-1 text-center font-medium text-[10px]">
                              <Badge variant="outline" className={`text-[9px] px-1 py-0 ${ROLE_COLORS[role] ?? ""}`}>
                                {role}
                              </Badge>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {Array.from(allScopes).sort().map((scope) => (
                          <tr key={scope} className="border-b border-border/30">
                            <td className="py-1 pr-3 font-mono text-[10px] text-muted-foreground">{scope}</td>
                            {roles.map((role) => {
                              const rule = policy.rules[role]?.[scope];
                              return (
                                <td key={role} className="px-2 py-1 text-center" title={rule?.reason}>
                                  {rule ? (
                                    <SourceBadge source={rule.source} />
                                  ) : (
                                    <span className="text-muted-foreground/30">—</span>
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="flex gap-4 mt-2 text-[9px] text-muted-foreground">
                    <span className="flex items-center gap-1"><User className="size-2 text-blue-300" /> User = must use User OAuth</span>
                    <span className="flex items-center gap-1"><Bot className="size-2 text-amber-300" /> Agent = always Agent OAuth</span>
                    <span className="flex items-center gap-1"><User className="size-2 text-emerald-300" /> User* = User OAuth, fallback Agent</span>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
