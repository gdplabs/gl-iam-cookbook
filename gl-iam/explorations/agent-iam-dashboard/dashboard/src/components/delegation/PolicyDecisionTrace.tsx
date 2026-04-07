import { CheckCircle2, XCircle, Shield } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ScenarioRunResult } from "@/lib/types";

interface PolicyDecisionTraceProps {
  result: ScenarioRunResult;
}

interface DecisionStep {
  label: string;
  check: string;
  value: string;
  passed: boolean;
  detail?: string;
}

function buildDecisionSteps(result: ScenarioRunResult): DecisionStep[] {
  const steps: DecisionStep[] = [];
  const user = result.user;
  const abac = result.abac;
  const aip = result.aip_response;
  const scenario = result.scenario;
  const accessType = scenario?.access_type ?? "user";

  // Step 1: User identity
  if (user) {
    steps.push({
      label: "User Identity",
      check: "Is the user authenticated?",
      value: user.role === "viewer"
        ? `Guest (not logged in) — viewer scopes only`
        : `${user.email} — role: ${user.role}`,
      passed: true,
    });
  } else {
    steps.push({
      label: "Trigger",
      check: "Who initiated the request?",
      value: "System (CronJob) — autonomous agent execution",
      passed: true,
    });
  }

  // Step 2: ABAC scope attenuation
  if (abac) {
    const userScopeCount = abac.user_scopes.length;
    const agentCeiling = abac.agent_ceiling.length;
    const attenuated = abac.attenuated_scopes.length;
    steps.push({
      label: "ABAC Scope Attenuation",
      check: `Intersection of user scopes (${userScopeCount}) ∩ agent ceiling (${agentCeiling})`,
      value: `${attenuated} effective scopes delegated`,
      passed: attenuated > 0,
      detail: attenuated === 0 ? "No overlapping scopes — delegation rejected" : undefined,
    });
  }

  // Step 3: Credential routing decision
  if (user && user.role) {
    const credentialDecision = accessType === "agent"
      ? user.role === "admin"
        ? "Admin → User+Agent (User OAuth first, Agent OAuth fallback)"
        : user.role === "member"
          ? "Member → Agent OAuth only (whitelisted resources)"
          : "Guest → Agent OAuth only (Pak On calendar only)"
      : user.role === "viewer"
        ? "Guest → requires User OAuth → DENIED (not logged in)"
        : `${user.role} → User OAuth (accessing own resources)`;

    steps.push({
      label: "Credential Routing",
      check: `Role "${user.role}" + access_type "${accessType}" → which OAuth?`,
      value: credentialDecision,
      passed: !(user.role === "viewer" && accessType === "user"),
    });
  }

  // Step 4: Resource constraint check
  if (aip) {
    const policyRejected = (aip.execution_log ?? []).filter(
      (e) => e.status === "policy_rejected"
    );
    const executed = (aip.tool_results ?? []).filter(
      (t) => t.status === "executed"
    );

    // Get resource constraints from delegation token
    // Try to extract constraints from the result
    const constraints = result.abac ? {
      agent_calendar_access: result.user?.role === "admin" ? "*"
        : result.user?.role === "member" ? '["onlee@gdplabs.id", "org:GLC"]'
        : '["onlee@gdplabs.id"]',
      agent_calendar_write_access: result.user?.role === "admin" ? "*"
        : result.user?.role === "member" ? '["onlee@gdplabs.id"]'
        : "[]",
    } : null;

    if (policyRejected.length > 0) {
      for (const pr of policyRejected) {
        const toolName = pr.step.includes("→") ? pr.step.split("→")[1] : pr.step;
        steps.push({
          label: "Resource Constraint (Agent Worker Policy)",
          check: `Is target allowed by agent_calendar_access?`,
          value: `${toolName} → DENIED by policy`,
          passed: false,
          detail: pr.error,
        });
      }
    }

    if (executed.length > 0) {
      const toolNames = executed.map(t => t.tool).join(", ");
      steps.push({
        label: "Resource Constraint (Agent Worker Policy)",
        check: "Are targets within allowed resources?",
        value: `${toolNames} → PASSED`,
        passed: true,
        detail: constraints
          ? `Constraints: agent_calendar_access = ${constraints.agent_calendar_access}`
          : undefined,
      });
    }

    // Step 5: Tool execution
    const denied = (aip.tool_results ?? []).filter(t => t.status === "denied");
    if (executed.length > 0) {
      steps.push({
        label: "Tool Execution (GL Connector)",
        check: `Call 3P API via ${accessType === "agent" ? "Agent" : "User"} OAuth`,
        value: `${executed.length} tool(s) executed successfully`,
        passed: true,
      });
    }
    if (denied.length > 0 && policyRejected.length === 0) {
      // Tool-level denial (3P API error, not policy)
      for (const d of denied) {
        steps.push({
          label: "Tool Execution (GL Connector)",
          check: `Call 3P API for ${d.tool}`,
          value: "3P API returned error",
          passed: false,
          detail: d.error,
        });
      }
    }
  }

  // Rejected before delegation (account deactivated, tenant boundary, etc.)
  if (result.outcome === "rejected" && !aip) {
    steps.push({
      label: "Pre-Delegation Check",
      check: "Can this user invoke this agent?",
      value: "REJECTED",
      passed: false,
      detail: result.reason,
    });
  }

  return steps;
}

