import { cn } from "@/lib/utils";
import type { ServiceHealth as ServiceHealthType } from "@/lib/types";

interface ServiceHealthProps {
  health: ServiceHealthType;
}

const services: { key: keyof ServiceHealthType; label: string; port: number }[] = [
  { key: "glchat", label: "glchat", port: 8000 },
  { key: "aip", label: "aip", port: 8001 },
  { key: "connectors", label: "connectors", port: 8002 },
];

export function ServiceHealth({ health }: ServiceHealthProps) {
  return (
    <div className="flex items-center gap-4">
      {services.map(({ key, label, port }) => {
        const status = health[key];
        return (
          <div key={key} className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              className={cn(
                "size-2 rounded-full",
                status === true && "bg-green-500",
                status === false && "bg-red-500",
                status === null && "bg-gray-500"
              )}
            />
            <span>{label}:{port}</span>
          </div>
        );
      })}
    </div>
  );
}
