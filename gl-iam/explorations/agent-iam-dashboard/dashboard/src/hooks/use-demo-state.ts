import { useCallback, useEffect, useRef, useState } from "react";
import {
  checkHealth,
  demoReset,
  demoSetup,
  getAllAuditEvents,
  getScenarios,
  runScenario,
} from "@/lib/api";
import type {
  AppPhase,
  AuditEvent,
  ScenarioRunResult,
  ScenariosByProduct,
  ServiceHealth,
  SetupResult,
} from "@/lib/types";

export function useDemoState() {
  const [phase, setPhase] = useState<AppPhase>("idle");
  const [health, setHealth] = useState<ServiceHealth>({
    glchat: null,
    aip: null,
    connectors: null,
  });
  const [scenarios, setScenarios] = useState<ScenariosByProduct | null>(null);
  const [setupResult, setSetupResult] = useState<SetupResult | null>(null);
  const [currentScenario, setCurrentScenario] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, ScenarioRunResult>>({});
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const healthInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll health
  const pollHealth = useCallback(async () => {
    const [g, a, c] = await Promise.all([
      checkHealth("glchat"),
      checkHealth("aip"),
      checkHealth("connectors"),
    ]);
    setHealth({ glchat: g, aip: a, connectors: c });
  }, []);

  useEffect(() => {
    pollHealth();
    healthInterval.current = setInterval(pollHealth, 5000);
    return () => {
      if (healthInterval.current) clearInterval(healthInterval.current);
    };
  }, [pollHealth]);

  // Setup
  const setup = useCallback(async () => {
    setPhase("setting-up");
    setError(null);
    try {
      const result = await demoSetup();
      setSetupResult(result);
      const scenarioData = await getScenarios();
      setScenarios(scenarioData);
      setPhase("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Setup failed");
      setPhase("idle");
    }
  }, []);

  // Reset
  const reset = useCallback(async () => {
    await demoReset();
    setPhase("idle");
    setSetupResult(null);
    setScenarios(null);
    setResults({});
    setAuditEvents([]);
    setCurrentScenario(null);
    setError(null);
  }, []);

  // Run scenario
  const run = useCallback(async (scenarioId: string) => {
    setPhase("running");
    setCurrentScenario(scenarioId);
    setError(null);
    try {
      const result = await runScenario(scenarioId);
      setResults((prev) => ({ ...prev, [scenarioId]: result }));

      // Fetch audit events for this delegation
      if (result.delegation_ref) {
        const events = await getAllAuditEvents(result.delegation_ref);
        setAuditEvents((prev) => [...prev, ...events]);
      }

      setPhase("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scenario run failed");
      setPhase("ready");
    }
  }, []);

  // Fetch all audit events
  const refreshAudit = useCallback(async (delegationRef?: string) => {
    const events = await getAllAuditEvents(delegationRef);
    if (delegationRef) {
      setAuditEvents((prev) => {
        const existing = prev.filter((e) => e.delegation_ref !== delegationRef);
        return [...existing, ...events].sort(
          (a, b) =>
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );
      });
    } else {
      setAuditEvents(events);
    }
  }, []);

  const allHealthy = health.glchat && health.aip && health.connectors;
  const currentResult = currentScenario ? results[currentScenario] : null;

  // Add a result from interactive mode (for comparison page)
  const addResult = useCallback((key: string, result: ScenarioRunResult) => {
    setResults((prev) => ({ ...prev, [key]: result }));
  }, []);

  return {
    phase,
    health,
    allHealthy,
    scenarios,
    setupResult,
    currentScenario,
    currentResult,
    results,
    auditEvents,
    error,
    setup,
    reset,
    run,
    addResult,
    refreshAudit,
    setCurrentScenario,
  };
}
