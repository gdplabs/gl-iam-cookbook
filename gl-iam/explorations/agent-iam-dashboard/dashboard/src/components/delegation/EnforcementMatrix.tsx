import { useState } from "react";
import { Code2, ChevronDown, ChevronUp, CheckCircle2, XCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ScenarioRunResult } from "@/lib/types";

interface EnforcementMatrixProps {
  result: ScenarioRunResult;
}

interface MatrixRow {
  user: string;
  role: string;
  value: string;
  match: boolean;
  result: string;
  credential: string;
  isCurrent: boolean;
}

interface EnforcementSnippet {
  title: string;
  code: string;
  description: string;
  rows: MatrixRow[];
}

const ROLE_COLORS: Record<string, string> = {
  admin: "text-purple-300",
  member: "text-blue-300",
  viewer: "text-gray-300",
};

function buildSnippet(result: ScenarioRunResult): EnforcementSnippet | null {
  const scenario = result.scenario;
  if (!scenario) return null;

  const user = result.user;
  const userRole = user?.role ?? "viewer";
  const userEmail = user?.email ?? "";
  const title = scenario.title ?? "";
  void scenario.access_type; // available for future use

  // Determine which action pattern this is
  if (title.toLowerCase().includes("own calendar") || title.toLowerCase().includes("schedule meeting on own")) {
    const isWrite = title.toLowerCase().includes("schedule");
    return {
      title: isWrite ? "Write to Own Calendar" : "Check Own Calendar",
      code: `def before_tool_call(target, delegation):
    # target == user_email → SELF ACCESS
    if target == delegation.user_email:
        return Allow(credential="user")  # Always allowed
    # Guest: no User OAuth available
    if delegation.user_role == "viewer":
        return Deny("No User OAuth — not logged in")`,
      description: "Self-access check: target is the user's own email → always allowed with User OAuth.",
      rows: [
        { user: "Pak On", role: "admin", value: "target == self", match: true, result: "Allow", credential: "User OAuth", isCurrent: userRole === "admin" },
        { user: "Maylina", role: "member", value: "target == self", match: true, result: "Allow", credential: "User OAuth", isCurrent: userEmail.startsWith("maylina") },
        { user: "Petry", role: "member", value: "target == self", match: true, result: "Allow", credential: "User OAuth", isCurrent: userEmail.startsWith("petry") },
        { user: "Guest", role: "viewer", value: "target == self, no OAuth", match: false, result: "Deny", credential: "—", isCurrent: userRole === "viewer" },
      ],
    };
  }

  if (title.toLowerCase().includes("pak on") && title.toLowerCase().includes("calendar")) {
    return {
      title: "Check Pak On (CEO) Calendar",
      code: `def before_tool_call(target, delegation):
    # target = "onlee@gdplabs.id" (resolved by directory_lookup)
    assert target != delegation.user_email  # Not self
    # Check: is target in target_whitelist?
    return Allow() if is_in_whitelist(
        "onlee@gdplabs.id", delegation.target_whitelist
    ) else Deny()`,
      description: "Pak On is whitelisted by exact email for all roles. All logged-in users can access via Agent OAuth.",
      rows: [
        { user: "Pak On", role: "admin", value: 'whitelist: "*"', match: true, result: "Allow", credential: "Agent OAuth", isCurrent: userRole === "admin" },
        { user: "Maylina", role: "member", value: '["onlee@...", "org:GLC"]', match: true, result: "Allow", credential: "Agent OAuth", isCurrent: userEmail.startsWith("maylina") },
        { user: "Petry", role: "member", value: '["onlee@...", "org:GLAIR"]', match: true, result: "Allow", credential: "Agent OAuth", isCurrent: userEmail.startsWith("petry") },
        { user: "Guest", role: "viewer", value: '["onlee@gdplabs.id"]', match: true, result: "Allow", credential: "Agent OAuth", isCurrent: userRole === "viewer" },
      ],
    };
  }

  if (title.toLowerCase().includes("sandy") && title.toLowerCase().includes("calendar") && !title.toLowerCase().includes("write")) {
    return {
      title: "Check Sandy's Calendar (GLC)",
      code: `def before_tool_call(target, delegation):
    # target = "sandy@gdplabs.id" (org: GLC)
    # resolved by directory_lookup("Sandy")
    assert target != delegation.user_email
    return Allow() if is_in_whitelist(
        "sandy@gdplabs.id", delegation.target_whitelist
    ) else Deny()

def is_in_whitelist(target, whitelist):
    for pattern in whitelist:
        if pattern == target: return True
        if pattern.startswith("org:"):
            if lookup_org(target) == pattern[4:]:
                return True  # sandy is org:GLC
    return False`,
      description: "Sandy is in GLC org. Members in GLC can access (org:GLC matches). Members in GLAIR cannot (org:GLAIR ≠ GLC).",
      rows: [
        { user: "Pak On", role: "admin", value: '"*" (wildcard)', match: true, result: "Allow", credential: "Agent OAuth", isCurrent: userRole === "admin" },
        { user: "Maylina (GLC)", role: "member", value: '"org:GLC" → GLC==GLC', match: true, result: "Allow", credential: "Agent OAuth", isCurrent: userEmail.startsWith("maylina") },
        { user: "Petry (GLAIR)", role: "member", value: '"org:GLAIR" → GLC≠GLAIR', match: false, result: "Deny", credential: "—", isCurrent: userEmail.startsWith("petry") },
        { user: "Guest", role: "viewer", value: "not in [onlee@]", match: false, result: "Deny", credential: "—", isCurrent: userRole === "viewer" },
      ],
    };
  }

  if (title.toLowerCase().includes("petry") && title.toLowerCase().includes("calendar")) {
    return {
      title: "Check Petry's Calendar (GLAIR)",
      code: `def before_tool_call(target, delegation):
    # target = "petry@gdplabs.id" (org: GLAIR)
    if target == delegation.user_email:
        return Allow(credential="user")  # Self!
    return Allow() if is_in_whitelist(
        "petry@gdplabs.id", delegation.target_whitelist
    ) else Deny()`,
      description: "Petry is in GLAIR org. GLC members can't access (org:GLC ≠ GLAIR). Petry accessing own = self-access.",
      rows: [
        { user: "Pak On", role: "admin", value: '"*" (wildcard)', match: true, result: "Allow", credential: "Agent OAuth", isCurrent: userRole === "admin" },
        { user: "Maylina (GLC)", role: "member", value: '"org:GLC" → GLAIR≠GLC', match: false, result: "Deny", credential: "—", isCurrent: userEmail.startsWith("maylina") },
        { user: "Petry (GLAIR)", role: "member", value: "target == self", match: true, result: "Allow", credential: "User OAuth", isCurrent: userEmail.startsWith("petry") },
        { user: "Guest", role: "viewer", value: "not in [onlee@]", match: false, result: "Deny", credential: "—", isCurrent: userRole === "viewer" },
      ],
    };
  }

  if (title.toLowerCase().includes("write") && title.toLowerCase().includes("colleague")) {
    return {
      title: "Write to Colleague's Calendar",
      code: `def before_tool_call(target, delegation):
    # target = "sandy@gdplabs.id" (resolved by LLM)
    if target == delegation.user_email:
        return Allow(credential="user")  # Self write
    # Others: check WRITE whitelist (stricter)
    return Allow() if is_in_whitelist(
        target, delegation.write_whitelist
    ) else Deny()`,
      description: "Write whitelist is stricter than read. Members can only write to Pak On's calendar.",
      rows: [
        { user: "Pak On", role: "admin", value: 'write: "*"', match: true, result: "Allow", credential: "Agent OAuth", isCurrent: userRole === "admin" },
        { user: "Maylina", role: "member", value: 'write: ["onlee@"]', match: false, result: "Deny", credential: "—", isCurrent: userEmail.startsWith("maylina") },
        { user: "Petry", role: "member", value: 'write: ["onlee@"]', match: false, result: "Deny", credential: "—", isCurrent: userEmail.startsWith("petry") },
        { user: "Guest", role: "viewer", value: "write: []", match: false, result: "Deny", credential: "—", isCurrent: userRole === "viewer" },
      ],
    };
  }

  if (title.toLowerCase().includes("invoice")) {
    return {
      title: "Send Invoice (Feature-Gated)",
      code: `def abac_scope_attenuation(user_scopes, agent_ceiling, user):
    scopes = intersect(user_scopes, agent_ceiling)
    # Feature gate: checked BEFORE delegation
    if "invoice_send" in scopes:
        if "invoice_send" not in user.features:
            scopes.remove("invoice_send")
    return scopes  # invoice_send stripped if no entitlement`,
      description: "Feature-level access. Checked at ABAC before delegation — invoice_send scope stripped if user doesn't have the feature.",
      rows: [
        { user: "Pak On", role: "admin", value: 'features: ["invoice_send"]', match: true, result: "Allow", credential: "Agent OAuth", isCurrent: userRole === "admin" },
        { user: "Maylina", role: "member", value: "features: []", match: false, result: "Deny (scope stripped)", credential: "—", isCurrent: userEmail.startsWith("maylina") },
        { user: "Petry", role: "member", value: "features: []", match: false, result: "Deny (scope stripped)", credential: "—", isCurrent: userEmail.startsWith("petry") },
        { user: "Guest", role: "viewer", value: "features: []", match: false, result: "Deny (scope stripped)", credential: "—", isCurrent: userRole === "viewer" },
      ],
    };
  }

  // Autonomous agent actions (weekly report, draft report)
  if (title.toLowerCase().includes("report") || title.toLowerCase().includes("draft")) {
    return {
      title: "Autonomous Agent Execution",
      code: `# Autonomous agent — no user in the chain
# Principal is the scheduler service / CronJob

def create_autonomous_delegation(agent):
    # Delegation token still created for:
    # 1. Audit trail — trace back to scheduler trigger
    # 2. Scope ceiling — agent can't exceed allowed_tools
    # 3. Token expiry — prevents indefinite execution
    # 4. Action budget — limits tool calls per run

    return DelegationToken(
        principal="apikey:scheduler-service",  # NOT a user
        scope=agent.allowed_tools,             # Full ceiling
        resource_constraints={
            "target_whitelist": "*",           # Wildcard (own resources)
            "autonomous": True,
        },
        max_actions=100,
        expires_in_seconds=3600,
    )`,
      description: "Autonomous agents use their own identity and credentials. Delegation token is still created for audit trail, scope ceiling enforcement, and action budgets.",
      rows: [
        { user: "Scheduler (CronJob)", role: "autonomous", value: "scope = agent.allowed_tools", match: true, result: "Allow", credential: "Agent OAuth", isCurrent: true },
        { user: "—", role: "autonomous", value: "target_whitelist = \"*\"", match: true, result: "Allow (wildcard)", credential: "Agent OAuth", isCurrent: false },
        { user: "—", role: "autonomous", value: "token expiry = 1 hour", match: true, result: "Time-bounded", credential: "Agent OAuth", isCurrent: false },
        { user: "—", role: "autonomous", value: "audit: principal = apikey:scheduler", match: true, result: "Traced", credential: "—", isCurrent: false },
      ],
    };
  }

  return null;
}

