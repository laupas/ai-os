import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CalendarClock, Pencil, Play, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ListView } from "@/components/list-view";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { HistoryButton } from "@/components/history-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Hint, Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type Schedule, type UserRef } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { useMe } from "@/lib/use-me";
import { when } from "@/lib/utils";

interface SchedulesData {
  schedules: Schedule[];
  users: UserRef[];
  /** Agents a run can go to directly, besides the orchestrator. */
  agents: string[];
}

// A datetime-local input holds local time without a zone; the API wants one.
const toLocalInput = (iso: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

export function SchedulesPage() {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { data, isLoading, error } = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api<SchedulesData>("GET", "/api/schedules"),
  });
  const [editing, setEditing] = useState<Schedule | "new" | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["schedules"] });
  const act = useMutation({
    mutationFn: async ({ s, action }: { s: Schedule; action: "toggle" | "run" | "delete" }) => {
      const path = `/api/schedules/${encodeURIComponent(s.id)}`;
      if (action === "toggle") return api("PATCH", path, { enabled: !s.enabled });
      if (action === "run") return api("POST", `${path}/run`);
      return api("DELETE", path);
    },
    onSuccess: (_, { action }) => {
      if (action === "run") toast.success("Started. It opens a new conversation for its user.");
      void refresh();
    },
    onError: (e) => toast.error(e.message),
  });
  const userName = (id: string) => data?.users.find((u) => u.id === id)?.name ?? "?";
  return (
    <Page>
      <PageHeader
        title="Schedules"
        description="Prompts ai-os runs by itself. Each run is a conversation that reaches its user on Slack and here."
        actions={
          <Button onClick={() => setEditing("new")}>
            <Plus /> New schedule
          </Button>
        }
      />
      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {data ? (
        <ListView
          items={data.schedules}
          keyOf={(s) => s.id}
          text={(s) => `${s.name} ${s.prompt} ${s.cron.join(" ")}`}
          facets={[
            { label: "states", value: (s) => (s.enabled ? "on" : "off"), options: ["on", "off"] },
            { label: "users", value: (s) => userName(s.user_id) },
            { label: "agents", value: (s) => s.agent ?? "orchestrator" },
          ]}
          empty="No schedules yet."
        >
          {(s) => (
          <Card className="p-4">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                <CalendarClock className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{s.name}</span>
                  {s.enabled ? (
                    <Badge variant="success">next {when(s.next_run)}</Badge>
                  ) : (
                    <Badge variant="secondary">off</Badge>
                  )}
                  <Badge variant="outline">for {userName(s.user_id)}</Badge>
                  {s.agent ? (
                    <Badge variant="outline" className="gap-1">
                      <Bot className="size-3" /> {s.agent}
                    </Badge>
                  ) : null}
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{s.prompt}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {s.cron.length ? (
                    s.cron.map((c) => (
                      <code key={c} className="rounded bg-muted px-1.5 py-0.5 text-xs">
                        {c}
                      </code>
                    ))
                  ) : (
                    <span className="text-xs text-muted-foreground">once, {when(s.once_at)}</span>
                  )}
                </div>
              </div>
              <Switch checked={s.enabled} onCheckedChange={() => act.mutate({ s, action: "toggle" })} aria-label="Enabled" />
            </div>
            <div className="mt-3 flex flex-wrap gap-2 border-t pt-3">
              <Button size="sm" variant="outline" onClick={() => setEditing(s)}>
                <Pencil /> Edit
              </Button>
              <Button size="sm" variant="outline" onClick={() => act.mutate({ s, action: "run" })}>
                <Play /> Run now
              </Button>
              <span className="flex-1" />
              <Button
                size="sm"
                variant="ghost"
                className="text-destructive"
                onClick={async () => {
                  if (await confirm({ title: `Delete ${s.name}?`, action: "Delete", destructive: true }))
                    act.mutate({ s, action: "delete" });
                }}
              >
                <Trash2 /> Delete
              </Button>
            </div>
          </Card>
          )}
        </ListView>
      ) : null}
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent side="right" className="gap-0 p-0">
          {editing !== null && data ? (
            <ScheduleForm
              schedule={editing === "new" ? null : editing}
              users={data.users}
              agents={data.agents}
              onDone={() => {
                setEditing(null);
                void refresh();
              }}
            />
          ) : null}
        </SheetContent>
      </Sheet>
    </Page>
  );
}

