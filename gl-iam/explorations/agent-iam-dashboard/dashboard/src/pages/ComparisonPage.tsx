import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ScenarioRunResult, ScenariosByProduct } from "@/lib/types";

interface ComparisonPageProps {
  results: Record<string, ScenarioRunResult>;
  scenarios: ScenariosByProduct | null;
}

function outcomeBadgeClass(outcome: string | undefined): string {
  switch (outcome) {
    case "success":
    case "delegated":
      return "bg-green-500/15 text-green-400 border-green-500/30";
    case "partial_success":
    case "success_with_warning":
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "denied":
    case "rejected":
      return "bg-red-500/15 text-red-400 border-red-500/30";
    default:
      return "bg-blue-500/15 text-blue-400 border-blue-500/30";
  }
}

const USER_LABELS: Record<string, string> = {
  "onlee": "Pak On",
  "maylina": "Maylina",
  "petry": "Petry",
  "guest": "Guest",
};

export function ComparisonPage({ results }: ComparisonPageProps) {
  const entries = Object.entries(results);

  if (entries.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center pt-4">
        <p className="text-sm text-muted-foreground">
          Run scenarios in the Demo tab to compare results here.
          Each run is added to the comparison grid.
        </p>
      </div>
    );
  }

  return (
    <div className="pt-4">
      <ScrollArea className="h-[calc(100vh-120px)]">
        <div className={cn(
          "grid gap-4",
          entries.length === 1 && "grid-cols-1",
          entries.length === 2 && "grid-cols-2",
          entries.length >= 3 && "grid-cols-3"
        )}>
          {entries.map(([key, result]) => {
            const user = result.user;
            const emailPrefix = user?.email?.split("@")[0] ?? "";
            const userName = USER_LABELS[emailPrefix] ?? emailPrefix;
            const userRole = user?.role ?? "system";
            const outcome = result.outcome ?? result.aip_response?.outcome ?? "unknown";

            return (
              <Card key={key}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{userName}</span>
                      <Badge variant="outline" className="text-xs px-1 py-0">
                        {userRole}
                      </Badge>
                      <Badge variant="outline" className={cn("text-xs ml-auto", outcomeBadgeClass(outcome))}>
                        {outcome}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground font-normal truncate">
                      {result.scenario?.title ?? key}
                    </p>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* ABAC summary */}
                  {result.abac && (
                    <div className="text-xs space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">Scopes:</span>
                        <span>{result.abac.attenuated_scopes.length} delegated</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">Rule:</span>
                        <span className="truncate">{result.abac.rule}</span>
                      </div>
                    </div>
                  )}

                  {/* Rejection reason */}
                  {result.reason && (
                    <p className="text-xs text-red-400 bg-red-500/10 rounded px-2 py-1">
                      {result.reason.length > 100 ? result.reason.slice(0, 100) + "..." : result.reason}
                    </p>
                  )}

                  {/* Tool results summary */}
                  {result.aip_response && result.aip_response.tool_results.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-xs font-medium text-muted-foreground">Tools</span>
                      {result.aip_response.tool_results.map((tr, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <span className={cn(
                            "size-1.5 rounded-full shrink-0",
                            tr.status === "executed" ? "bg-green-400"
                              : tr.status === "denied" ? "bg-red-400"
                              : "bg-amber-400"
                          )} />
                          <span className="truncate">{tr.tool}</span>
                          <span className="text-muted-foreground ml-auto shrink-0">{tr.status}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Blocked tools */}
                  {result.aip_response && (result.aip_response.blocked_tools ?? []).length > 0 && (
                    <div className="space-y-1">
                      <span className="text-xs font-medium text-muted-foreground">Blocked</span>
                      {(result.aip_response.blocked_tools ?? []).map((bt, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs text-red-400">
                          <span className="size-1.5 rounded-full bg-red-400 shrink-0" />
                          <span className="truncate">{bt.tool}</span>
                          <span className="text-muted-foreground ml-auto shrink-0">not available</span>
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