export function EnforcementMatrix({ result }: EnforcementMatrixProps) {
  const [expanded, setExpanded] = useState(true);
  const snippet = buildSnippet(result);

  if (!snippet) return null;

  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-semibold hover:text-foreground transition-colors w-full"
      >
        <Code2 className="size-4" />
        Enforcement Logic
        <Badge variant="outline" className="text-[10px] ml-1">
          {snippet.title}
        </Badge>
        {expanded ? <ChevronUp className="size-3.5 ml-auto" /> : <ChevronDown className="size-3.5 ml-auto" />}
      </button>

      {expanded && (
        <Card size="sm">
          <CardContent className="space-y-4">
            <p className="text-[10px] text-muted-foreground">{snippet.description}</p>

            {/* Code snippet */}
            <pre className="bg-muted/30 rounded-lg p-3 text-[10px] text-foreground overflow-auto font-mono leading-relaxed border border-border/30">
              {snippet.code}
            </pre>

            {/* Enforcement matrix table */}
            <div className="overflow-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="py-1.5 pr-2 text-left font-medium">User</th>
                    <th className="px-2 py-1.5 text-left font-medium">Evaluation</th>
                    <th className="px-2 py-1.5 text-center font-medium">Match?</th>
                    <th className="px-2 py-1.5 text-center font-medium">Result</th>
                    <th className="px-2 py-1.5 text-center font-medium">Credential</th>
                  </tr>
                </thead>
                <tbody>
                  {snippet.rows.map((row, i) => (
                    <tr
                      key={i}
                      className={`border-b border-border/30 ${row.isCurrent ? "bg-blue-500/5 ring-1 ring-blue-500/20 rounded" : ""}`}
                    >
                      <td className="py-1.5 pr-2">
                        <span className={`font-medium ${ROLE_COLORS[row.role] ?? ""}`}>{row.user}</span>
                        {row.isCurrent && (
                          <Badge variant="outline" className="text-[7px] px-1 py-0 ml-1 bg-blue-500/15 text-blue-400 border-blue-500/30">
                            current
                          </Badge>
                        )}
                      </td>
                      <td className="px-2 py-1.5 font-mono text-muted-foreground">{row.value}</td>
                      <td className="px-2 py-1.5 text-center">
                        {row.match
                          ? <CheckCircle2 className="size-3.5 text-green-400 mx-auto" />
                          : <XCircle className="size-3.5 text-red-400 mx-auto" />
                        }
                      </td>
                      <td className="px-2 py-1.5 text-center">
                        <Badge variant="outline" className={`text-[8px] ${row.result.startsWith("Allow") ? "bg-green-500/10 text-green-400 border-green-500/30" : "bg-red-500/10 text-red-400 border-red-500/30"}`}>
                          {row.result}
                        </Badge>
                      </td>
                      <td className="px-2 py-1.5 text-center text-muted-foreground">{row.credential}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
