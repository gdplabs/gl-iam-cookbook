import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AuditEvent } from "@/lib/types";

interface AuditPageProps {
  auditEvents: AuditEvent[];
  refreshAudit: (delegationRef?: string) => Promise<void>;
}

export function AuditPage({ auditEvents, refreshAudit }: AuditPageProps) {
  return (
    <div className="space-y-4 pt-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Audit Trail</h2>
        <Button variant="ghost" size="sm" onClick={() => refreshAudit()}>
          <RefreshCw className="size-3.5" />
          Refresh
        </Button>
      </div>
      <ScrollArea className="h-[calc(100vh-160px)]">
        <AuditTimeline events={auditEvents} />
      </ScrollArea>
    </div>
  );
}
