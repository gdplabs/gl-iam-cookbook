import { CheckCircle2, XCircle, Minus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { ScenarioRunResult, DelegationChainEntry } from "@/lib/types";

interface ScopeAttenuationTableProps {
  result: ScenarioRunResult;
}

function collectScopesByDepth(chain: DelegationChainEntry[]): Record<number, Set<string>> {
  const byDepth: Record<number, Set<string>> = { 1: new Set(), 2: new Set(), 3: new Set(), 4: new Set() };
  for (const entry of chain) {
    const d = entry.depth;
    if (d < 1 || d > 4) continue;
    const scopes = entry.scopes ?? (entry.scope ? [entry.scope] : []);
    for (const s of scopes) {
      byDepth[d]!.add(s);
    }
  }
  return byDepth;
}

function collectAllScopes(chain: DelegationChainEntry[]): string[] {
  const all = new Set<string>();
  for (const entry of chain) {
    const scopes = entry.scopes ?? (entry.scope ? [entry.scope] : []);
    for (const s of scopes) all.add(s);
  }
  return Array.from(all).sort();
}

function ScopeCell({ present, applicable }: { present: boolean; applicable: boolean }) {
  if (!applicable) {
    return <Minus className="mx-auto size-3.5 text-muted-foreground/40" />;
  }
  return present ? (
    <CheckCircle2 className="mx-auto size-3.5 text-green-400" />
  ) : (
    <XCircle className="mx-auto size-3.5 text-red-400" />
  );
}

export function ScopeAttenuationTable({ result }: ScopeAttenuationTableProps) {
  const aip = result.aip_response;
  if (!aip || aip.delegation_chain.length === 0) return null;

  const byDepth = collectScopesByDepth(aip.delegation_chain);
  const allScopes = collectAllScopes(aip.delegation_chain);
  const maxDepthPresent = Math.max(
    ...aip.delegation_chain.map((e) => e.depth)
  );

  if (allScopes.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">Scope Attenuation</h3>
      <Card size="sm">
        <CardContent>
          <div className="overflow-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="py-1.5 pr-4 text-left font-medium">Scope</th>
                  <th className="px-3 py-1.5 text-center font-medium">d1 User</th>
                  <th className="px-3 py-1.5 text-center font-medium">d2 Agent</th>
                  <th className="px-3 py-1.5 text-center font-medium">d3 Worker</th>
                  <th className="px-3 py-1.5 text-center font-medium">d4 Tool</th>
                </tr>
              </thead>
              <tbody>
                {allScopes.map((scope) => (
                  <tr key={scope} className="border-b border-border/50">
                    <td className="py-1.5 pr-4 font-mono">{scope}</td>
                    {[1, 2, 3, 4].map((d) => (
                      <td key={d} className="px-3 py-1.5 text-center">
                        <ScopeCell
                          present={byDepth[d]?.has(scope) ?? false}
                          applicable={d <= maxDepthPresent}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
