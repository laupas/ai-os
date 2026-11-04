import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bot, ChevronRight, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { HistoryButton } from "@/components/history-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckRow } from "@/components/ui/checkbox";
import { Hint, Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api, type Agent, type AgentsData } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { go, href } from "@/lib/router";

// Which agent may use which built-in tool, skill and connector. ai-os enforces it in
// code on every tool call; a change applies to the next turn, no restart.

const MODELS = ["", "sonnet", "opus", "haiku"];

export const useAgents = () =>
  useQuery({ queryKey: ["agents"], queryFn: () => api<AgentsData>("GET", "/api/agents") });

function AgentBadges({ a }: { a: Agent }) {
  return (
    <>
      {a.fixed ? <Badge variant="secondary">fixed</Badge> : null}
      {!a.enabled ? <Badge variant="destructive">off</Badge> : null}
    </>
  );
}

export function AgentsPage({ name }: { name?: string }) {
  const { data, isLoading, error } = useAgents();
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} />;
  if (name) return <AgentForm data={data} name={name} />;
  const configured = new Set(data.connectors.map((c) => c.name));
  return (
    <Page>
      <PageHeader
        title="Agents"
        description="The orchestrator answers every turn and delegates to the enabled agents. Each agent may use only what is granted here."
        actions={
          <Button asChild>
            <a href={href("agents", "new")}>
              <Plus /> New agent
            </a>
          </Button>
        }
      />
      <div className="grid gap-3 md:grid-cols-2">
        {data.agents.map((a) => (
          <a key={a.name} href={href("agents", a.name)} className="group">
            <Card className="h-full p-4 transition-colors group-hover:bg-accent/40">
              <div className="flex items-start gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <Bot className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium">{a.name}</span>
                    <AgentBadges a={a} />
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{a.description}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-muted-foreground">
                    <Badge variant="outline">{a.model || "default model"}</Badge>
                    {a.builtin_tools.length ? <Badge variant="outline">{a.builtin_tools.length} tools</Badge> : null}
                    {a.skills.map((s) => (
                      <Badge key={s} variant="secondary">
                        {s}
                      </Badge>
                    ))}
                    {Object.entries(a.connectors).map(([c, t]) => (
                      <Badge key={c} variant={configured.has(c) ? "outline" : "destructive"} title={configured.has(c) ? "" : "not configured"}>
                        {c} · {t === null ? "all" : t.length}
                      </Badge>
                    ))}
                  </div>
                </div>
                <ChevronRight className="size-4 text-muted-foreground" />
              </div>
            </Card>
          </a>
        ))}
      </div>
    </Page>
  );
}

type Grant = { on: boolean; all: boolean; tools: string[]; text: string };