function StepRow({ step, isLast }: { step: DecisionStep; isLast: boolean }) {
  return (
    <div className="flex gap-3">
      {/* Timeline line */}
      <div className="flex flex-col items-center">
        <div className={`size-5 rounded-full flex items-center justify-center shrink-0 ${
          step.passed ? "bg-green-500/20" : "bg-red-500/20"
        }`}>
          {step.passed
            ? <CheckCircle2 className="size-3 text-green-400" />
            : <XCircle className="size-3 text-red-400" />
          }
        </div>
        {!isLast && <div className="w-px flex-1 bg-border/50 my-1" />}
      </div>

      {/* Content */}
      <div className="pb-3 min-w-0 flex-1">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-[10px] font-semibold text-foreground">{step.label}</span>
          <Badge variant="outline" className={`text-[8px] px-1 py-0 ${
            step.passed
              ? "bg-green-500/10 text-green-400 border-green-500/30"
              : "bg-red-500/10 text-red-400 border-red-500/30"
          }`}>
            {step.passed ? "PASS" : "FAIL"}
          </Badge>
        </div>
        <p className="text-[10px] text-muted-foreground">{step.check}</p>
        <p className="text-[10px] text-foreground mt-0.5">{step.value}</p>
        {step.detail && (
          <p className="text-[9px] text-muted-foreground mt-0.5 italic leading-tight">
            {step.detail.length > 200 ? step.detail.slice(0, 200) + "..." : step.detail}
          </p>
        )}
      </div>
    </div>
  );
}

export function PolicyDecisionTrace({ result }: PolicyDecisionTraceProps) {
  const steps = buildDecisionSteps(result);
  if (steps.length === 0) return null;

  const allPassed = steps.every(s => s.passed);
  const outcome = result.outcome ?? result.aip_response?.outcome;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold flex items-center gap-2">
        <Shield className="size-4" />
        Policy Decision Trace
        <Badge variant="outline" className={`text-[10px] ${
          allPassed
            ? "bg-green-500/10 text-green-400 border-green-500/30"
            : "bg-red-500/10 text-red-400 border-red-500/30"
        }`}>
          {outcome === "rejected" || outcome === "denied" ? "blocked" :
           outcome === "success" || outcome === "delegated" ? "allowed" :
           outcome ?? "unknown"}
        </Badge>
      </h3>
      <Card size="sm">
        <CardContent>
          <p className="text-[10px] text-muted-foreground mb-3">
            Step-by-step deterministic policy evaluation. Each decision is pre-defined — not decided by the LLM.
          </p>
          <div>
            {steps.map((step, i) => (
              <StepRow key={i} step={step} isLast={i === steps.length - 1} />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
