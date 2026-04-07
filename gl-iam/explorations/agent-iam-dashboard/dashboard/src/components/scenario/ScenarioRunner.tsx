import { Loader2, Play } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { AppPhase, ScenarioRunResult, ScenariosByProduct, ScenarioMeta } from "@/lib/types";

interface ScenarioRunnerProps {
  currentScenario: string | null;
  scenarios: ScenariosByProduct | null;
  onRun: (id: string) => Promise<void>;
  phase: AppPhase;
  currentResult: ScenarioRunResult | null;
}

function findScenario(scenarios: ScenariosByProduct, id: string): ScenarioMeta | null {
  for (const group of Object.values(scenarios)) {
    const found = group.find((s: ScenarioMeta) => s.id === id);
    if (found) return found;
  }
  return null;
}

function outcomeBadge(outcome: string | undefined) {
  if (!outcome) return null;
  const cls =
    outcome === "success" || outcome === "full_access"
      ? "bg-green-500/15 text-green-400 border-green-500/30"
      : outcome === "partial" || outcome === "partial_access"
        ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
        : outcome === "denied" || outcome === "rejected" || outcome === "blocked"
          ? "bg-red-500/15 text-red-400 border-red-500/30"
          : "bg-blue-500/15 text-blue-400 border-blue-500/30";
  return (
    <Badge variant="outline" className={cn("text-xs", cls)}>
      {outcome}
    </Badge>
  );
}

export function ScenarioRunner({
  currentScenario,
  scenarios,
  onRun,
  phase,
  currentResult,
}: ScenarioRunnerProps) {
  const isRunning = phase === "running";
  const meta = currentScenario && scenarios ? findScenario(scenarios, currentScenario) : null;

  if (!meta) {
    return (
      <Card size="sm">
        <CardHeader>
          <CardTitle>Run Scenario</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            Select a scenario from the list to run it.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Run Scenario
          <Badge variant="outline" className="font-mono text-[10px]">
            {meta.id}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <p className="text-sm font-medium">{meta.title}</p>
          <p className="mt-1 text-xs text-muted-foreground">{meta.description}</p>
        </div>
        <div className="flex flex-wrap gap-1">
          {meta.concepts.map((c) => (
            <Badge key={c} variant="secondary" className="text-[10px]">
              {c}
            </Badge>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            onClick={() => currentScenario && onRun(currentScenario)}
            disabled={isRunning}
          >
            {isRunning ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Play className="size-3.5" />
            )}
            {isRunning ? "Running..." : "Run Scenario"}
          </Button>
          {currentResult && outcomeBadge(currentResult.outcome)}
        </div>
      </CardContent>
    </Card>
  );
}
