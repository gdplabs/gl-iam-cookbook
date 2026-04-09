import { useDemoState } from "@/hooks/use-demo-state";
import { Header } from "@/components/layout/Header";
import { DemoPage } from "@/pages/DemoPage";
import { ComparisonPage } from "@/pages/ComparisonPage";
import { AuditPage } from "@/pages/AuditPage";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

function App() {
  const state = useDemoState();

  return (
    <div className="dark flex min-h-screen flex-col bg-background text-foreground">
      <Header health={state.health} />
      <main className="flex-1 p-4">
        <Tabs defaultValue="demo">
          <TabsList>
            <TabsTrigger value="demo">Demo</TabsTrigger>
            <TabsTrigger value="comparison">Comparison</TabsTrigger>
            <TabsTrigger value="audit">Audit Trail</TabsTrigger>
          </TabsList>

          <TabsContent value="demo">
            <DemoPage {...state} />
          </TabsContent>

          <TabsContent value="comparison">
            <ComparisonPage results={state.results} scenarios={state.scenarios} />
          </TabsContent>

          <TabsContent value="audit">
            <AuditPage
              auditEvents={state.auditEvents}
              refreshAudit={state.refreshAudit}
            />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

export default App;
