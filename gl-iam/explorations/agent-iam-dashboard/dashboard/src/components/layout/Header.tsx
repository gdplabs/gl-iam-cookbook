import { Shield } from "lucide-react";
import { ServiceHealth } from "@/components/setup/ServiceHealth";
import type { ServiceHealth as ServiceHealthType } from "@/lib/types";

interface HeaderProps {
  health: ServiceHealthType;
}

export function Header({ health }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-border bg-card px-6 py-3">
      <div className="flex items-center gap-3">
        <Shield className="size-6 text-blue-400" />
        <h1 className="text-lg font-semibold tracking-tight">
          Agent IAM Dashboard
        </h1>
      </div>
      <ServiceHealth health={health} />
    </header>
  );
}
