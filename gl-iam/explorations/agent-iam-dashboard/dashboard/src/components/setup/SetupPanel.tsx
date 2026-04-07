import { useState } from "react";
import { CheckCircle2, Loader2, RotateCcw, Play, User, Bot, ChevronDown, ChevronUp, Shield, Wrench, Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ROLE_SCOPES } from "@/lib/role-scopes";
import { AGENT_CONFIGS } from "@/lib/agent-policies";
import type { AgentConfig } from "@/lib/agent-policies";
import type { AppPhase, SetupResult } from "@/lib/types";

interface SetupPanelProps {
  phase: AppPhase;
  setup: () => Promise<void>;
  reset: () => Promise<void>;
  setupResult: SetupResult | null;
  allHealthy: boolean | null;
}

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  member: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  viewer: "bg-gray-500/20 text-gray-300 border-gray-500/30",
};

const AGENT_TYPE_COLORS: Record<string, string> = {
  orchestrator: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  worker: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
  autonomous: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
};

function AgentRow({ agentConfig }: { agentConfig: AgentConfig }) {
  return (
    <Dialog>
      <DialogTrigger className="w-full flex items-center justify-between text-xs bg-muted/30 rounded px-2 py-1.5 hover:bg-muted/50 transition-colors cursor-pointer">
        <span className="text-foreground font-medium truncate">{agentConfig.name}</span>
        <div className="flex items-center gap-1.5 shrink-0">
          <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${AGENT_TYPE_COLORS[agentConfig.type]}`}>
            {agentConfig.type}
          </Badge>
          <Info className="size-3 text-muted-foreground" />
        </div>
      </DialogTrigger>
      <DialogContent className="sm:max-w-4xl max-h-[85vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Bot className="size-5" />
            {agentConfig.name}
            <Badge variant="outline" className={`text-xs ${AGENT_TYPE_COLORS[agentConfig.type]}`}>
              {agentConfig.type}
            </Badge>
            <Badge variant="outline" className="text-xs text-muted-foreground">
              {agentConfig.product}
            </Badge>
          </DialogTitle>
        </DialogHeader>
        <ScrollArea className="max-h-[70vh] pr-4">
          <div className="space-y-5">
            {/* Scope Ceiling */}
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-1.5">
                <Shield className="size-3.5" /> Scope Ceiling ({agentConfig.allowedScopes.length})
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {agentConfig.allowedScopes.map((scope) => (
                  <Badge key={scope} variant="outline" className="text-xs">
                    {scope}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Workers */}
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-1.5">
                <Wrench className="size-3.5" /> Sub-Agent Workers ({agentConfig.workers.length})
              </h4>
              <div className="space-y-3">
                {agentConfig.workers.map((worker) => (
                  <div key={worker.name} className="bg-muted/30 rounded-lg p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <Bot className="size-3.5 text-cyan-400" />
                      <span className="text-sm font-medium">{worker.name}</span>
                      <Badge variant="outline" className="text-[10px] bg-cyan-500/15 text-cyan-300 border-cyan-500/30">
                        worker
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {worker.scopes.map((s) => (
                        <Badge key={s} variant="outline" className="text-xs text-muted-foreground">
                          {s}
                        </Badge>
                      ))}
                    </div>
                    {worker.resourcePolicy && (
                      <div className="mt-2 border-t border-border/50 pt-2">
                        <p className="text-xs text-muted-foreground italic mb-2">{worker.resourcePolicy.description}</p>
                        <div className="space-y-1">
                          {worker.resourcePolicy.rules.map((rule, ri) => (
                            <div key={ri} className="flex items-start gap-2 text-xs">
                              <span className={`shrink-0 ${rule.action === "ALLOW" ? "text-green-400" : "text-red-400"}`}>
                                {rule.action === "ALLOW" ? "✓" : "✗"}
                              </span>
                              <div>
                                <span className="font-medium text-foreground">{rule.condition}</span>
                                <span className="text-muted-foreground"> → {rule.detail}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Resource Constraints */}
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-1.5">
                <Shield className="size-3.5" /> Resource Constraints (in DelegationToken)
              </h4>
              <p className="text-xs text-muted-foreground italic mb-3">
                {agentConfig.resourceConstraints.description}
              </p>
              <div className="space-y-3">
                {Object.entries(agentConfig.resourceConstraints.perRole).map(([role, constraints]) => (
                  <div key={role} className="bg-muted/30 rounded-lg p-3">
                    <Badge variant="outline" className={`text-xs mb-2 ${ROLE_COLORS[role] ?? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"}`}>
                      {role}
                    </Badge>
                    <div className="space-y-1 mt-1">
                      {Object.entries(constraints).map(([key, value]) => (
                        <div key={key} className="text-xs">
                          <code className="text-foreground bg-muted px-1 py-0.5 rounded">{key}</code>
                          <span className="text-muted-foreground ml-2">{value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}

export function SetupPanel({ phase, setup, reset, setupResult, allHealthy }: SetupPanelProps) {
  const isSettingUp = phase === "setting-up";
  const isReady = phase === "ready" || phase === "running";
  const [showDetails, setShowDetails] = useState(false);
  const [expandedUser, setExpandedUser] = useState<string | null>(null);

  // Show only the 3 role archetypes
  const ARCHETYPE_EMAILS = ["onlee@gdplabs.id", "maylina@gdplabs.id", "petry@gdplabs.id", "guest@gdplabs.id"];
  const ARCHETYPE_LABELS: Record<string, string> = {
    "onlee@gdplabs.id": "Pak On",
    "maylina@gdplabs.id": "Maylina",
    "petry@gdplabs.id": "Petry",
    "guest@gdplabs.id": "Guest",
  };
  // Show only orchestrator/autonomous agents (not workers)
  const ORCHESTRATOR_AGENTS = ["scheduling-agent", "de-pm-agent", "weekly-report-agent"];

  const archetypeUsers = setupResult
    ? ARCHETYPE_EMAILS.filter(e => setupResult.users[e] && !setupResult.users[e].error)
    : [];
  const orchAgents = setupResult
    ? ORCHESTRATOR_AGENTS.filter(a => setupResult.agents[a] && !setupResult.agents[a].error)
    : [];

  const userCount = archetypeUsers.length;
  const agentCount = orchAgents.length;

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>Environment</CardTitle>
      </CardHeader>
      <CardContent>
        {isReady && setupResult ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-green-400">
              <CheckCircle2 className="size-4" />
              <span className="text-sm font-medium">Demo initialized</span>
            </div>
            <div className="flex gap-4 text-xs text-muted-foreground">
              <span>{userCount} users</span>
              <span>{agentCount} agents</span>
            </div>

            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {showDetails ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
              {showDetails ? "Hide details" : "Show users & agents"}
            </button>

            {showDetails && (
              <div className="space-y-4 pt-1">
                {/* Users — only archetypes */}
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
                    <User className="size-3" /> Users
                  </h4>
                  <div className="space-y-1">
                    {archetypeUsers.map((email) => {
                      const user = setupResult.users[email]!;
                      const role = user.role ?? "member";
                      const scopes = ROLE_SCOPES[role]?.scopes ?? [];
                      const label = ARCHETYPE_LABELS[email] ?? email.split("@")[0];
                      const isExpanded = expandedUser === email;
                      return (
                        <div key={email} className="text-xs bg-muted/30 rounded overflow-hidden">
                          <button
                            onClick={() => setExpandedUser(isExpanded ? null : email)}
                            className="w-full flex items-center justify-between px-2 py-1.5 hover:bg-muted/50 transition-colors"
                          >
                            <span className="text-foreground truncate">{label}</span>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${ROLE_COLORS[role]}`}>
                                {role}
                              </Badge>
                              {isExpanded ? <ChevronUp className="size-2.5" /> : <ChevronDown className="size-2.5" />}
                            </div>
                          </button>
                          {isExpanded && (
                            <div className="px-2 pb-2 pt-1 border-t border-border/50">
                              <div className="flex items-center gap-1 mb-1.5 text-muted-foreground">
                                <Shield className="size-2.5" />
                                <span className="text-[10px]">Scopes ({scopes.length})</span>
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {scopes.map((scope) => (
                                  <Badge key={scope} variant="outline" className="text-[9px] px-1 py-0 bg-muted/50 text-muted-foreground border-border">
                                    {scope}
                                  </Badge>
                                ))}
                              </div>
                              <p className="text-[10px] text-muted-foreground mt-1.5 italic">
                                {ROLE_SCOPES[role]?.description}
                              </p>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Agents + Workers */}
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
                    <Bot className="size-3" /> Agents & Workers
                  </h4>
                  <div className="space-y-1">
                    {AGENT_CONFIGS.map((agentConfig) => (
                      <AgentRow key={agentConfig.name} agentConfig={agentConfig} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            <Button variant="ghost" size="sm" onClick={reset}>
              <RotateCcw className="size-3.5" />
              Reset
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Set up demo users, agents, and scopes.
            </p>
            <Button
              size="sm"
              onClick={setup}
              disabled={!allHealthy || isSettingUp}
            >
              {isSettingUp ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Play className="size-3.5" />
              )}
              {isSettingUp ? "Initializing..." : "Initialize Demo"}
            </Button>
            {!allHealthy && (
              <p className="text-xs text-amber-400">
                Waiting for all services to be healthy...
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
