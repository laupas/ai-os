import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Power, Save } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { prune, SchemaForm, type Values } from "@/components/schema-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { restartAiOs } from "@/lib/restart";
import { go } from "@/lib/router";
import { GitPanel } from "./git-page";
import { RolesPanel, UsersPanel } from "./settings-people";

const TABS = ["config", "yaml", "users", "roles", "git"];
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
          <TabsTrigger value="config">General</TabsTrigger>
          <TabsTrigger value="yaml">aios.yaml</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="roles">Roles</TabsTrigger>
          <TabsTrigger value="git">Git</TabsTrigger>
        </TabsList>
        <TabsContent value="git">
          <GitPanel />
        </TabsContent>
        <TabsContent value="config">
          {data.config_values ? (
            // Keyed by the file, so a save, or a change on the YAML tab, starts the form afresh.
            <ConfigForm key={data.config} schema={data.config_schema} initial={data.config_values} inRepository={Boolean(data.in_repository)} />
          ) : (
            <ErrorBox error="aios.yaml does not parse; fix it on the aios.yaml tab." />
          )}
        </TabsContent>
        <TabsContent value="yaml">
          <ConfigEditor key={data.config} text={data.config} inRepository={Boolean(data.in_repository)} />
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

// Read once at start and not again: copied into the connectors on the first start.
const HIDDEN = ["mcp_servers"];

function savedMessage(inRepository: boolean) {
  return inRepository ? "Saved and committed. Restart ai-os to apply it." : "Saved. Restart ai-os to apply it.";
}

/** aios.yaml as a form. Saving writes only what changed into the file, so its
 * comments stay; the YAML tab still has the whole text. */
function ConfigForm({ schema, initial, inRepository }: { schema: Record<string, any>; initial: Values; inRepository: boolean }) {
  const [values, setValues] = useState<Values>(initial);
  const queryClient = useQueryClient();
  const dirty = JSON.stringify(prune(values)) !== JSON.stringify(prune(initial));
  const save = async () => {
    try {
      await api("PUT", "/api/settings/config-values", { values: prune(values) });
      void queryClient.invalidateQueries({ queryKey: ["restart-needed"] });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success(savedMessage(inRepository));
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <div className="space-y-4">
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-3 rounded-xl border bg-background/95 p-3 backdrop-blur">
        <p className="min-w-0 flex-1 text-sm text-muted-foreground">
          An empty field uses its default, shown greyed out. Applies after a restart.
        </p>
        <Button variant="outline" onClick={() => setValues(initial)} disabled={!dirty}>
          Discard
        </Button>
        <Button onClick={save} disabled={!dirty}>
          <Save /> Save
        </Button>
      </div>
      <SchemaForm schema={schema} values={values} onChange={setValues} hidden={HIDDEN} />
    </div>
  );
}

function ConfigEditor({ text: initial, inRepository }: { text: string; inRepository: boolean }) {
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
  return (
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
  );
}
