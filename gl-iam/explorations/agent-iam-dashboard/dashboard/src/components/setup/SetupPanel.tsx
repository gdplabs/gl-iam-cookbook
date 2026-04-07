import { useState } from "react";
import { CheckCircle2, Loader2, RotateCcw, Play, User, Bot, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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

export function SetupPanel({ phase, setup, reset, setupResult, allHealthy }: SetupPanelProps) {
  const isSettingUp = phase === "setting-up";
  const isReady = phase === "ready" || phase === "running";
  const [showDetails, setShowDetails] = useState(false);

  const userCount = setupResult ? Object.values(setupResult.users).filter(u => !u.error && !u.skipped).length : 0;
  const agentCount = setupResult ? Object.values(setupResult.agents).filter(a => !a.error).length : 0;

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

            {/* Toggle details */}
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {showDetails ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
              {showDetails ? "Hide details" : "Show users & agents"}
            </button>

            {showDetails && (
              <div className="space-y-4 pt-1">
                {/* Users */}
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
                    <User className="size-3" /> Users
                  </h4>
                  <div className="space-y-1.5">
                    {Object.entries(setupResult.users)
                      .filter(([, u]) => !u.error && !u.skipped)
                      .map(([email, user]) => (
                        <div key={email} className="flex items-center justify-between text-xs bg-muted/30 rounded px-2 py-1.5">
                          <span className="text-foreground truncate mr-2">{email.split("@")[0]}</span>
                          <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${ROLE_COLORS[user.role ?? "member"]}`}>
                            {user.role ?? "member"}
                          </Badge>
                        </div>
                      ))}
                    {/* Show deactivated users */}
                    {Object.entries(setupResult.users)
                      .filter(([, u]) => u.skipped)
                      .map(([email]) => (
                        <div key={email} className="flex items-center justify-between text-xs bg-muted/30 rounded px-2 py-1.5 opacity-50">
                          <span className="text-foreground truncate mr-2 line-through">{email.split("@")[0]}</span>
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-red-500/20 text-red-300 border-red-500/30">
                            deactivated
                          </Badge>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Agents */}
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
                    <Bot className="size-3" /> Agents
                  </h4>
                  <div className="space-y-2">
                    {Object.entries(setupResult.agents)
                      .filter(([, a]) => !a.error)
                      .map(([name, agent]) => (
                        <div key={name} className="text-xs bg-muted/30 rounded px-2 py-1.5 space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="text-foreground font-medium">{name}</span>
                            <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${AGENT_TYPE_COLORS[agent.type ?? "orchestrator"]}`}>
                              {agent.type ?? "orchestrator"}
                            </Badge>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {(agent.allowed_scopes ?? []).map((scope: string) => (
                              <Badge key={scope} variant="outline" className="text-[9px] px-1 py-0 bg-muted/50 text-muted-foreground border-border">
                                {scope}
                              </Badge>
                            ))}
                          </div>
                        </div>
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
