import { motion } from "framer-motion";
import { User, Bot, Wrench, ChevronRight, XCircle, Shield, Building2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ScenarioRunResult, DelegationChainEntry, BlockedTool, ExecutionLogEntry } from "@/lib/types";

interface DelegationFlowProps {
  result: ScenarioRunResult;
}

interface FlowNode {
  depth: number;
  label: string;
  scopes: string[];
  token?: string;
  agentId?: string;
  worker?: string;
  execOrder?: number;
}

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  member: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  viewer: "bg-gray-500/20 text-gray-300 border-gray-500/30",
};

const USER_LABELS: Record<string, string> = {
  "onlee": "Pak On",
  "maylina": "Maylina",
  "sandy": "Sandy",
  "petry": "Petry",
  "guest": "Guest",
};

/** Sort tools: directory.lookup first, then calendar, then others */
function sortToolNodes(nodes: FlowNode[]): FlowNode[] {
  const priority: Record<string, number> = {
    "directory.lookup": 0,
    "calendar.list_events": 1,
    "calendar.create_event": 2,
  };
  return [...nodes].sort((a, b) => {
    const pa = priority[a.label] ?? 10;
    const pb = priority[b.label] ?? 10;
    return pa - pb;
  });
}

/** Sort workers: directory-worker first */
function sortWorkerNodes(nodes: FlowNode[]): FlowNode[] {
  const priority: Record<string, number> = {
    "directory-worker": 0,
    "calendar-worker": 1,
    "comms-worker": 2,
  };
  return [...nodes].sort((a, b) => {
    const pa = priority[a.label] ?? 10;
    const pb = priority[b.label] ?? 10;
    return pa - pb;
  });
}

function parseNodes(chain: DelegationChainEntry[]): Record<number, FlowNode[]> {
  const groups: Record<number, FlowNode[]> = { 1: [], 2: [], 3: [], 4: [] };
  for (const entry of chain) {
    const d = entry.depth;
    if (d < 1 || d > 4) continue;
    const existing = groups[d] ?? [];
    existing.push({
      depth: d,
      label: entry.label,
      scopes: entry.scopes ?? (entry.scope ? [entry.scope] : []),
      token: entry.token,
      agentId: entry.agent_id,
      worker: entry.worker,
    });
    groups[d] = existing;
  }
  // Sort workers and tools
  groups[3] = sortWorkerNodes(groups[3] ?? []);
  groups[4] = sortToolNodes(groups[4] ?? []);
  // Assign execution order numbers
  let order = 1;
  for (const node of groups[4]) {
    node.execOrder = order++;
  }
  return groups;
}

function depthColor(depth: number): string {
  switch (depth) {
    case 1: return "bg-blue-500/20 text-blue-400 border-blue-500/30";
    case 2: return "bg-purple-500/20 text-purple-400 border-purple-500/30";
    case 3: return "bg-amber-500/20 text-amber-400 border-amber-500/30";
    case 4: return "bg-green-500/20 text-green-400 border-green-500/30";
    default: return "bg-muted text-muted-foreground";
  }
}

function depthLabel(depth: number): string {
  switch (depth) {
    case 1: return "User";
    case 2: return "Orchestrator";
    case 3: return "Worker";
    case 4: return "Tool";
    default: return `d${depth}`;
  }
}

function DepthIcon({ depth }: { depth: number }) {
  switch (depth) {
    case 1: return <User className="size-4" />;
    case 2: return <Bot className="size-4" />;
    case 3: return <Bot className="size-3.5" />;
    case 4: return <Wrench className="size-3.5" />;
    default: return null;
  }
}

