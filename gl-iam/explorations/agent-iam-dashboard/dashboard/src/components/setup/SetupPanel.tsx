import { useState } from "react";
import { CheckCircle2, Loader2, RotateCcw, Play, User, Bot, ChevronDown, ChevronUp, Shield, Key } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ROLE_SCOPES, AGENT_CREDENTIAL_POLICIES } from "@/lib/role-scopes";
import type { CredentialSource } from "@/lib/role-scopes";
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

function CredentialSourceIcon({ source }: { source: CredentialSource }) {
  if (source === "user") {
    return <span className="inline-flex items-center gap-0.5 text-blue-400"><User className="size-2" />U</span>;
  }
  if (source === "agent") {
    return <span className="inline-flex items-center gap-0.5 text-amber-400"><Bot className="size-2" />A</span>;
  }
  return <span className="inline-flex items-center gap-0.5 text-emerald-400"><User className="size-2" />U*</span>;
}

export function SetupPanel({ phase, setup, reset, setupResult, allHealthy }: SetupPanelProps) {
  const isSettingUp = phase === "setting-up";
  const isReady = phase === "ready" || phase === "running";
  const [showDetails, setShowDetails] = useState(false);
  const [expandedUser, setExpandedUser] = useState<string | null>(null);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

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
                  <div className="space-y-1">
                    {Object.entries(setupResult.users)
                      .filter(([, u]) => !u.error && !u.skipped)
                      .map(([email, user]) => {
                        const role = user.role ?? "member";
                        const scopes = ROLE_SCOPES[role]?.scopes ?? [];
                        const isExpanded = expandedUser === email;
                        return (
                          <div key={email} className="text-xs bg-muted/30 rounded overflow-hidden">
                            <button
                              onClick={() => setExpandedUser(isExpanded ? null : email)}
                              className="w-full flex items-center justify-between px-2 py-1.5 hover:bg-muted/50 transition-colors"
                            >
                              <div className="flex items-center gap-1.5 truncate">
                                <span className="text-foreground truncate">{email.split("@")[0]}</span>
                                <span className="text-muted-foreground">@{email.split("@")[1]}</span>
                              </div>
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
                    {/* Deactivated users */}
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
                  <div className="space-y-1">
                    {Object.entries(setupResult.agents)
                      .filter(([, a]) => !a.error)
                      .map(([name, agent]) => {
                        const agentType = agent.type ?? "orchestrator";
                        const isExpanded = expandedAgent === name;
                        return (
                          <div key={name} className="text-xs bg-muted/30 rounded overflow-hidden">
                            <button
                              onClick={() => setExpandedAgent(isExpanded ? null : name)}
                              className="w-full flex items-center justify-between px-2 py-1.5 hover:bg-muted/50 transition-colors"
                            >
                              <span className="text-foreground font-medium truncate">{name}</span>
                              <div className="flex items-center gap-1.5 shrink-0">
                                <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${AGENT_TYPE_COLORS[agentType]}`}>
                                  {agentType}
                                </Badge>
                                {isExpanded ? <ChevronUp className="size-2.5" /> : <ChevronDown className="size-2.5" />}
                              </div>
                            </button>
                            {isExpanded && (
                              <div className="px-2 pb-2 pt-1 border-t border-border/50 space-y-3">
                                {/* Scope ceiling */}
                                <div>
                                  <div className="flex items-center gap-1 mb-1.5 text-muted-foreground">
                                    <Shield className="size-2.5" />
                                    <span className="text-[10px]">Scope Ceiling ({(agent.allowed_scopes ?? []).length})</span>
                                  </div>
                                  <div className="flex flex-wrap gap-1">
                                    {(agent.allowed_scopes ?? []).map((scope: string) => (
                                      <Badge key={scope} variant="outline" className="text-[9px] px-1 py-0 bg-muted/50 text-muted-foreground border-border">
                                        {scope}
                                      </Badge>
                                    ))}
                                  </div>
                                </div>

                                {/* Credential routing policy per role */}
                                {AGENT_CREDENTIAL_POLICIES[name] && (
                                  <div>
                                    <div className="flex items-center gap-1 mb-1.5 text-muted-foreground">
                                      <Key className="size-2.5" />
                                      <span className="text-[10px]">Credential Routing Policy</span>
                                    </div>
                                    <div className="space-y-2">
                                      {Object.entries(AGENT_CREDENTIAL_POLICIES[name]!.rules).map(([role, scopes]) => (
                                        <div key={role}>
                                          <div className="flex items-center gap-1 mb-1">
                                            <Badge variant="outline" className={`text-[9px] px-1 py-0 ${ROLE_COLORS[role] ?? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"}`}>
                                              {role}
                                            </Badge>
                                          </div>
                                          <div className="space-y-0.5 ml-1">
                                            {Object.entries(scopes).map(([scope, rule]) => (
                                              <div key={scope} className="flex items-center gap-1.5 text-[9px]">
                                                <CredentialSourceIcon source={rule.source} />
                                                <span className="font-mono text-muted-foreground">{scope}</span>
                                                <span className="text-muted-foreground/60 truncate">— {rule.reason}</span>
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
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