function ScheduleForm({
  schedule: s,
  users,
  agents,
  onDone,
}: {
  schedule: Schedule | null;
  users: UserRef[];
  agents: string[];
  onDone: () => void;
}) {
  const { data: me } = useMe();
  const defaultUser = users.find((u) => u.name === me?.name)?.id ?? users[0]?.id ?? "";
  const [form, setForm] = useState({
    name: s?.name ?? "",
    prompt: s?.prompt ?? "",
    timing: s?.once_at ? "once" : "cron",
    cron: s ? s.cron.join("\n") : "0 7 * * 1-5",
    once_at: toLocalInput(s?.once_at ?? null),
    timezone: s?.timezone ?? "Europe/Zurich",
    user_id: s?.user_id ?? defaultUser,
    agent: s?.agent ?? "",
    enabled: s?.enabled ?? true,
    max_lateness_minutes: String(s?.max_lateness_minutes ?? 60),
  });
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));
  const save = useMutation({
    mutationFn: () => {
      const once = form.timing === "once";
      if (once && !form.once_at) throw new Error("Pick when it should run.");
      const body = {
        name: form.name.trim(),
        prompt: form.prompt.trim(),
        cron: once ? [] : form.cron.split("\n").map((l) => l.trim()).filter(Boolean),
        once_at: once ? new Date(form.once_at).toISOString() : null,
        timezone: form.timezone.trim(),
        user_id: form.user_id,
        agent: form.agent || null,
        enabled: form.enabled,
        max_lateness_minutes: Number(form.max_lateness_minutes),
      };
      return s ? api("PUT", `/api/schedules/${encodeURIComponent(s.id)}`, body) : api("POST", "/api/schedules", body);
    },
    onSuccess: () => {
      toast.success(s ? "Saved." : "Created.");
      onDone();
    },
    onError: (e) => toast.error(e.message),
  });
  return (
    <form
      className="flex h-full flex-col"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <SheetHeader className="border-b">
        <SheetTitle>{s ? `Edit ${s.name}` : "New schedule"}</SheetTitle>
        <SheetDescription>Changing when it runs counts from now.</SheetDescription>
      </SheetHeader>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <Label>
          Name
          <Input required value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="morning-brief" />
        </Label>
        <Label>
          Prompt
          <Textarea required rows={5} value={form.prompt} onChange={(e) => set({ prompt: e.target.value })} />
          <Hint>Written as you would ask it; the run remembers nothing else.</Hint>
        </Label>
        <Label>
          Agent
          <NativeSelect value={form.agent} onChange={(e) => set({ agent: e.target.value })}>
            <option value="">Any agent (ai-os decides)</option>
            {[...new Set([...agents, ...(form.agent ? [form.agent] : [])])].map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </NativeSelect>
          <Hint>A chosen agent answers the prompt itself, with only its own tools; leave it on any agent for a prompt that needs several.</Hint>
        </Label>
        <Tabs value={form.timing} onValueChange={(timing) => set({ timing })}>
          <TabsList>
            <TabsTrigger value="cron">Repeat</TabsTrigger>
            <TabsTrigger value="once">Once</TabsTrigger>
          </TabsList>
        </Tabs>
        {form.timing === "cron" ? (
          <Label>
            Cron, one per line
            <Textarea rows={3} className="font-mono" value={form.cron} onChange={(e) => set({ cron: e.target.value })} />
            <Hint>
              minute hour day month weekday · <code>0 7 * * 1-5</code> is weekdays at 07:00
            </Hint>
          </Label>
        ) : (
          <Label>
            At
            <Input type="datetime-local" value={form.once_at} onChange={(e) => set({ once_at: e.target.value })} />
          </Label>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Label>
            For
            <NativeSelect value={form.user_id} onChange={(e) => set({ user_id: e.target.value })}>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </NativeSelect>
            <Hint>Runs as them and reaches them on Slack and here.</Hint>
          </Label>
          <Label>
            Time zone
            <Input value={form.timezone} onChange={(e) => set({ timezone: e.target.value })} />
          </Label>
          <Label>
            Skip if late by more than (min)
            <Input type="number" min={1} value={form.max_lateness_minutes} onChange={(e) => set({ max_lateness_minutes: e.target.value })} />
          </Label>
          <label className="flex items-center gap-3 text-sm font-medium sm:pt-6">
            <Switch checked={form.enabled} onCheckedChange={(enabled) => set({ enabled })} /> Enabled
          </label>
        </div>
      </div>
      <div className="flex gap-2 border-t p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <Button type="submit" disabled={save.isPending} className="flex-1 sm:flex-none">
          {s ? "Save" : "Create"}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        {s ? <HistoryButton kind="schedules" id={s.id} label={s.name} onRestored={onDone} /> : null}
      </div>
    </form>
  );
}
