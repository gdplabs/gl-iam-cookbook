import { User, Bot, MessageSquare } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { getHypotheticalResponse } from "@/lib/hypothetical-responses";
import type { ScenarioRunResult } from "@/lib/types";

interface ChatSimulationProps {
  result: ScenarioRunResult;
}

export function ChatSimulation({ result }: ChatSimulationProps) {
  const scenarioId = result.scenario_id ?? "";
  const userMessage = result.aip_response?.user_message ?? result.scenario?.title ?? "";
  const userName = result.user?.email?.split("@")[0] ?? "System";
  const userRole = result.user?.role;
  const agentName = result.scenario?.product === "aip"
    ? "Weekly Report Agent"
    : result.scenario?.product === "de"
      ? "DE PM Agent"
      : "Scheduling Agent";
  const response = getHypotheticalResponse(scenarioId);
  const outcome = result.outcome ?? result.aip_response?.outcome;

  const outcomeColor =
    outcome === "success" || outcome === "delegated"
      ? "text-green-400"
      : outcome === "partial_success" || outcome === "success_with_warning"
        ? "text-amber-400"
        : outcome === "rejected"
          ? "text-red-400"
          : "text-blue-400";

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold flex items-center gap-2">
        <MessageSquare className="size-4" />
        Chat Simulation
        {outcome && (
          <Badge variant="outline" className={`text-[10px] ${outcomeColor} border-current/30`}>
            {outcome}
          </Badge>
        )}
      </h3>
      <Card size="sm">
        <CardContent className="space-y-3 pt-1">
          {/* User message */}
          {result.user !== null && (
            <div className="flex gap-3">
              <div className="shrink-0 mt-0.5">
                <div className="size-7 rounded-full bg-blue-500/20 flex items-center justify-center">
                  <User className="size-3.5 text-blue-400" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-foreground">{userName}</span>
                  {userRole && (
                    <Badge variant="outline" className="text-[9px] px-1 py-0 text-muted-foreground">
                      {userRole}
                    </Badge>
                  )}
                </div>
                <div className="rounded-lg bg-blue-500/10 border border-blue-500/20 px-3 py-2">
                  <p className="text-xs text-foreground">{userMessage}</p>
                </div>
              </div>
            </div>
          )}

          {/* Autonomous trigger (no user) */}
          {result.user === null && (
            <div className="flex gap-3">
              <div className="shrink-0 mt-0.5">
                <div className="size-7 rounded-full bg-emerald-500/20 flex items-center justify-center">
                  <Bot className="size-3.5 text-emerald-400" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-foreground">System (CronJob)</span>
                  <Badge variant="outline" className="text-[9px] px-1 py-0 text-emerald-400 border-emerald-500/30">
                    autonomous
                  </Badge>
                </div>
                <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-3 py-2">
                  <p className="text-xs text-foreground">{userMessage}</p>
                </div>
              </div>
            </div>
          )}

          {/* Agent response */}
          <div className="flex gap-3">
            <div className="shrink-0 mt-0.5">
              <div className="size-7 rounded-full bg-amber-500/20 flex items-center justify-center">
                <Bot className="size-3.5 text-amber-400" />
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-medium text-foreground">{agentName}</span>
                <Badge variant="outline" className="text-[9px] px-1 py-0 text-amber-400 border-amber-500/30">
                  agent
                </Badge>
              </div>
              <div className={`rounded-lg border px-3 py-2 ${
                outcome === "rejected"
                  ? "bg-red-500/5 border-red-500/20"
                  : outcome === "partial_success" || outcome === "success_with_warning"
                    ? "bg-amber-500/5 border-amber-500/20"
                    : "bg-muted/30 border-border"
              }`}>
                <div className="text-xs text-foreground whitespace-pre-line leading-relaxed prose-sm">
                  {response.split("\n").map((line, i) => {
                    // Simple markdown-like rendering
                    if (line.startsWith("**") && line.endsWith("**")) {
                      return <p key={i} className="font-semibold">{line.replace(/\*\*/g, "")}</p>;
                    }
                    if (line.startsWith("- ")) {
                      const content = line.slice(2);
                      return (
                        <p key={i} className="pl-2">
                          <span className="text-muted-foreground">•</span>{" "}
                          {renderBold(content)}
                        </p>
                      );
                    }
                    if (line.match(/^\d+\. /)) {
                      return <p key={i} className="pl-2">{renderBold(line)}</p>;
                    }
                    if (line.startsWith("_") && line.endsWith("_")) {
                      return <p key={i} className="italic text-muted-foreground">{line.replace(/_/g, "")}</p>;
                    }
                    if (line === "") return <br key={i} />;
                    return <p key={i}>{renderBold(line)}</p>;
                  })}
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/** Render **bold** text within a line */
function renderBold(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}
