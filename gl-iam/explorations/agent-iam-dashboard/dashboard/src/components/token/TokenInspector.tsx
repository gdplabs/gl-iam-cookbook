import { Key } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { decodeJwt, formatTimestamp } from "@/lib/decode-jwt";

interface TokenInspectorProps {
  token: string;
  label: string;
}

const HIGHLIGHT_KEYS = new Set(["sub", "act", "scopes", "delegation_chain", "exp", "iat", "iss", "aud"]);

function ClaimRow({ k, v }: { k: string; v: unknown }) {
  const isHighlighted = HIGHLIGHT_KEYS.has(k);
  let display: React.ReactNode;

  if (k === "exp" || k === "iat") {
    display = (
      <span>
        {String(v)}{" "}
        <span className="text-muted-foreground">
          ({formatTimestamp(v as number)})
        </span>
      </span>
    );
  } else if (typeof v === "object" && v !== null) {
    display = (
      <pre className="max-h-32 overflow-auto rounded bg-muted/50 p-1.5 text-[10px]">
        {JSON.stringify(v, null, 2)}
      </pre>
    );
  } else {
    display = String(v);
  }

  return (
    <div className={cn("flex gap-3 py-1 text-xs", isHighlighted && "font-medium")}>
      <span
        className={cn(
          "w-32 shrink-0 font-mono",
          isHighlighted ? "text-blue-400" : "text-muted-foreground"
        )}
      >
        {k}
      </span>
      <span className="min-w-0 break-all">{display}</span>
    </div>
  );
}

export function TokenInspector({ token, label }: TokenInspectorProps) {
  const claims = decodeJwt(token);

  if (!claims) {
    return (
      <Card size="sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Key className="size-3.5" />
            {label}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">Unable to decode token.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Key className="size-3.5" />
          {label}
          <Badge variant="secondary" className="text-[10px]">
            JWT
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="divide-y divide-border/50">
          {Object.entries(claims).map(([k, v]) => (
            <ClaimRow key={k} k={k} v={v} />
          ))}
        </div>
        <details className="mt-3">
          <summary className="cursor-pointer text-[10px] text-muted-foreground hover:text-foreground">
            Raw token
          </summary>
          <pre className="mt-1 max-h-20 overflow-auto break-all rounded bg-muted/50 p-2 text-[10px]">
            {token}
          </pre>
        </details>
      </CardContent>
    </Card>
  );
}