function AgentForm({ data, name }: { data: AgentsData; name: string }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const isNew = name === "new";
  const a: Agent | undefined = isNew
    ? { name: "", description: "", prompt: "", model: null, enabled: true, builtin_tools: [], skills: [], connectors: {}, fixed: false }
    : data.agents.find((x) => x.name === name);
  const isOrchestrator = a?.name === data.orchestrator;
  // Delegating is the orchestrator's job; Skill is granted by naming skills below.
  const builtins = data.builtin_tools.filter((t) => t !== "Skill" && (isOrchestrator || (t !== "Task" && t !== "Agent")));
  // A grant on a connector that is not configured stays visible, or saving would drop it.
  const known = new Set(data.connectors.map((c) => c.name));
  const connectorList = [
    ...data.connectors.map((c) => ({ ...c, missing: false })),
    ...Object.keys(a?.connectors ?? {})
      .filter((c) => !known.has(c))
      .map((c) => ({ name: c, enabled: false, tools: null as string[] | null, missing: true })),
  ];
  const [form, setForm] = useState(() => ({
    name: "",
    description: a?.description ?? "",
    prompt: a?.prompt ?? "",
    model: a?.model ?? "",
    enabled: a?.enabled ?? true,
    builtin: new Set(a?.builtin_tools ?? []),
    skills: new Set(a?.skills ?? []),
    grants: Object.fromEntries(
      connectorList.map((c) => {
        const granted = a?.connectors[c.name];
        return [c.name, { on: c.name in (a?.connectors ?? {}), all: granted === null, tools: granted ?? [], text: (granted ?? []).join(", ") }];
      }),
    ) as Record<string, Grant>,
  }));
  const toggle = (set: Set<string>, v: string, on: boolean) => {
    const next = new Set(set);
    if (on) next.add(v);
    else next.delete(v);
    return next;
  };
  const setGrant = (c: string, patch: Partial<Grant>) =>
    setForm((f) => ({ ...f, grants: { ...f.grants, [c]: { ...f.grants[c], ...patch } } }));

  const save = useMutation({
    mutationFn: async () => {
      if (!a) throw new Error("no such agent");
      const connectors: Record<string, string[] | null> = {};
      for (const c of connectorList) {
        const g = form.grants[c.name];
        if (!g.on) continue;
        const pick = c.tools && c.tools.length ? g.tools : g.text.split(",").map((t) => t.trim()).filter(Boolean);
        connectors[c.name] = g.all ? null : pick;
      }
      const body = {
        description: form.description.trim(),
        prompt: form.prompt,
        model: form.model || null,
        enabled: a.fixed || form.enabled,
        // Task is not offered outside the orchestrator, so keep whatever was there.
        builtin_tools: [...form.builtin].filter((t) => builtins.includes(t)).concat(a.builtin_tools.filter((t) => !builtins.includes(t))),
        skills: [...form.skills],
        connectors,
      };
      if (isNew) return api("POST", "/api/agents", { ...body, name: form.name.trim() });
      return api("PUT", `/api/agents/${encodeURIComponent(a.name)}`, body);
    },
    onSuccess: () => {
      toast.success("Saved. Applies to the next turn.");
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
      if (isNew) go("agents", form.name.trim());
    },
    onError: (e) => toast.error(e.message),
  });

  if (!a) return <ErrorBox error={new Error("no such agent")} />;
  const remove = async () => {
    const ok = await confirm({
      title: `Delete ${a.name}?`,
      body: "Conversations and schedules that go straight to it stop working.",
      action: "Delete",
      destructive: true,
    });
    if (!ok) return;
    try {
      await api("DELETE", `/api/agents/${encodeURIComponent(a.name)}`);
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
      go("agents");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <Page className="max-w-3xl">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild>
          <a href={href("agents")} aria-label="Back">
            <ArrowLeft />
          </a>
        </Button>
        <h1 className="text-xl font-semibold">{isNew ? "New agent" : a.name}</h1>
        <AgentBadges a={a} />
      </div>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Card>
          <CardContent className="space-y-4 pt-4 md:pt-5">
            {isNew ? (
              <Label>
                Name
                <Input required pattern="[a-z][a-z0-9-]*" placeholder="lower-case, e.g. travel" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </Label>
            ) : null}
            <Label>
              Description
              <Textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              <Hint>How the orchestrator decides when to delegate to it.</Hint>
            </Label>
            <div className="flex flex-wrap items-end gap-4">
              <Label className="w-44">
                Model
                <NativeSelect value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })}>
                  {[...new Set([...MODELS, a.model || ""])].map((m) => (
                    <option key={m} value={m}>
                      {m || "default"}
                    </option>
                  ))}
                </NativeSelect>
              </Label>
              <label className="flex h-9 items-center gap-3 text-sm font-medium">
                <Switch checked={a.fixed || form.enabled} disabled={a.fixed} onCheckedChange={(enabled) => setForm({ ...form, enabled })} />
                Enabled{a.fixed ? " (fixed)" : ""}
              </label>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Built-in tools</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-x-4 sm:grid-cols-3">
            {builtins.map((t) => (
              <CheckRow key={t} label={t} checked={form.builtin.has(t)} onChange={(on) => setForm({ ...form, builtin: toggle(form.builtin, t, on) })} />
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Skills</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-x-4 sm:grid-cols-3">
            {data.skills.length ? null : <span className="text-sm text-muted-foreground">none</span>}
            {data.skills.map((s) => (
              <CheckRow key={s.name} label={s.name} checked={form.skills.has(s.name)} onChange={(on) => setForm({ ...form, skills: toggle(form.skills, s.name, on) })} />
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Connectors</CardTitle>
            <CardDescription>Every tool, or only the ones ticked.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {connectorList.map((c) => {
              const g = form.grants[c.name];
              const tools = [...new Set([...(c.tools ?? []), ...g.tools])].sort();
              return (
                <div key={c.name} className="rounded-lg border p-3">
                  <CheckRow
                    label={<span className="font-medium">{c.name}</span>}
                    checked={g.on}
                    onChange={(on) => setGrant(c.name, { on })}
                    hint={c.missing ? "not configured" : c.enabled ? undefined : "switched off"}
                  />
                  {g.on ? (
                    <div className="mt-2 space-y-2 pl-6">
                      <div className="flex gap-4 text-sm">
                        <label className="flex items-center gap-2">
                          <input type="radio" checked={g.all} onChange={() => setGrant(c.name, { all: true })} /> every tool
                        </label>
                        <label className="flex items-center gap-2">
                          <input type="radio" checked={!g.all} onChange={() => setGrant(c.name, { all: false })} /> only these
                        </label>
                      </div>
                      {!g.all ? (
                        tools.length ? (
                          <div className="grid gap-x-4 sm:grid-cols-2">
                            {tools.map((t) => (
                              <CheckRow
                                key={t}
                                label={<code className="text-xs">{t}</code>}
                                checked={g.tools.includes(t)}
                                onChange={(on) => setGrant(c.name, { tools: on ? [...g.tools, t] : g.tools.filter((x) => x !== t) })}
                              />
                            ))}
                          </div>
                        ) : (
                          <Input
                            value={g.text}
                            onChange={(e) => setGrant(c.name, { text: e.target.value })}
                            placeholder="tool names, comma separated (none seen yet)"
                          />
                        )
                      ) : null}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Prompt</CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea rows={16} className="font-mono text-xs md:text-xs" spellCheck={false} value={form.prompt} onChange={(e) => setForm({ ...form, prompt: e.target.value })} />
          </CardContent>
        </Card>
        <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-2 border-t bg-background/95 px-4 py-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] backdrop-blur md:static md:mx-0 md:border-0 md:bg-transparent md:p-0">
          <Button type="submit" disabled={save.isPending}>
            {isNew ? "Create" : "Save"}
          </Button>
          {!isNew && !a.fixed ? (
            <Button type="button" variant="ghost" className="text-destructive" onClick={remove}>
              Delete
            </Button>
          ) : null}
          {isNew ? null : <HistoryButton kind="agents" id={a.name} />}
          <span className="text-xs text-muted-foreground">Applies to the next turn.</span>
        </div>
      </form>
    </Page>
  );
}