function FlowCard({ node, index }: { node: FlowNode; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: node.depth * 0.15 + index * 0.05 }}
    >
      <Card size="sm" className="border-border/50">
        <CardContent className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={cn("text-[10px]", depthColor(node.depth))}>
              d{node.depth}
            </Badge>
            {node.execOrder && (
              <Badge variant="outline" className="text-[10px] bg-foreground/10 text-foreground border-foreground/20 font-mono">
                #{node.execOrder}
              </Badge>
            )}
            <DepthIcon depth={node.depth} />
            <span className="text-xs font-medium">{node.label}</span>
          </div>
          {node.scopes.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {node.scopes.map((s) => (
                <Badge key={s} variant="secondary" className="text-[10px]">
                  {s}
                </Badge>
              ))}
            </div>
          )}
          {node.worker && (
            <span className="text-[10px] text-muted-foreground">worker: {node.worker}</span>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}

function UserCard({ result }: { result: ScenarioRunResult }) {
  const user = result.user;
  const abac = result.abac;

  if (!user) {
    // Autonomous agent
    return (
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
      >
        <Card size="sm" className="border-emerald-500/30 bg-emerald-500/5">
          <CardContent className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px] bg-blue-500/20 text-blue-400 border-blue-500/30">
                d1
              </Badge>
              <Bot className="size-4 text-emerald-400" />
              <span className="text-xs font-medium">System (CronJob)</span>
            </div>
            <Badge variant="outline" className="text-[9px] bg-emerald-500/15 text-emerald-300 border-emerald-500/30">
              autonomous
            </Badge>
          </CardContent>
        </Card>
      </motion.div>
    );
  }

  const emailPrefix = user.email?.split("@")[0] ?? "";
  const displayName = USER_LABELS[emailPrefix] ?? emailPrefix;
  const role = user.role ?? "member";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.1 }}
    >
      <Card size="sm" className="border-blue-500/30 bg-blue-500/5">
        <CardContent className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-[10px] bg-blue-500/20 text-blue-400 border-blue-500/30">
              d1
            </Badge>
            <User className="size-4 text-blue-400" />
            <span className="text-xs font-medium">{displayName}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Badge variant="outline" className={cn("text-[9px] px-1.5 py-0", ROLE_COLORS[role])}>
              {role}
            </Badge>
            {user.email && (
              <span className="text-[9px] text-muted-foreground">{user.email}</span>
            )}
          </div>
          {abac && (
            <div className="space-y-1">
              <div className="flex items-center gap-1 text-[9px] text-muted-foreground">
                <Shield className="size-2.5" />
                <span>{abac.attenuated_scopes.length} scopes delegated</span>
              </div>
              {user.role === "admin" && (
                <div className="flex items-center gap-1 text-[9px] text-muted-foreground">
                  <Building2 className="size-2.5" />
                  <span>Multi-org access</span>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}

function BlockedToolCard({ tool, index }: { tool: BlockedTool; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 4 * 0.15 + index * 0.05 }}
    >
      <Card size="sm" className="border-red-500/30 bg-red-500/5">
        <CardContent>
          <div className="flex items-center gap-2">
            <XCircle className="size-3.5 text-red-400" />
            <span className="text-xs font-medium text-red-400">{tool.tool}</span>
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">
            missing: {tool.missing_scope}
          </p>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function PolicyRejectedCard({ entry, index }: { entry: ExecutionLogEntry; index: number }) {
  // Extract tool name from step like "d3:calendar-worker→calendar.list_events"
  const toolName = entry.step.includes("→")
    ? entry.step.split("→")[1]
    : entry.step.split(":").slice(1).join(":");

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 4 * 0.15 + index * 0.05 }}
    >
      <Card size="sm" className="border-red-500/30 bg-red-500/5">
        <CardContent className="space-y-1.5">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-[10px] bg-red-500/20 text-red-400 border-red-500/30">
              d3
            </Badge>
            <Shield className="size-3 text-red-400" />
            <span className="text-xs font-medium text-red-400">{toolName}</span>
          </div>
          <div className="flex items-center gap-1 text-[9px] text-amber-400">
            <Bot className="size-2.5" />
            <span>Rejected by agent worker policy</span>
          </div>
          {entry.error && (
            <p className="text-[9px] text-red-400/80 leading-tight">
              {entry.error.length > 120 ? entry.error.slice(0, 120) + "..." : entry.error}
            </p>
          )}
          {entry.worker && (
            <span className="text-[9px] text-muted-foreground">worker: {entry.worker}</span>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}

function Arrow() {
  return (
    <div className="flex items-center justify-center">
      <ChevronRight className="size-5 text-muted-foreground/50" />
    </div>
  );
}

export function DelegationFlow({ result }: DelegationFlowProps) {
  const aip = result.aip_response;
  if (!aip || aip.delegation_chain.length === 0) {
    // Show rejected state if no delegation chain
    if (result.outcome === "rejected") {
      return (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">Delegation Flow</h3>
          <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-2">
            <div className="space-y-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">User</div>
              <UserCard result={result} />
            </div>
            <Arrow />
            <div className="space-y-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Result</div>
              <Card size="sm" className="border-red-500/30 bg-red-500/5">
                <CardContent>
                  <div className="flex items-center gap-2">
                    <XCircle className="size-3.5 text-red-400" />
                    <span className="text-xs font-medium text-red-400">Rejected</span>
                  </div>
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {result.reason ?? "Delegation denied"}
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      );
    }
    return null;
  }

  const groups = parseNodes(aip.delegation_chain);
  const blockedTools = aip.blocked_tools ?? [];
  // Extract policy-rejected tool calls from execution log
  const policyRejected = (aip.execution_log ?? []).filter(
    (e) => e.status === "policy_rejected"
  );

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">Delegation Flow</h3>
      <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] items-start gap-2">
        {/* d1 - User */}
        <div className="space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {depthLabel(1)}
          </div>
          <UserCard result={result} />
        </div>

        <Arrow />

        {/* d2 - Orchestrator */}
        <div className="space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {depthLabel(2)}
          </div>
          {(groups[2] ?? []).map((n, i) => (
            <FlowCard key={`d2-${i}`} node={n} index={i} />
          ))}
        </div>

        <Arrow />

        {/* d3 - Workers */}
        <div className="space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {depthLabel(3)}
          </div>
          {(groups[3] ?? []).map((n, i) => (
            <FlowCard key={`d3-${i}`} node={n} index={i} />
          ))}
        </div>

        <Arrow />

        {/* d4 - Tools */}
        <div className="space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {depthLabel(4)}
          </div>
          {(groups[4] ?? []).map((n, i) => (
            <FlowCard key={`d4-${i}`} node={n} index={i} />
          ))}
          {policyRejected.map((pr, i) => (
            <PolicyRejectedCard key={`policy-${i}`} entry={pr} index={i} />
          ))}
          {blockedTools.map((bt, i) => (
            <BlockedToolCard key={`blocked-${i}`} tool={bt} index={i} />
          ))}
        </div>
      </div>
    </div>
  );
}
