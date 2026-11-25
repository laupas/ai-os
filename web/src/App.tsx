import { AppShell, useNav } from "@/components/app-shell";
import { ErrorBox, Loading } from "@/components/page";
import { useRoute } from "@/lib/router";
import { useLogin } from "@/lib/use-login";
import { useMe } from "@/lib/use-me";
import { AgentsPage } from "@/pages/agents-page";
import { AppearancePage } from "@/pages/appearance-page";
import { ApprovalsPage } from "@/pages/approvals-page";
import { AuditPage } from "@/pages/audit-page";
import { ChatPage } from "@/pages/chat/chat-page";
import { ConnectorsPage } from "@/pages/connectors-page";
import { HealthPage } from "@/pages/health-page";
import { LoginScreen } from "@/pages/login-page";
import { LogsPage } from "@/pages/logs-page";
import { MemoriesPage } from "@/pages/memories-page";
import { TriggersPage } from "@/pages/triggers-page";
import { SettingsPage } from "@/pages/settings-page";
import { StorePage } from "@/pages/store-page";
import { VariablesPage } from "@/pages/variables-page";
import { VoicePage } from "@/pages/voice/voice-page";
import { SkillsPage } from "@/pages/skills-page";

export function App() {
  const me = useMe();
  const [route = "chat", routeArg] = useRoute();
  // Git moved into Settings; an old #/git link still lands there.
  const [page, arg] = route === "git" ? ["settings", "git"] : [route, routeArg];
  // Appearance is everyone's, reached from the account box rather than the menu.
  const allowed = [...useNav().map((n) => n.id), "appearance"];
  // Not signed in: the console's own login page, if it has one.
  const login = useLogin(Boolean(me.error));
  if (me.isLoading || (me.error && login.isLoading)) return <Loading />;
  if (me.error && login.data?.mode) return <LoginScreen info={login.data} />;
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
    voice: <VoicePage />,
    approvals: <ApprovalsPage />,
    triggers: <TriggersPage />,
    memories: <MemoriesPage />,
    agents: <AgentsPage name={arg} />,
    skills: <SkillsPage />,
    connectors: <ConnectorsPage />,
    store: <StorePage />,
    variables: <VariablesPage />,
    audit: <AuditPage />,
    logs: <LogsPage />,
    health: <HealthPage />,
    settings: <SettingsPage tab={arg} />,
    appearance: <AppearancePage />,
  }[current];
  // In a chat thread the composer takes the bottom of a phone's screen, not the tab bar.
  return (
    <AppShell current={current} hideTabBar={current === "chat" && Boolean(arg)}>
      {body}
    </AppShell>
  );
}
