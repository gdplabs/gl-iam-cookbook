import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle, AlertTriangle, Wrench, Shield, Bot } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ToolResult } from "@/lib/types";

interface ToolResultCardProps {
  result: ToolResult;
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "executed":
    case "success":
      return <CheckCircle2 className="size-3.5 text-green-400" />;
    case "denied":
    case "blocked":
    case "policy_rejected":
      return <XCircle className="size-3.5 text-red-400" />;
    default:
      return <AlertTriangle className="size-3.5 text-amber-400" />;
  }
}

function statusColor(status: string): string {
  switch (status) {
    case "executed":
    case "success":
      return "bg-green-500/15 text-green-400 border-green-500/30";
    case "denied":
    case "blocked":
    case "policy_rejected":
      return "bg-red-500/15 text-red-400 border-red-500/30";
    default:
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
  }
}

/** Detect if the rejection came from agent policy (worker level) vs tool/connector level */
function isAgentPolicyRejection(error: string | undefined): boolean {
  if (!error) return false;
  return error.includes("Resource constraint violation") ||
         error.includes("delegation policy restricts") ||
         error.includes("personal OAuth credentials");
}

export function ToolResultCard({ result }: ToolResultCardProps) {
  const isPolicyRejection = isAgentPolicyRejection(result.error);

  return (
    <Card size="sm">
      <CardContent className="space-y-2">
        <div className="flex items-center gap-2">
          <Wrench className="size-3.5 text-muted-foreground" />
          <span className="text-xs font-medium">{result.tool}</span>
          <Badge variant="outline" className={cn("ml-auto text-xs", statusColor(result.status))}>
            <StatusIcon status={result.status} />
            {result.status === "denied" && isPolicyRejection ? "policy rejected" : result.status}
          </Badge>
        </div>

        {/* Show enforcement layer */}
        {result.status === "denied" && isPolicyRejection && (
          <div className="flex items-center gap-1.5 text-xs text-amber-400">
            <Bot className="size-3" />
            <Shield className="size-3" />
            <span>Rejected by <strong>Agent Worker</strong> (policy guard rail) — GL Connector was never called</span>
          </div>
        )}

        {result.result && Object.keys(result.result).length > 0 && (
          <pre className="max-h-24 overflow-auto rounded bg-muted/50 p-2 text-xs">
            {JSON.stringify(result.result, null, 2)}
          </pre>
        )}
        {result.error && (
          <p className="text-xs text-red-400">{result.error}</p>
        )}
        {result.warnings && result.warnings.length > 0 && (
          <div className="space-y-0.5">
            {result.warnings.map((w, i) => (
              <p key={i} className="text-xs text-amber-400">{w}</p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
