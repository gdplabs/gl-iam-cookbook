import { useState } from "react";
import { Bot, Shield, Wrench, ChevronDown, ChevronUp, Settings, Layers } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AGENT_CONFIGS } from "@/lib/agent-policies";

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  member: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  viewer: "bg-gray-500/20 text-gray-300 border-gray-500/30",
  autonomous: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
};

const LAYER_COLORS = {
  gliam: "bg-violet-500/10 border-violet-500/20 text-violet-300",
  aip: "bg-purple-500/10 border-purple-500/20 text-purple-300",
  de: "bg-cyan-500/10 border-cyan-500/20 text-cyan-300",
};

interface AgentConfigPanelProps {
  agentName?: string;
}

export function AgentConfigPanel({ agentName }: AgentConfigPanelProps) {
  const [expanded, setExpanded] = useState(true);

  const config = agentName
    ? AGENT_CONFIGS.find(c => agentName.includes(c.name))
    : null;

  if (!config) return null;

  return (
    <div className="space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm font-semibold hover:text-foreground transition-colors w-full"
      >
        <Settings className="size-4" />
        Agent Static Config
        <Badge variant="outline" className="text-[10px] ml-1 bg-amber-500/15 text-amber-300 border-amber-500/30">
          {config.name}
        </Badge>
        {expanded ? <ChevronUp className="size-3.5 ml-auto" /> : <ChevronDown className="size-3.5 ml-auto" />}
      </button>

      {expanded && (
        <Card size="sm">
          <CardContent>
            {/* Layer legend */}
            <div className="flex items-center gap-3 mb-4 text-[9px]">
              <Layers className="size-3 text-muted-foreground" />
              <span className="text-muted-foreground">Responsibility:</span>
              <Badge variant="outline" className={`text-[8px] px-1.5 py-0 ${LAYER_COLORS.gliam}`}>GL-IAM SDK</Badge>
              <span className="text-muted-foreground/50">provides token</span>
              <Badge variant="outline" className={`text-[8px] px-1.5 py-0 ${LAYER_COLORS.aip}`}>AIP Platform</Badge>
              <span className="text-muted-foreground/50">provides hooks</span>
              <Badge variant="outline" className={`text-[8px] px-1.5 py-0 ${LAYER_COLORS.de}`}>DE / Agent Code</Badge>
              <span className="text-muted-foreground/50">implements logic</span>
            </div>

            <div className="space-y-5">
              {/* Scope Ceiling — set by Platform Admin, enforced by AIP */}
              <LayeredSection
                layer="aip"
                layerLabel="AIP auto-enforces"
                icon={<Shield className="size-3.5" />}
                title={`Scope Ceiling (${config.allowedScopes.length} tools)`}
                description="Set at agent registration. AIP automatically removes tools not in this list from the LLM's available set."
              >
                <div className="flex flex-wrap gap-1.5">
                  {config.allowedScopes.map((scope) => (
                    <Badge key={scope} variant="outline" className="text-[10px] font-mono">
                      {scope}
                    </Badge>
                  ))}
                </div>
              </LayeredSection>

              {/* Workers — defined by Agent Developer */}
              <LayeredSection
                layer="de"
                layerLabel="DE implements"
                icon={<Wrench className="size-3.5" />}
                title={`Sub-Agent Workers (${config.workers.length})`}
                description="Agent developer defines workers and their policy guard rails. AIP provides the DelegationToolManager hook."
              >
                <div className="space-y-2">
                  {config.workers.map((worker) => (
                    <div key={worker.name} className="bg-muted/20 rounded-lg p-2.5">
                      <div className="flex items-center gap-2 mb-1.5">
                        <Bot className="size-3 text-cyan-400" />
                        <span className="text-xs font-medium">{worker.name}</span>
                        <Badge variant="outline" className="text-[9px] bg-cyan-500/15 text-cyan-300 border-cyan-500/30">
                          worker
                        </Badge>
                      </div>
                      <div className="flex flex-wrap gap-1 mb-1.5">
                        {worker.scopes.map((s) => (
                          <Badge key={s} variant="outline" className="text-[9px] font-mono text-muted-foreground">
                            {s}
                          </Badge>
                        ))}
                      </div>
                      {worker.resourcePolicy && (
                        <div className="border-t border-border/30 pt-1.5 mt-1.5">
                          <div className="flex items-center gap-1 mb-1">
                            <Badge variant="outline" className={`text-[8px] px-1 py-0 ${LAYER_COLORS.de}`}>DE implements</Badge>
                            <span className="text-[9px] text-muted-foreground italic">{worker.resourcePolicy.description}</span>
                          </div>
                          <div className="space-y-0.5">
                            {worker.resourcePolicy.rules.map((rule, i) => (
                              <div key={i} className="flex items-start gap-1.5 text-[10px]">
                                <span className={`shrink-0 mt-0.5 ${rule.action === "ALLOW" ? "text-green-400" : "text-red-400"}`}>
                                  {rule.action === "ALLOW" ? "✓" : "✗"}
                                </span>
                                <span>
                                  <span className="font-medium text-foreground">{rule.condition}</span>
                                  <span className="text-muted-foreground"> → {rule.detail}</span>
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </LayeredSection>

              {/* Resource Constraints — GL-IAM carries, DE enforces */}
              <LayeredSection
                layer="gliam"
                layerLabel="GL-IAM carries in token"
                icon={<Shield className="size-3.5" />}
                title="Resource Constraint Templates"
                description="GL-IAM embeds these values in the DelegationToken (per-user, dynamic). DE reads them and enforces in guard rails."
              >
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="outline" className={`text-[8px] px-1 py-0 ${LAYER_COLORS.gliam}`}>GL-IAM</Badge>
                  <span className="text-[9px] text-muted-foreground">fills values at delegation time (dynamic per user + role)</span>
                </div>
                <div className="flex items-center gap-2 mb-3">
                  <Badge variant="outline" className={`text-[8px] px-1 py-0 ${LAYER_COLORS.de}`}>DE</Badge>
                  <span className="text-[9px] text-muted-foreground">reads from token and enforces in before_tool_call()</span>
                </div>
                <p className="text-[10px] text-muted-foreground italic mb-2">
                  {config.resourceConstraints.description}
                </p>
                <div className="space-y-2">
                  {Object.entries(config.resourceConstraints.perRole).map(([role, constraints]) => (
                    <div key={role} className="bg-muted/20 rounded-lg p-2.5">
                      <Badge variant="outline" className={`text-[10px] mb-1.5 ${ROLE_COLORS[role] ?? ""}`}>
                        {role}
                      </Badge>
                      <div className="space-y-1">
                        {Object.entries(constraints).map(([key, value]) => (
                          <div key={key} className="text-[10px]">
                            <code className="text-foreground bg-muted px-1 py-0.5 rounded text-[9px]">{key}</code>
                            <span className="text-muted-foreground ml-1.5">{value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </LayeredSection>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function LayeredSection({ layer, layerLabel, icon, title, description, children }: {
  layer: "gliam" | "aip" | "de";
  layerLabel: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <h4 className="text-xs font-medium flex items-center gap-1.5 text-muted-foreground">
          {icon} {title}
        </h4>
        <Badge variant="outline" className={`text-[8px] px-1.5 py-0 ml-auto ${LAYER_COLORS[layer]}`}>
          {layerLabel}
        </Badge>
      </div>
      <p className="text-[9px] text-muted-foreground italic mb-2">{description}</p>
      {children}
    </div>
  );
}
