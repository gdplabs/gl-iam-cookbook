import { motion } from "framer-motion";
import { User, Bot, Wrench, ChevronRight, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ScenarioRunResult, DelegationChainEntry, BlockedTool } from "@/lib/types";

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
    return (
      <Card size="sm">
        <CardContent>
          <p className="text-xs text-muted-foreground">
            No delegation chain data. Run a scenario first.
          </p>
        </CardContent>
      </Card>
    );
  }

  const groups = parseNodes(aip.delegation_chain);
  const blockedTools = aip.blocked_tools ?? [];

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">Delegation Flow</h3>
      <div className="grid grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] items-start gap-2">
        {/* d1 - User */}
        <div className="space-y-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {depthLabel(1)}
          </div>
          {(groups[1] ?? []).map((n, i) => (
            <FlowCard key={`d1-${i}`} node={n} index={i} />
          ))}
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
          {blockedTools.map((bt, i) => (
            <BlockedToolCard key={`blocked-${i}`} tool={bt} index={i} />
          ))}
        </div>
      </div>
    </div>
  );
}
