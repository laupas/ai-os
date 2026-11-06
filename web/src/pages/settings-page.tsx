import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Power, Save } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { ConfigReference } from "@/components/config-reference";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { restartAiOs } from "@/lib/restart";
import { go } from "@/lib/router";
import { GitPanel } from "./git-page";
import { RepositoryPanel } from "./repository-panel";
import { RolesPanel, UsersPanel } from "./settings-people";

const TABS = ["config", "users", "roles", "repository", "git"];
import { api, type Settings } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";

const editor = "font-mono text-xs md:text-xs";

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
  return (
    <Page>
      <PageHeader
        title="Settings"
        actions={
          <Button variant="outline" onClick={restart}>
            <Power /> Restart ai-os
          </Button>
        }
      />
      <Tabs value={TABS.includes(tab ?? "") ? tab : "config"} onValueChange={(v) => go("settings", v)} className="space-y-4">
        <TabsList className="w-full sm:w-fit">
          <TabsTrigger value="config">aios.yaml</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="roles">Roles</TabsTrigger>
          <TabsTrigger value="repository">Repository</TabsTrigger>
          <TabsTrigger value="git">Branches</TabsTrigger>
        </TabsList>
        <TabsContent value="repository">
          <RepositoryPanel />
        </TabsContent>
        <TabsContent value="git">
          <GitPanel />
        </TabsContent>
        <TabsContent value="config">
          <ConfigEditor key={data.config} text={data.config} schema={data.config_schema} inRepository={Boolean(data.in_repository)} />
        </TabsContent>
        <TabsContent value="users">
          <UsersPanel data={data} />
        </TabsContent>
        <TabsContent value="roles">
          <RolesPanel data={data} />
        </TabsContent>
      </Tabs>
    </Page>
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
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
    <Card>
      <CardHeader className="flex-row items-center">
        <div className="flex-1">
          <CardTitle>aios.yaml</CardTitle>
          <CardDescription>
            {inRepository
              ? "In the configuration repository: every save is a commit, with History and branches like the rest. Checked before it is saved; applies after a restart."
              : "Checked before it is saved; applies after a restart."}
          </CardDescription>
        </div>
        <Button onClick={save} disabled={text === initial}>
          <Save /> Save
        </Button>
      </CardHeader>
      <CardContent>
        <Textarea rows={24} className={editor} spellCheck={false} value={text} onChange={(e) => setText(e.target.value)} />
      </CardContent>
    </Card>
      <div className="lg:sticky lg:top-0 lg:max-h-[calc(100svh-8rem)] lg:overflow-y-auto">
        <ConfigReference schema={schema} onInsert={insert} />
      </div>
    </div>
  );
}
