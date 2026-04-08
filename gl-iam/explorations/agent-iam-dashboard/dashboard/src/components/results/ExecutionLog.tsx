import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import type { ExecutionLogEntry } from "@/lib/types";

interface ExecutionLogProps {
  executionLog: ExecutionLogEntry[];
}

function statusBadge(status: string) {
  const cls =
    status === "ok" || status === "success" || status === "executed"
      ? "bg-green-500/15 text-green-400 border-green-500/30"
      : status === "partial" || status === "attenuated"
        ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
        : status === "denied" || status === "blocked" || status === "error"
          ? "bg-red-500/15 text-red-400 border-red-500/30"
          : "bg-blue-500/15 text-blue-400 border-blue-500/30";
  return (
    <Badge variant="outline" className={cn("text-xs", cls)}>
      {status}
    </Badge>
  );
}

function ScopeList({ label, scopes, color }: { label: string; scopes: string[]; color: string }) {
  if (scopes.length === 0) return null;
  return (
    <div className="space-y-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="flex flex-wrap gap-1">
        {scopes.map((s) => (
          <Badge key={s} variant="outline" className={cn("text-xs", color)}>
            {s}
          </Badge>
        ))}
      </div>
    </div>
  );
}

export function ExecutionLog({ executionLog }: ExecutionLogProps) {
  if (executionLog.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">Execution Log</h3>
      <Accordion>
        {executionLog.map((entry, idx) => (
          <AccordionItem key={idx} value={`step-${idx}`}>
            <AccordionTrigger>
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium">{entry.step}</span>
                {statusBadge(entry.status)}
                {entry.agent_id && (
                  <span className="text-xs text-muted-foreground">
                    {entry.agent_id}
                  </span>
                )}
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-2 pl-1">
                <ScopeList
                  label="Parent scopes"
                  scopes={entry.parent_scopes}
                  color="text-muted-foreground"
                />
                <ScopeList
                  label="Granted scopes"
                  scopes={entry.scopes ?? entry.requested_scopes ?? []}
                  color="text-green-400 border-green-500/30"
                />
                <ScopeList
                  label="Rejected scopes"
                  scopes={entry.rejected_scopes ?? entry.denied_scopes ?? []}
                  color="text-red-400 border-red-500/30"
                />
                {entry.planned_tools && entry.planned_tools.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-muted-foreground">
                      Planned tools
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {entry.planned_tools.map((t) => (
                        <Badge key={t} variant="secondary" className="text-xs">
                          {t}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                {entry.blocked_tools && entry.blocked_tools.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-xs font-medium text-muted-foreground">
                      Blocked tools
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {entry.blocked_tools.map((bt) => (
                        <Badge
                          key={bt.tool}
                          variant="outline"
                          className="text-xs text-red-400 border-red-500/30"
                        >
                          {bt.tool} (missing: {bt.missing_scope})
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                {entry.error && (
                  <p className="text-xs text-red-400">{entry.error}</p>
                )}
              </div>
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </div>
  );
}
