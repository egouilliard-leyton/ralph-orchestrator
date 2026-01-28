import { Header } from "@/components/layout/header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function SettingsPage() {
  return (
    <>
      <Header title="Settings" />
      <main className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
            <p className="text-muted-foreground">
              Configure Ralph Orchestrator
            </p>
          </div>
        </div>
        <div className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle>API Configuration</CardTitle>
              <CardDescription>
                Configure the connection to the Ralph Orchestrator API
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="api-url" className="text-sm font-medium">
                  API URL
                </label>
                <Input
                  id="api-url"
                  placeholder="http://localhost:8000"
                  defaultValue="http://localhost:8000"
                />
              </div>
              <Button>Save Configuration</Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Claude CLI</CardTitle>
              <CardDescription>
                Settings for Claude Code CLI integration
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="claude-cmd" className="text-sm font-medium">
                  Claude Command
                </label>
                <Input
                  id="claude-cmd"
                  placeholder="claude"
                  defaultValue="claude"
                />
              </div>
              <Button>Save Configuration</Button>
            </CardContent>
          </Card>
        </div>
      </main>
    </>
  );
}
