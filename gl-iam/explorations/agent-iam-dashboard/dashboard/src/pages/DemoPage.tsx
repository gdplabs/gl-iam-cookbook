import { useState } from "react";
import { SetupPanel } from "@/components/setup/SetupPanel";
import { ScenarioBuilder } from "@/components/scenario/ScenarioBuilder";
import { DelegationFlow } from "@/components/delegation/DelegationFlow";
import { ScopeAttenuationTable } from "@/components/delegation/ScopeAttenuationTable";
import { CredentialPolicyPanel } from "@/components/delegation/CredentialPolicyPanel";
import { PolicyDecisionTrace } from "@/components/delegation/PolicyDecisionTrace";
import { ChatSimulation } from "@/components/results/ChatSimulation";
import { ExecutionLog } from "@/components/results/ExecutionLog";
import { ToolResultCard } from "@/components/results/ToolResultCard";
import { TokenInspector } from "@/components/token/TokenInspector";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type {
  AppPhase,
  ScenarioRunResult,
  ScenariosByProduct,
  SetupResult,
} from "@/lib/types";

interface DemoPageProps {
  phase: AppPhase;
  setup: () => Promise<void>;
  reset: () => Promise<void>;
  setupResult: SetupResult | null;
  allHealthy: boolean | null;
  scenarios: ScenariosByProduct | null;
  currentScenario: string | null;
  currentResult: ScenarioRunResult | null | undefined;
  run: (id: string) => Promise<void>;
  setCurrentScenario: (id: string) => void;
  error: string | null;
}

export function DemoPage({
  phase,
  setup,
  reset,
  setupResult,
  allHealthy,
  error: parentError,
}: DemoPageProps) {
  const [currentResult, setCurrentResult] = useState<ScenarioRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const displayError = error || parentError;

  return (
    <div className="flex gap-4 pt-4">
      {/* Left panel */}
      <div className="w-[420px] shrink-0 space-y-4">
        <SetupPanel
          phase={phase}
          setup={setup}
          reset={async () => { await reset(); setCurrentResult(null); setError(null); }}
          setupResult={setupResult}
          allHealthy={allHealthy}
        />

        <ScenarioBuilder
          phase={phase}
          onResult={(result) => { setCurrentResult(result); setError(null); }}
          onError={setError}
        />

        {displayError && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
            {displayError}
          </div>
        )}
      </div>

      {/* Right panel */}
      <div className="flex-1 min-w-0">
        <ScrollArea className="h-[calc(100vh-120px)]">
          {currentResult ? (
            <div className="space-y-6 pr-2">
              <ChatSimulation result={currentResult} />
              <Separator />
              <DelegationFlow result={currentResult} />
              <Separator />
              <ScopeAttenuationTable result={currentResult} />

              <Separator />
              <PolicyDecisionTrace result={currentResult} />

              <Separator />
              <CredentialPolicyPanel
                agentName={
                  currentResult.aip_response?.delegation_chain
                    .find((e) => e.depth === 2)
                    ?.agent_id?.split(":").pop()
                }
              />

              {currentResult.aip_response &&
                currentResult.aip_response.execution_log.length > 0 && (
                  <>
                    <Separator />
                    <ExecutionLog
                      executionLog={currentResult.aip_response.execution_log}
                    />
                  </>
                )}

              {currentResult.aip_response &&
                currentResult.aip_response.tool_results.length > 0 && (
                  <>
                    <Separator />
                    <div className="space-y-3">
                      <h3 className="text-sm font-semibold">Tool Results</h3>
                      <div className="grid gap-2 sm:grid-cols-2">
                        {currentResult.aip_response.tool_results.map((tr, i) => (
                          <ToolResultCard key={i} result={tr} />
                        ))}
                      </div>
                    </div>
                  </>
                )}

              {currentResult.delegation_token && (
                <>
                  <Separator />
                  <TokenInspector
                    token={currentResult.delegation_token}
                    label="Delegation Token"
                  />
                </>
              )}

              {currentResult.aip_response &&
                currentResult.aip_response.delegation_chain.length > 0 && (
                  <>
                    <Separator />
                    <div className="space-y-3">
                      <h3 className="text-sm font-semibold">Chain Tokens</h3>
                      <div className="space-y-2">
                        {currentResult.aip_response.delegation_chain
                          .filter((e) => e.token)
                          .map((e, i) => (
                            <TokenInspector
                              key={i}
                              token={e.token}
                              label={`d${e.depth} - ${e.label}`}
                            />
                          ))}
                      </div>
                    </div>
                  </>
                )}
            </div>
          ) : (
            <div className="flex h-64 items-center justify-center">
              <p className="text-sm text-muted-foreground">
                {phase === "idle"
                  ? "Initialize the demo environment to get started."
                  : "Pick a user, agent, and action — then run the scenario."}
              </p>
            </div>
          )}
        </ScrollArea>
      </div>
    </div>
  );
}
