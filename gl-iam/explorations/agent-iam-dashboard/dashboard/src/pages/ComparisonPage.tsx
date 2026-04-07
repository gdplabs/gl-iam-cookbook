import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DelegationFlow } from "@/components/delegation/DelegationFlow";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ScenarioRunResult, ScenariosByProduct, ScenarioMeta } from "@/lib/types";

interface ComparisonPageProps {
  results: Record<string, ScenarioRunResult>;
  scenarios: ScenariosByProduct | null;
}

function findScenario(scenarios: ScenariosByProduct, id: string): ScenarioMeta | null {
  for (const group of Object.values(scenarios)) {
    const found = group.find((s: ScenarioMeta) => s.id === id);
    if (found) return found;
  }
  return null;
}

function outcomeBadgeClass(outcome: string | undefined): string {
  switch (outcome) {
    case "success":
    case "full_access":
      return "bg-green-500/15 text-green-400 border-green-500/30";
    case "partial":
    case "partial_access":
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "denied":
    case "rejected":
    case "blocked":
      return "bg-red-500/15 text-red-400 border-red-500/30";
    default:
      return "bg-blue-500/15 text-blue-400 border-blue-500/30";
  }
}

export function ComparisonPage({ results, scenarios }: ComparisonPageProps) {
  const entries = Object.entries(results);

  if (entries.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center pt-4">
        <p className="text-sm text-muted-foreground">
          Run multiple scenarios to compare results side by side.
        </p>
      </div>
    );
  }

  return (
    <div className="pt-4">
      <ScrollArea className="h-[calc(100vh-120px)]">
        <div
          className={cn(
            "grid gap-4",
            entries.length === 1 && "grid-cols-1",
            entries.length === 2 && "grid-cols-2",
            entries.length >= 3 && "grid-cols-3"
          )}
        >
          {entries.map(([scenarioId, result]) => {
            const meta = scenarios ? findScenario(scenarios, scenarioId) : null;
            return (
              <Card key={scenarioId}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {scenarioId}
                    </Badge>
                    <span className="truncate">{meta?.title ?? scenarioId}</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Outcome */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Outcome:</span>
                    <Badge
                      variant="outline"
                      className={cn("text-[10px]", outcomeBadgeClass(result.outcome))}
                    >
                      {result.outcome ?? "unknown"}
                    </Badge>
                  </div>

                  {/* User info */}
                  {result.user && (
                    <div className="text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">{result.user.email}</span>
                      {" "}({result.user.role})
                    </div>
                  )}

                  {/* Effective scopes */}
                  {result.aip_response && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-medium text-muted-foreground">
                        Effective scopes
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {result.aip_response.effective_scopes.map((s) => (
                          <Badge key={s} variant="secondary" className="text-[10px]">
                            {s}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Mini delegation flow */}
                  {result.aip_response &&
                    result.aip_response.delegation_chain.length > 0 && (
                      <div className="rounded-md border border-border/50 p-2">
                        <DelegationFlow result={result} />
                      </div>
                    )}

                  {/* Tool results summary */}
                  {result.aip_response &&
                    result.aip_response.tool_results.length > 0 && (
                      <div className="space-y-1">
                        <span className="text-[10px] font-medium text-muted-foreground">
                          Tools
                        </span>
                        {result.aip_response.tool_results.map((tr, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs">
                            <span className={cn(
                              "size-1.5 rounded-full",
                              tr.status === "executed" || tr.status === "success"
                                ? "bg-green-400"
                                : tr.status === "denied" || tr.status === "blocked"
                                  ? "bg-red-400"
                                  : "bg-amber-400"
                            )} />
                            <span>{tr.tool}</span>
                            <span className="text-muted-foreground">{tr.status}</span>
                          </div>
                        ))}
                      </div>
                    )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}
