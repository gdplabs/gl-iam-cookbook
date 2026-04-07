import { useCallback, useEffect, useState } from "react";
import { User, Bot, Zap, Play, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  getDemoUsers,
  getDemoOrchestrators,
  getDemoActions,
  interactiveRun,
} from "@/lib/api";
import type { DemoUser, DemoOrchestrator, DemoAction } from "@/lib/api";
import type { AppPhase, ScenarioRunResult } from "@/lib/types";

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  member: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  viewer: "bg-gray-500/20 text-gray-300 border-gray-500/30",
};

interface ScenarioBuilderProps {
  phase: AppPhase;
  onResult: (result: ScenarioRunResult) => void;
  onError: (error: string) => void;
}

const selectClass = cn(
  "w-full h-9 rounded-md border border-input bg-card text-foreground text-xs",
  "px-2 py-1.5 outline-none focus:ring-2 focus:ring-ring/50",
  "appearance-auto cursor-pointer",
);

export function ScenarioBuilder({ phase, onResult, onError }: ScenarioBuilderProps) {
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [orchestrators, setOrchestrators] = useState<DemoOrchestrator[]>([]);
  const [actions, setActions] = useState<Record<string, DemoAction[]>>({});

  const [selectedUserEmail, setSelectedUserEmail] = useState("");
  const [selectedAgentName, setSelectedAgentName] = useState("");
  const [selectedActionId, setSelectedActionId] = useState("");
  const [isRunning, setIsRunning] = useState(false);

  const selectedUser = users.find((u) => u.email === selectedUserEmail) ?? null;
  const selectedAgent = orchestrators.find((a) => a.name === selectedAgentName) ?? null;
  const availableActions = selectedAgentName ? (actions[selectedAgentName] ?? []) : [];
  const selectedAction = availableActions.find((a) => a.id === selectedActionId) ?? null;

  useEffect(() => {
    if (phase !== "ready" && phase !== "running") return;
    const load = async () => {
      try {
        const [u, o, a] = await Promise.all([
          getDemoUsers(),
          getDemoOrchestrators(),
          getDemoActions(),
        ]);
        setUsers(u);
        setOrchestrators(o);
        setActions(a);
      } catch {
        // Data not available yet
      }
    };
    load();
  }, [phase]);

  const handleAgentChange = useCallback((value: string) => {
    setSelectedAgentName(value);
    setSelectedActionId("");
  }, []);

  const handleRun = useCallback(async () => {
    if (!selectedUser || !selectedAgent || !selectedAction) return;
    setIsRunning(true);
    try {
      const result = await interactiveRun(
        selectedUser.email,
        selectedAgent.name,
        selectedAction.id,
      );
      onResult(result);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setIsRunning(false);
    }
  }, [selectedUser, selectedAgent, selectedAction, onResult, onError]);

  if (users.length === 0) return null;

  const canRun = selectedUser && selectedAgent && selectedAction && !isRunning;

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>Interactive Demo</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* User */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
            <User className="size-3" /> User
          </label>
          <select
            className={selectClass}
            value={selectedUserEmail}
            onChange={(e) => setSelectedUserEmail(e.target.value)}
          >
            <option value="">Select a user...</option>
            {users.map((user) => {
              const orgLabel = user.tenant === "NONE" ? "No Org"
                : user.role === "admin" ? "Cross-Org"
                : user.tenant;
              return (
                <option key={user.email} value={user.email}>
                  {user.display_name} — {user.role} ({orgLabel})
                </option>
              );
            })}
          </select>
          {selectedUser && (
            <div className="flex items-center gap-2 px-0.5 flex-wrap">
              <Badge variant="outline" className={cn("text-[9px] px-1.5 py-0", ROLE_COLORS[selectedUser.role])}>
                {selectedUser.role}
              </Badge>
              <Badge variant="outline" className={`text-[9px] px-1.5 py-0 ${
                selectedUser.tenant === "NONE" ? "bg-gray-500/15 text-gray-300 border-gray-500/30"
                : selectedUser.role === "admin" ? "bg-purple-500/15 text-purple-300 border-purple-500/30"
                : "bg-cyan-500/15 text-cyan-300 border-cyan-500/30"
              }`}>
                {selectedUser.tenant === "NONE" ? "No Org" : selectedUser.role === "admin" ? "Cross-Org" : `Org: ${selectedUser.tenant}`}
              </Badge>
              <span className="text-[10px] text-muted-foreground">
                {selectedUser.scopes.length} scopes
              </span>
            </div>
          )}
        </div>

        {/* Agent */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
            <Bot className="size-3" /> Agent
          </label>
          <select
            className={selectClass}
            value={selectedAgentName}
            onChange={(e) => handleAgentChange(e.target.value)}
          >
            <option value="">Select an agent...</option>
            {orchestrators.map((agent) => (
              <option key={agent.name} value={agent.name}>
                {agent.name} ({agent.type})
              </option>
            ))}
          </select>
          {selectedAgent && (
            <div className="flex items-center gap-2 px-0.5">
              <Badge variant="outline" className="text-[9px] px-1.5 py-0 bg-amber-500/15 text-amber-300 border-amber-500/30">
                {selectedAgent.type}
              </Badge>
              <span className="text-[10px] text-muted-foreground">
                {selectedAgent.allowed_scopes.length} scopes
              </span>
            </div>
          )}
        </div>

        {/* Action */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
            <Zap className="size-3" /> Action
          </label>
          <select
            className={selectClass}
            value={selectedActionId}
            onChange={(e) => setSelectedActionId(e.target.value)}
            disabled={!selectedAgentName}
          >
            <option value="">{selectedAgentName ? "Select an action..." : "Pick an agent first"}</option>
            {availableActions.map((action) => (
              <option key={action.id} value={action.id}>
                {action.title}
              </option>
            ))}
          </select>
          {selectedAction && (
            <p className="text-[10px] text-muted-foreground italic px-0.5">
              &ldquo;{selectedAction.message}&rdquo;
            </p>
          )}
        </div>

        {/* Run */}
        <Button
          size="sm"
          className="w-full"
          onClick={handleRun}
          disabled={!canRun}
        >
          {isRunning ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Play className="size-3.5" />
          )}
          {isRunning ? "Running..." : "Run Scenario"}
        </Button>
      </CardContent>
    </Card>
  );
}
