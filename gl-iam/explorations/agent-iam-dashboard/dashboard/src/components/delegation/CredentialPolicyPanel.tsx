import { useState } from "react";
import { Key, User, Bot, ChevronDown, ChevronUp, XCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CALENDAR_ACCESS_POLICY } from "@/lib/role-scopes";

function AccessCell({ value, constraint }: { value: string; constraint?: string }) {
  if (value === "User") {
    return (
      <Badge variant="outline" className="text-[9px] px-1 py-0 bg-blue-500/15 text-blue-300 border-blue-500/30 cursor-help" title={constraint}>
        <User className="size-2 mr-0.5" />User
      </Badge>
    );
  }
  if (value === "User+Agent") {
    return (
      <Badge variant="outline" className="text-[9px] px-1 py-0 bg-emerald-500/15 text-emerald-300 border-emerald-500/30 cursor-help" title={constraint}>
        <User className="size-2 mr-0.5" />User+Agent
      </Badge>
    );
  }
  if (value === "Agent") {
    return (
      <Badge variant="outline" className="text-[9px] px-1 py-0 bg-amber-500/15 text-amber-300 border-amber-500/30 cursor-help" title={constraint}>
        <Bot className="size-2 mr-0.5" />Agent
      </Badge>
    );
  }
  return (
    <span title={constraint}><XCircle className="mx-auto size-3.5 text-red-400/60" /></span>
  );
}

interface CredentialPolicyPanelProps {
  agentName?: string;
}

export function CredentialPolicyPanel({ agentName }: CredentialPolicyPanelProps) {
  const [expanded, setExpanded] = useState(true);

  // Only show for scheduling-agent (or when no agent is specified)
  if (agentName && agentName !== "scheduling-agent") return null;

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
              Deterministic rules: same agent, same tool, same scope — but credential and access depends on <strong>who you are</strong> and <strong>what resource</strong> you're touching.
            </p>

            <div className="overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="py-1.5 pr-3 text-left font-medium text-[10px]">Resource</th>
                    <th className="px-2 py-1.5 text-center font-medium text-[10px]">
                      <Badge variant="outline" className="text-[9px] px-1 py-0 bg-purple-500/20 text-purple-300 border-purple-500/30">
                        Admin
                      </Badge>
                    </th>
                    <th className="px-2 py-1.5 text-center font-medium text-[10px]">
                      <Badge variant="outline" className="text-[9px] px-1 py-0 bg-blue-500/20 text-blue-300 border-blue-500/30">
                        Member
                      </Badge>
                    </th>
                    <th className="px-2 py-1.5 text-center font-medium text-[10px]">
                      <Badge variant="outline" className="text-[9px] px-1 py-0 bg-gray-500/20 text-gray-300 border-gray-500/30">
                        Guest
                      </Badge>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {CALENDAR_ACCESS_POLICY.map((row) => (
                    <>
                      <tr key={row.resource} className="border-b border-border/10">
                        <td className="pt-2 pb-0.5 pr-3 text-[10px] text-foreground font-medium">{row.resource}</td>
                        <td className="px-2 pt-2 pb-0.5 text-center">
                          <AccessCell value={row.admin} constraint={row.adminConstraint} />
                        </td>
                        <td className="px-2 pt-2 pb-0.5 text-center">
                          <AccessCell value={row.member} constraint={row.memberConstraint} />
                        </td>
                        <td className="px-2 pt-2 pb-0.5 text-center">
                          <AccessCell value={row.guest} constraint={row.guestConstraint} />
                        </td>
                      </tr>
                      <tr key={`${row.resource}-detail`} className="border-b border-border/30">
                        <td className="pb-2 pr-3">
                          <div className="text-[8px] text-muted-foreground space-y-0.5">
                            <div>scope: <code className="text-foreground/80">{row.scope}</code></div>
                            <div>constraint: <code className="text-foreground/80">{row.constraintKey}</code></div>
                          </div>
                        </td>
                        <td className="px-2 pb-2 text-center">
                          <span className="text-[8px] text-muted-foreground">{row.adminConstraint}</span>
                        </td>
                        <td className="px-2 pb-2 text-center">
                          <span className="text-[8px] text-muted-foreground">{row.memberConstraint}</span>
                        </td>
                        <td className="px-2 pb-2 text-center">
                          <span className="text-[8px] text-muted-foreground">{row.guestConstraint}</span>
                        </td>
                      </tr>
                    </>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-3 space-y-1.5 text-[9px] text-muted-foreground">
              <div className="flex flex-wrap gap-3">
                <span className="flex items-center gap-1"><User className="size-2 text-blue-300" /> User = user's own OAuth</span>
                <span className="flex items-center gap-1"><User className="size-2 text-emerald-300" /> User+Agent = User first, Agent fallback</span>
                <span className="flex items-center gap-1"><Bot className="size-2 text-amber-300" /> Agent = agent service account only</span>
                <span className="flex items-center gap-1"><XCircle className="size-2 text-red-400/60" /> Denied</span>
              </div>
              <p className="italic">
                Resource constraints in the DelegationToken:
                Admin gets <code className="text-foreground">agent_calendar_access: "*"</code>, <code className="text-foreground">agent_calendar_write_access: "*"</code>.
                Member gets read: <code className="text-foreground">["onlee@gdplabs.id", "org:{'{user.tenant}'}"]</code> (dynamic based on user's org), write: <code className="text-foreground">["onlee@gdplabs.id"]</code> (Pak On only).
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
