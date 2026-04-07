import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { AuditEvent } from "@/lib/types";

interface AuditTimelineProps {
  events: AuditEvent[];
}

function sourceColor(event: AuditEvent): string {
  if (event.source === "sdk") {
    return "bg-violet-500/15 text-violet-400 border-violet-500/30";
  }
  switch (event.service) {
    case "glchat_be":
    case "glchat":
      return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    case "aip_backend":
    case "aip":
      return "bg-purple-500/15 text-purple-400 border-purple-500/30";
    case "connectors":
      return "bg-green-500/15 text-green-400 border-green-500/30";
    case "gl-iam":
      return "bg-violet-500/15 text-violet-400 border-violet-500/30";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function dotColor(event: AuditEvent): string {
  if (event.source === "sdk") return "bg-violet-400";
  switch (event.service) {
    case "glchat_be":
    case "glchat":
      return "bg-blue-400";
    case "aip_backend":
    case "aip":
      return "bg-purple-400";
    case "connectors":
      return "bg-green-400";
    default:
      return "bg-gray-400";
  }
}

function severityColor(severity?: string): string {
  switch (severity) {
    case "error":
    case "critical":
      return "bg-red-500/15 text-red-400 border-red-500/30";
    case "warning":
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    default:
      return "";
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

function sourceLabel(event: AuditEvent): string {
  if (event.source === "sdk") return "GL-IAM SDK";
  return event.service;
}

function groupByRef(events: AuditEvent[]): Record<string, AuditEvent[]> {
  const groups: Record<string, AuditEvent[]> = {};
  for (const e of events) {
    const ref = e.delegation_ref || "(no ref)";
    if (!groups[ref]) groups[ref] = [];
    groups[ref].push(e);
  }
  return groups;
}

function EventDetails({ event }: { event: AuditEvent }) {
  const knownKeys = new Set([
    "timestamp", "service", "event", "delegation_ref", "source", "severity",
    "id", "user_id", "organization_id", "resource_id", "error_code", "message",
  ]);
  const extra = Object.entries(event).filter(
    ([k, v]) => !knownKeys.has(k) && v !== null && v !== undefined && v !== ""
  );

  return (
    <div className="mt-1.5 space-y-1">
      {/* Show key SDK fields inline */}
      {event.source === "sdk" && (
        <div className="flex flex-wrap gap-2 text-[10px] text-muted-foreground">
          {event.user_id && <span>user: <code className="text-foreground">{event.user_id}</code></span>}
          {event.resource_id && <span>resource: <code className="text-foreground">{event.resource_id}</code></span>}
          {event.organization_id && <span>org: <code className="text-foreground">{event.organization_id}</code></span>}
        </div>
      )}
      {event.message && (
        <p className="text-[10px] text-muted-foreground">{event.message}</p>
      )}
      {extra.length > 0 && (
        <details>
          <summary className="cursor-pointer text-[10px] text-muted-foreground hover:text-foreground">
            Details ({extra.length} fields)
          </summary>
          <pre className="mt-1 max-h-24 overflow-auto rounded bg-muted/50 p-1.5 text-[10px]">
            {JSON.stringify(Object.fromEntries(extra), null, 2)}
          </pre>
        </details>
      )}
    </div>
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
              {ref.length > 20 ? ref.slice(0, 20) + "..." : ref}
            </Badge>
            <span className="text-[10px] text-muted-foreground">
              {refEvents.length} event{refEvents.length !== 1 ? "s" : ""}
            </span>
            {/* Count by source */}
            <span className="text-[9px] text-muted-foreground/60">
              ({refEvents.filter(e => e.source === "sdk").length} SDK, {refEvents.filter(e => e.source !== "sdk").length} app)
            </span>
          </div>

          <div className="relative ml-3 border-l border-border/50 pl-4">
            {refEvents.map((evt, idx) => (
              <div key={idx} className="relative pb-3 last:pb-0">
                <div className={cn("absolute -left-[calc(1rem+4.5px)] top-1 size-2 rounded-full", dotColor(evt))} />

                <Card size="sm" className="border-border/30">
                  <CardContent>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] font-mono text-muted-foreground">
                        {formatTs(evt.timestamp)}
                      </span>
                      <Badge variant="outline" className={cn("text-[10px]", sourceColor(evt))}>
                        {sourceLabel(evt)}
                      </Badge>
                      {evt.severity && evt.severity !== "info" && (
                        <Badge variant="outline" className={cn("text-[9px]", severityColor(evt.severity))}>
                          {evt.severity}
                        </Badge>
                      )}
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
