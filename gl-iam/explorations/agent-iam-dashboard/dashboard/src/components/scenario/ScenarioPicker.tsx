import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ScenariosByProduct, ScenarioMeta } from "@/lib/types";

interface ScenarioPickerProps {
  scenarios: ScenariosByProduct;
  currentScenario: string | null;
  onSelect: (id: string) => void;
}

const productLabels: Record<string, string> = {
  glchat: "GLChat",
  de: "DE",
  aip: "AIP",
};

function outcomeBadgeClass(outcome: string): string {
  switch (outcome) {
    case "success":
    case "full_access":
      return "bg-green-500/15 text-green-400 border-green-500/30";
    case "partial":
    case "partial_access":
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "denied":
    case "rejected":
    case "blocked":
      return "bg-red-500/15 text-red-400 border-red-500/30";
    default:
      return "bg-blue-500/15 text-blue-400 border-blue-500/30";
  }
}

function ScenarioRow({
  scenario,
  isSelected,
  onSelect,
}: {
  scenario: ScenarioMeta;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-muted",
        isSelected && "bg-muted ring-1 ring-blue-500/40"
      )}
    >
      <Badge variant="outline" className="shrink-0 font-mono text-[10px]">
        {scenario.id}
      </Badge>
      <span className="flex-1 truncate">{scenario.title}</span>
      <Badge
        variant="outline"
        className={cn("shrink-0 text-[10px]", outcomeBadgeClass(scenario.expected_outcome))}
      >
        {scenario.expected_outcome}
      </Badge>
    </button>
  );
}

export function ScenarioPicker({ scenarios, currentScenario, onSelect }: ScenarioPickerProps) {
  const products = Object.entries(scenarios) as [string, ScenarioMeta[]][];
  const nonEmpty = products.filter(([, items]) => items.length > 0);

  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>Scenarios</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="max-h-[320px] overflow-auto">
          <Accordion defaultValue={nonEmpty.map(([k]) => k)}>
            {nonEmpty.map(([product, items]) => (
              <AccordionItem key={product} value={product}>
                <AccordionTrigger className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {productLabels[product] ?? product} ({items.length})
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-0.5">
                    {items.map((s) => (
                      <ScenarioRow
                        key={s.id}
                        scenario={s}
                        isSelected={currentScenario === s.id}
                        onSelect={() => s.id && onSelect(s.id)}
                      />
                    ))}
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
