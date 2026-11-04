import { AppShell, useNav } from "@/components/app-shell";
import { ErrorBox, Loading } from "@/components/page";
import { useRoute } from "@/lib/router";
import { useMe } from "@/lib/use-me";
import { AgentsPage } from "@/pages/agents-page";
import { ApprovalsPage } from "@/pages/approvals-page";
import { ChatPage } from "@/pages/chat/chat-page";
import { ConnectorsPage } from "@/pages/connectors-page";
import { HealthPage } from "@/pages/health-page";
import { LogsPage } from "@/pages/logs-page";
import { MemoriesPage } from "@/pages/memories-page";
import { SchedulesPage } from "@/pages/schedules-page";
import { SettingsPage } from "@/pages/settings-page";
import { VariablesPage } from "@/pages/variables-page";
import { SkillsPage } from "@/pages/skills-page";

export function App() {
  const me = useMe();
  const [route = "chat", routeArg] = useRoute();
  // Git moved into Settings; an old #/git link still lands there.
  const [page, arg] = route === "git" ? ["settings", "git"] : [route, routeArg];
  const allowed = useNav().map((n) => n.id);
  if (me.isLoading) return <Loading />;
  if (me.error) {
    return (
      <div className="flex h-dvh items-center justify-center p-6">
        <div className="max-w-sm space-y-2 text-center">
          <h1 className="text-lg font-semibold">Not signed in to ai-os</h1>
          <ErrorBox error={me.error} />
        </div>
      </div>
    );
  }
  const current = allowed.includes(page) ? page : "chat";
  const body = {
    chat: <ChatPage id={arg} />,
    approvals: <ApprovalsPage />,
    schedules: <SchedulesPage />,
    memories: <MemoriesPage />,
    agents: <AgentsPage name={arg} />,
    skills: <SkillsPage />,
    connectors: <ConnectorsPage />,
    variables: <VariablesPage />,
    logs: <LogsPage />,
    health: <HealthPage />,
    settings: <SettingsPage tab={arg} />,
  }[current];
  // In a chat thread the thread header (with its back button) replaces the phone's top bar.
  return (
    <AppShell current={current} hideMobileBar={current === "chat" && Boolean(arg)}>
      {body}
    </AppShell>
  );
}
