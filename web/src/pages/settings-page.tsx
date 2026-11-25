import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ChevronRight, Power } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { ConfigReference } from "@/components/config-reference";
import { SaveBar } from "@/components/save-bar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { api, type Settings } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { restartAiOs } from "@/lib/restart";
import { href } from "@/lib/router";
import { cn } from "@/lib/utils";
import { GitPanel } from "./git-page";
import { RepositoryPanel } from "./repository-panel";
import { ChannelsPanel } from "./settings-channels";
import { ClaudePanel } from "./settings-claude";
import { SecurityPanel } from "./settings-security";
import { LoginPanel } from "./settings-login";
import { FilesPanel } from "./settings-files";
import { AgentsSettingsPanel, ApprovalsSettingsPanel, DataAccessPanel, GeneralPanel } from "./settings-sections";
import { GroupsPanel, UsersPanel } from "./settings-people";

// The sections, by group. The ids are the addresses (#/settings/git), so old links keep working.
export const SECTIONS = [
  { group: "AI", items: [{ id: "claude", label: "Claude" }, { id: "agents", label: "Agents" }, { id: "approvals", label: "Approvals" }] },
  { group: "Access", items: [{ id: "login", label: "Login" }, { id: "users", label: "Users" }, { id: "groups", label: "Groups" }, { id: "access", label: "Data access" }, { id: "security", label: "Security" }] },
  { group: "System", items: [{ id: "general", label: "General" }, { id: "channels", label: "Channels" }, { id: "files", label: "Files" }] },
  { group: "Configuration", items: [{ id: "repository", label: "Repository" }, { id: "git", label: "Branches" }, { id: "config", label: "aios.yaml" }] },
];
const ALL = SECTIONS.flatMap((g) => g.items);

const editor = "font-mono text-xs md:text-xs";

/** The sections listed on the left from 768px. On a phone the list and a section are
 * two screens, as in chat: #/settings is the list, #/settings/<section> one section. */
export function SettingsPage({ tab }: { tab?: string }) {
  const { data, isLoading, error } = useQuery({ queryKey: ["settings"], queryFn: () => api<Settings>("GET", "/api/settings") });
  const confirm = useConfirm();
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} />;
  const restart = async () => {
    if (!(await confirm({ title: "Restart ai-os?", body: "Running turns are stopped. The page reloads when it is back.", action: "Restart" })))
      return;
    try {
      await restartAiOs();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const chosen = ALL.find((s) => s.id === tab);
  const shown = chosen ?? ALL[0];
  const panel = {
    claude: <ClaudePanel />,
    channels: <ChannelsPanel />,
    general: <GeneralPanel />,
    agents: <AgentsSettingsPanel />,
    approvals: <ApprovalsSettingsPanel />,
    repository: <RepositoryPanel />,
    git: <GitPanel />,
    config: <ConfigEditor key={data.config} text={data.config} schema={data.config_schema} inRepository={Boolean(data.in_repository)} />,
    login: <LoginPanel />,
    files: <FilesPanel />,
    access: <DataAccessPanel />,
    users: <UsersPanel data={data} />,
    groups: <GroupsPanel data={data} />,
    security: <SecurityPanel />,
  }[shown.id];
  return (
    <Page className="max-w-6xl">
      <div className={cn(chosen && "max-md:hidden")}>
        <PageHeader
          title="Settings"
          actions={
            <Button variant="outline" onClick={restart}>
              <Power /> Restart ai-os
            </Button>
          }
        />
      </div>
      {chosen ? (
        <div className="-ml-2 flex items-center gap-1 md:hidden">
          <Button variant="ghost" size="icon" asChild>
            <a href={href("settings")} aria-label="All settings">
              <ArrowLeft />
            </a>
          </Button>
          <h1 className="text-xl font-semibold">{chosen.label}</h1>
        </div>
      ) : null}
      <div className="md:grid md:grid-cols-[12rem_minmax(0,1fr)] md:items-start md:gap-8">
        <SectionNav current={shown.id} className={cn("md:sticky md:top-0", chosen && "max-md:hidden")} />
        <div className={cn("min-w-0", !chosen && "max-md:hidden")}>{panel}</div>
      </div>
    </Page>
  );
}

/** Grouped rows to tap on a phone; on a wider screen a list of links beside the section. */
function SectionNav({ current, className }: { current: string; className?: string }) {
  return (
    <nav aria-label="Settings sections" className={cn("space-y-5 md:space-y-4", className)}>
      {SECTIONS.map(({ group, items }) => (
        <div key={group}>
          <div className="px-1 pb-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase md:px-3 md:pb-1 md:text-[11px]">{group}</div>
          <div className="divide-y overflow-hidden rounded-xl border bg-card md:space-y-0.5 md:divide-y-0 md:overflow-visible md:rounded-none md:border-0 md:bg-transparent">
            {items.map(({ id, label }) => (
              <a
                key={id}
                href={href("settings", id)}
                aria-current={id === current ? "page" : undefined}
                className={cn(
                  "flex min-h-12 items-center px-4 text-sm hover:bg-accent/50 md:min-h-0 md:rounded-lg md:px-3 md:py-1.5 md:text-muted-foreground md:hover:bg-accent md:hover:text-foreground",
                  id === current && "md:bg-primary/10 md:font-medium md:text-primary md:hover:bg-primary/15 md:hover:text-primary",
                )}
              >
                <span className="flex-1">{label}</span>
                <ChevronRight className="size-4 text-muted-foreground md:hidden" />
              </a>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

function savedMessage(inRepository: boolean) {
  return inRepository ? "Saved and committed. Restart ai-os to apply it." : "Saved. Restart ai-os to apply it.";
}

function ConfigEditor({ text: initial, schema, inRepository }: { text: string; schema: Record<string, any>; inRepository: boolean }) {
  const [text, setText] = useState(initial);
  const queryClient = useQueryClient();
  const save = async () => {
    try {
      await api("PUT", "/api/settings/config", { text });
      void queryClient.invalidateQueries({ queryKey: ["restart-needed"] });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success(savedMessage(inRepository));
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const insert = async (path: string[], value: unknown) => {
    try {
      const result = await api<{ text: string }>("POST", "/api/settings/config-insert", { text, path, value });
      if (result.text === text) toast.info(`${path.join(".")} is in the file already.`);
      setText(result.text);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <>
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
    <Card>
      <CardHeader>
        <div>
          <CardTitle>aios.yaml</CardTitle>
          <CardDescription>
            {inRepository
              ? "In the configuration repository: every save is a commit, with History and branches like the rest. Checked before it is saved; applies at once, except channels, web, owner and collection access, which need a restart."
              : "Checked before it is saved; applies at once, except channels, web, owner and collection access, which need a restart."}
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <Textarea rows={24} className={editor} spellCheck={false} value={text} onChange={(e) => setText(e.target.value)} />
      </CardContent>
    </Card>
      <div className="xl:sticky xl:top-0 xl:max-h-[calc(100svh-8rem)] xl:overflow-y-auto">
        <ConfigReference schema={schema} onInsert={insert} />
      </div>
    </div>
    <SaveBar dirty={text !== initial} onSave={save} onDiscard={() => setText(initial)} />
    </>
  );
}
