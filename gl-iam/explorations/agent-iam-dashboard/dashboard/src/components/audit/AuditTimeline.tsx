import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { AuditEvent } from "@/lib/types";

interface AuditTimelineProps {
  events: AuditEvent[];
}

function serviceColor(service: string): string {
  switch (service) {
    case "glchat":
      return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    case "aip":
      return "bg-purple-500/15 text-purple-400 border-purple-500/30";
    case "connectors":
      return "bg-green-500/15 text-green-400 border-green-500/30";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function formatTs(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts;
  }
}

function groupByRef(events: AuditEvent[]): Record<string, AuditEvent[]> {
  const groups: Record<string, AuditEvent[]> = {};
  for (const e of events) {
    const ref = e.delegation_ref || "unknown";
    if (!groups[ref]) groups[ref] = [];
    groups[ref].push(e);
  }
  return groups;
}

function EventDetails({ event }: { event: AuditEvent }) {
  const knownKeys = new Set(["timestamp", "service", "event", "delegation_ref"]);
  const extra = Object.entries(event).filter(([k]) => !knownKeys.has(k));
  if (extra.length === 0) return null;

  return (
    <details className="mt-1.5">
      <summary className="cursor-pointer text-[10px] text-muted-foreground hover:text-foreground">
        Details
      </summary>
      <pre className="mt-1 max-h-24 overflow-auto rounded bg-muted/50 p-1.5 text-[10px]">
        {JSON.stringify(Object.fromEntries(extra), null, 2)}
      </pre>
    </details>
  );
}

export function AuditTimeline({ events }: AuditTimelineProps) {
  if (events.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No audit events yet. Run a scenario to generate events.
      </p>
    );
  }

  const grouped = groupByRef(events);

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([ref, refEvents]) => (
        <div key={ref} className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-[10px]">
              {ref}
            </Badge>
            <span className="text-[10px] text-muted-foreground">
              {refEvents.length} event{refEvents.length !== 1 ? "s" : ""}
            </span>
          </div>

          <div className="relative ml-3 border-l border-border/50 pl-4">
            {refEvents.map((evt, idx) => (
              <div key={idx} className="relative pb-4 last:pb-0">
                {/* Timeline dot */}
                <div
                  className={cn(
                    "absolute -left-[calc(1rem+4.5px)] top-1 size-2 rounded-full",
                    evt.service === "glchat"
                      ? "bg-blue-400"
                      : evt.service === "aip"
                        ? "bg-purple-400"
                        : "bg-green-400"
                  )}
                />

                <Card size="sm" className="border-border/30">
                  <CardContent>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-muted-foreground">
                        {formatTs(evt.timestamp)}
                      </span>
                      <Badge
                        variant="outline"
                        className={cn("text-[10px]", serviceColor(evt.service))}
                      >
                        {evt.service}
                      </Badge>
                      <span className="text-xs font-medium">{evt.event}</span>
                    </div>
                    <EventDetails event={evt} />
                  </CardContent>
                </Card>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
