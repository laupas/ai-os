import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, CheckCircle2, Loader2, PlugZap, Plus, RefreshCw, Save, X, XCircle } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading } from "@/components/page";
import { SettingsFields, type Schema, type Values } from "@/components/schema-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckRow } from "@/components/ui/checkbox";
import { Hint, Input, Label, NativeSelect } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api, type AgentsData, type SettingsSections } from "@/lib/api";
import { cn } from "@/lib/utils";

// The aios.yaml sections the forms edit, one PUT per section. What is not set
// stays out of the file, so its default applies; each save is a commit and
// applies at once, except collection access, which the restart banner then offers.

type Section = SettingsSections["sections"][string];

const isPlain = (v: unknown): v is Values => typeof v === "object" && v !== null && !Array.isArray(v);

function useSections() {
  return useQuery({ queryKey: ["settings-sections"], queryFn: () => api<SettingsSections>("GET", "/api/settings/sections") });
}

/** The section's schema with only `keys` in it, for a form that shows part of it. */
function only(schema: Schema, keys: string[]): Schema {
  const target = schema.$ref ? schema.$defs[String(schema.$ref).split("/").pop()!] : schema;
  return { ...target, $defs: schema.$defs, properties: Object.fromEntries(keys.map((k) => [k, target.properties[k]])) };
}

/** Saves the sections that changed, in order; true when all went through. */
function useSave() {
  const queryClient = useQueryClient();
  return async (changes: Record<string, unknown>) => {
    try {
      for (const [key, value] of Object.entries(changes)) {
        await api("PUT", `/api/settings/sections/${key}`, { value: value ?? null });
      }
      void queryClient.invalidateQueries({ queryKey: ["settings-sections"] });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      void queryClient.invalidateQueries({ queryKey: ["restart-needed"] });
      toast.success("Saved and committed. Restart ai-os to apply it.");
      return true;
    } catch (e) {
      toast.error((e as Error).message);
      return false;
    }
  };
}

function SectionCard({ title, description, dirty, onSave, children }: { title: string; description: ReactNode; dirty: boolean; onSave: () => void; children: ReactNode }) {
  return (
    <Card className="max-w-3xl">
      <CardHeader className="flex-row items-start gap-3">
        <div className="flex-1">
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <Button onClick={onSave} disabled={!dirty}>
          <Save /> Save
        </Button>
      </CardHeader>
      <CardContent className="space-y-5">{children}</CardContent>
    </Card>
  );
}

function Loaded({ children }: { children: (sections: Record<string, Section>) => ReactNode }) {
  const { data, isLoading, error } = useSections();
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} />;
  return <>{children(data.sections)}</>;
}

/** Seconds stored, shown in a friendlier unit. */
function DurationField({ label, hint, seconds, fallback, unit, onChange }: { label: string; hint: string; seconds: number | undefined; fallback: number; unit: "minutes" | "hours"; onChange: (s: number | undefined) => void }) {
  const factor = unit === "minutes" ? 60 : 3600;
  const shown = (s: number) => String(Math.round((s / factor) * 100) / 100);
  return (
    <Label>
      {label}
      <span className="flex items-center gap-2">
        <Input
          type="number"
          min={0}
          step="any"
          className="w-32"
          placeholder={shown(fallback)}
          value={seconds === undefined ? "" : shown(seconds)}
          onChange={(e) => onChange(e.target.value === "" ? undefined : Math.round(Number(e.target.value) * factor))}
        />
        <span className="text-sm font-normal text-muted-foreground">{unit}</span>
      </span>
      <Hint>{hint}</Hint>
    </Label>
  );
}

// ─── General ────────────────────────────────────────────────────────────────

export function GeneralPanel() {
  return (
    <div className="space-y-3">
      <Loaded>{(s) => <GeneralForm key={JSON.stringify([s.timezone.value, s.triggers.value])} timezone={s.timezone} triggers={s.triggers} />}</Loaded>
      <Loaded>{(s) => <RateLimitsCard key={JSON.stringify(s.rate_limits.value)} section={s.rate_limits} />}</Loaded>
      <Loaded>{(s) => <ApiDocsCard section={s.api_docs} />}</Loaded>
      <VoiceCard />
    </div>
  );
}

function GeneralForm({ timezone, triggers }: { timezone: Section; triggers: Section }) {
  const [zone, setZone] = useState((timezone.value as string | null) ?? "");
  const [trig, setTrig] = useState<Values>(isPlain(triggers.value) ? triggers.value : {});
  const save = useSave();
  const zones = useMemo(() => {
    try {
      return Intl.supportedValuesOf("timeZone");
    } catch {
      return [];
    }
  }, []);
  const effective = zone || (timezone.schema.default as string);
  let now = "";
  try {
    now = new Date().toLocaleString(undefined, { timeZone: effective, weekday: "short", hour: "2-digit", minute: "2-digit" });
  } catch {
    now = "";
  }
  const zoneDirty = zone !== ((timezone.value as string | null) ?? "");
  const trigDirty = JSON.stringify(trig) !== JSON.stringify(isPlain(triggers.value) ? triggers.value : {});
  const onSave = () => {
    const changes: Record<string, unknown> = {};
    if (zoneDirty) changes.timezone = zone || null;
    if (trigDirty) changes.triggers = Object.keys(trig).length ? trig : null;
    void save(changes);
  };
  return (
    <SectionCard title="General" description="Time zone and the triggers. Applies at once." dirty={zoneDirty || trigDirty} onSave={onSave}>
      <Label>
        Time zone
        <Input list="aios-timezones" className="max-w-sm" placeholder={timezone.schema.default} value={zone} onChange={(e) => setZone(e.target.value.trim())} />
        <datalist id="aios-timezones">
          {zones.map((z) => (
            <option key={z} value={z} />
          ))}
        </datalist>
        <Hint>
          For triggers and the dates agents see. {now ? `Now there: ${now}.` : "Not a time zone this browser knows."}
        </Hint>
      </Label>
      <div className="space-y-2">
        <div className="text-sm font-medium">Triggers</div>
        <SettingsFields schema={only(triggers.schema, ["enabled", "tick_seconds"])} values={trig} onChange={setTrig} />
      </div>
    </SectionCard>
  );
}

const LIMITS: { key: string; label: string; hint: string }[] = [
  { key: "messages_per_minute", label: "Messages a minute", hint: "Per person: messages, voice notes and trigger runs, what costs tokens. A group can set its own under Groups." },
  { key: "reads_per_minute", label: "Reads a minute", hint: "Per person: everything else that only reads." },
  { key: "writes_per_minute", label: "Changes a minute", hint: "Per person: everything else that changes something." },
  { key: "login_per_minute", label: "Sign-in requests a minute", hint: "Per address, before signing in: the login page, single sign-on, OAuth returns." },
  { key: "hooks_per_minute", label: "Webhook calls a minute", hint: "Per address: trigger webhooks." },
  { key: "hook_failures", label: "Wrong webhook tokens before blocking", hint: "Per address." },
  { key: "hook_block_minutes", label: "Block for (minutes)", hint: "How long an address that kept sending wrong tokens is refused." },
];

/** How often the console answers before "too many requests" (429). Applies at once. */
function RateLimitsCard({ section }: { section: Section }) {
  const queryClient = useQueryClient();
  const initial: Values = isPlain(section.value) ? section.value : {};
  const [values, setValues] = useState<Values>(initial);
  const target = section.schema.$ref ? section.schema.$defs[String(section.schema.$ref).split("/").pop()!] : section.schema;
  const defaults = (key: string) => String(target.properties?.[key]?.default ?? "");
  const enabled = values.enabled !== false;
  const dirty = JSON.stringify(values) !== JSON.stringify(initial);
  const save = async () => {
    try {
      const clean = Object.fromEntries(Object.entries(values).filter(([, v]) => v !== undefined && v !== ""));
      await api("PUT", "/api/settings/sections/rate_limits", { value: Object.keys(clean).length ? clean : null });
      await queryClient.invalidateQueries({ queryKey: ["settings-sections"] });
      toast.success("Rate limits saved. They apply at once.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <SectionCard
      title="Rate limits"
      description="Who asks too often gets 'too many requests' (429) until the minute has passed. Counted per person after signing in, per address before. Applies at once."
      dirty={dirty}
      onSave={() => void save()}
    >
      <label className="flex items-center gap-3 text-sm font-medium">
        <Switch checked={enabled} onCheckedChange={(on) => setValues((v) => ({ ...v, enabled: on ? undefined : false }))} /> Limit requests
      </label>
      {enabled ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {LIMITS.map((l) => (
            <Label key={l.key}>
              {l.label}
              <Input
                type="number"
                min={1}
                className="w-32"
                placeholder={defaults(l.key)}
                value={values[l.key] === undefined ? "" : String(values[l.key])}
                onChange={(e) => setValues((v) => ({ ...v, [l.key]: e.target.value === "" ? undefined : Number(e.target.value) }))}
              />
              <Hint>{l.hint}</Hint>
            </Label>
          ))}
        </div>
      ) : null}
    </SectionCard>
  );
}

/** One switch: the API's OpenAPI description and a Swagger page, for administrators. Applies at once. */
function ApiDocsCard({ section }: { section: Section }) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const on = isPlain(section.value) && section.value.enabled === true;
  const toggle = async (enabled: boolean) => {
    setBusy(true);
    try {
      await api("PUT", "/api/settings/sections/api_docs", { value: enabled ? { enabled: true } : null });
      await queryClient.invalidateQueries({ queryKey: ["settings-sections"] });
      toast.success(enabled ? "API docs are on." : "API docs are off.");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card className="max-w-3xl">
      <CardHeader className="flex-row items-start gap-3">
        <div className="flex-1">
          <CardTitle>API docs</CardTitle>
          <CardDescription>
            Every route of the console's API, with a Swagger page to read and try them (OpenAPI 3.1). Only administrators see it. Applies at once.
          </CardDescription>
        </div>
        <Switch checked={on} disabled={busy} onCheckedChange={(v) => void toggle(v)} aria-label="API docs" />
      </CardHeader>
      {on ? (
        <CardContent className="flex flex-wrap gap-2">
          <Button asChild variant="outline" size="sm">
            <a href="/api/docs" target="_blank" rel="noreferrer">
              <BookOpen /> Open the API docs
            </a>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <a href="/api/openapi.json" target="_blank" rel="noreferrer">
              openapi.json
            </a>
          </Button>
        </CardContent>
      ) : null}
    </Card>
  );
}

// ─── Agents ─────────────────────────────────────────────────────────────────

const MODELS = [
  { value: "", label: "Claude Code default" },
  { value: "opus", label: "Opus: most capable" },
  { value: "sonnet", label: "Sonnet: balanced" },
  { value: "haiku", label: "Haiku: fastest, cheapest" },
];

/** Built-in Claude Code tools that may be offered. Never Bash: the process
 * environment holds every secret, and the server refuses it too. */
const BUILTIN_TOOLS: [string, string][] = [
  ["Task", "hand work to another agent"],
  ["Skill", "use the skills it was given"],
  ["TodoWrite", "keep a to-do list during a turn"],
  ["WebSearch", "search the web"],
  ["WebFetch", "read a web page"],
  ["Read", "read files"],
  ["Grep", "search in files"],
  ["Glob", "find files by name"],
  ["Edit", "change files"],
  ["Write", "write files"],
];
// Only tools FileAccessRule checks; NotebookEdit is not one, so it is not offered.
const FILE_TOOLS = new Set(["Read", "Grep", "Glob", "Edit", "Write"]);

export function AgentsSettingsPanel() {
  return <Loaded>{(s) => <AgentsForm key={JSON.stringify(s.agent.value)} section={s.agent} />}</Loaded>;
}

function AgentsForm({ section }: { section: Section }) {
  // Everything set is kept, `auth` too: the Claude tab owns that one.
  const initial = isPlain(section.value) ? section.value : {};
  const [values, setValues] = useState<Values>(initial);
  const save = useSave();
  const schema = section.schema.$ref ? section.schema.$defs[String(section.schema.$ref).split("/").pop()!] : section.schema;
  const defaults: string[] = schema.properties.builtin_tools.default;
  const tools = (values.builtin_tools as string[] | undefined) ?? defaults;
  const model = (values.model as string | undefined) ?? "";
  const custom = model !== "" && !MODELS.some((m) => m.value === model);
  const set = (key: string, value: unknown) =>
    setValues((v) => {
      const next = { ...v };
      if (value === undefined) delete next[key];
      else next[key] = value;
      return next;
    });
  const toggle = (tool: string, on: boolean) => {
    const next = on ? [...tools, tool] : tools.filter((t) => t !== tool);
    const ordered = BUILTIN_TOOLS.map(([t]) => t).filter((t) => next.includes(t));
    const extra = next.filter((t) => !ordered.includes(t));
    const all = [...ordered, ...extra];
    set("builtin_tools", JSON.stringify([...all].sort()) === JSON.stringify([...defaults].sort()) ? undefined : all);
  };
  const dirty = JSON.stringify(values) !== JSON.stringify(initial);
  const offered = [...BUILTIN_TOOLS, ...tools.filter((t) => !BUILTIN_TOOLS.some(([b]) => b === t)).map((t): [string, string] => [t, ""])];
  return (
    <SectionCard
      title="Agents"
      description="What applies to every agent: the model when an agent names none, the built-in tools any agent may be given, and how long a turn may run. Applies from the next turn."
      dirty={dirty}
      onSave={() => void save({ agent: Object.keys(values).length ? values : null })}
    >
      <Label>
        Default model
        <span className="flex flex-wrap gap-2">
          <NativeSelect className="w-auto min-w-56" value={custom ? "custom" : model} onChange={(e) => set("model", e.target.value === "custom" ? "claude-" : e.target.value || undefined)}>
            {MODELS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
            <option value="custom">Another model id…</option>
          </NativeSelect>
          {custom ? <Input className="w-64 font-mono" value={model} onChange={(e) => set("model", e.target.value.trim() || undefined)} /> : null}
        </span>
        <Hint>Used by agents that do not set their own model on the Agents page.</Hint>
      </Label>

      <div className="space-y-2">
        <div className="text-sm font-medium">Built-in tools agents may be given</div>
        <Hint>
          The most any agent can get; each agent is then given some of these on the Agents page. Bash is never offered: the process
          environment holds the secrets. The file tools only reach the folders under <code>files</code> in aios.yaml.
        </Hint>
        <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
          {offered.map(([tool, what]) => (
            <CheckRow
              key={tool}
              checked={tools.includes(tool)}
              onChange={(on) => toggle(tool, on)}
              label={
                <span>
                  <code className="text-xs">{tool}</code>
                  {what ? <span className="text-muted-foreground"> · {what}</span> : null}
                  {FILE_TOOLS.has(tool) ? <Badge variant="outline" className="ml-1.5">files</Badge> : null}
                </span>
              }
            />
          ))}
        </div>
        {values.builtin_tools === undefined ? <Hint>The default set.</Hint> : null}
      </div>

      <DurationField
        label="Turn time limit"
        hint="A turn still running after this long is stopped. Time spent waiting for an approval does not count."
        seconds={values.turn_timeout_seconds as number | undefined}
        fallback={schema.properties.turn_timeout_seconds.default}
        unit="minutes"
        onChange={(s) => set("turn_timeout_seconds", s)}
      />
    </SectionCard>
  );
}

// ─── Approvals ──────────────────────────────────────────────────────────────

export function ApprovalsSettingsPanel() {
  const agents = useQuery({ queryKey: ["agents"], queryFn: () => api<AgentsData>("GET", "/api/agents") });
  // Every tool name ai-os knows: a connector's are known once it has run, here or in a turn.
  const known = useMemo(() => {
    const names = new Set<string>();
    for (const c of agents.data?.connectors ?? []) for (const t of c.tools ?? []) names.add(`mcp__${c.name}__${t}`);
    return names;
  }, [agents.data]);
  const connectors = agents.data?.connectors.map((c) => c.name) ?? [];
  return (
    <Loaded>
      {(s) => (
        <div className="space-y-3">
          <ToolLookup data={agents.data} />
          <ApprovalsForm key={JSON.stringify(s.approval.value)} section={s.approval} known={known} connectors={connectors} />
        </div>
      )}
    </Loaded>
  );
}

/** Starts the connectors whose tools are not known yet (or all of them, to refresh),
 * the way the Connectors page's Start does, so their tools can be picked below. */
function ToolLookup({ data }: { data: AgentsData | undefined }) {
  const queryClient = useQueryClient();
  const [running, setRunning] = useState<string[]>([]);
  const enabled = (data?.connectors ?? []).filter((c) => c.enabled && c.name !== "aios");
  const unknown = enabled.filter((c) => !c.tools?.length);
  const targets = unknown.length ? unknown : enabled;
  if (!enabled.length) return null;
  const look = async () => {
    setRunning(targets.map((c) => c.name));
    const results = await Promise.allSettled(
      targets.map(async (c) => {
        try {
          const r = await api<{ status: string; error: string | null }>("POST", `/api/connectors/${encodeURIComponent(c.name)}/start`);
          if (r.status !== "connected") throw new Error(`${c.name}: ${r.error ?? r.status}`);
        } finally {
          setRunning((left) => left.filter((n) => n !== c.name));
        }
      }),
    );
    void queryClient.invalidateQueries({ queryKey: ["agents"] });
    const failed = results.flatMap((r) => (r.status === "rejected" ? [(r.reason as Error).message] : []));
    if (failed.length) toast.error(`Not started: ${failed.join("; ")}`);
    else toast.success("Tools looked up.");
  };
  return (
    <Card className="flex max-w-3xl flex-wrap items-center gap-3 p-4">
      <p className="min-w-0 flex-1 text-sm text-muted-foreground">
        {running.length
          ? `Starting ${running.join(", ")}…`
          : unknown.length
            ? `The tools of ${unknown.map((c) => c.name).join(", ")} are not known yet: a connector's tools are learnt when it runs.`
            : "Every connector's tools are known."}
      </p>
      <Button variant="outline" onClick={look} disabled={running.length > 0}>
        {running.length ? <Loader2 className="animate-spin" /> : <RefreshCw />} {unknown.length ? "Look up tools" : "Refresh tools"}
      </Button>
    </Card>
  );
}

function ApprovalsForm({ section, known, connectors }: { section: Section; known: Set<string>; connectors: string[] }) {
  const initial = isPlain(section.value) ? section.value : {};
  const [values, setValues] = useState<Values>(initial);
  const save = useSave();
  const schema = section.schema.$ref ? section.schema.$defs[String(section.schema.$ref).split("/").pop()!] : section.schema;
  const list = (key: "always" | "deny") => (values[key] as string[] | undefined) ?? [];
  const set = (key: string, value: unknown) =>
    setValues((v) => {
      const next = { ...v };
      if (value === undefined || (Array.isArray(value) && value.length === 0)) delete next[key];
      else next[key] = value;
      return next;
    });
  const dirty = JSON.stringify(values) !== JSON.stringify(initial);
  return (
    <SectionCard
      title="Approvals"
      description="Tools that need a person's Yes every time, and tools that are never allowed, whichever agent asks. Applies at once."
      dirty={dirty}
      onSave={() => void save({ approval: Object.keys(values).length ? values : null })}
    >
      <ToolList
        title="Always ask"
        hint="An administrator is asked in Slack or the console before each call."
        value={list("always")}
        other={list("deny")}
        known={known}
        connectors={connectors}
        onChange={(v) => set("always", v)}
      />
      <ToolList
        title="Never allow"
        hint="Refused outright, e.g. a connector's send or delete tools."
        value={list("deny")}
        other={list("always")}
        known={known}
        connectors={connectors}
        onChange={(v) => set("deny", v)}
      />
      <DurationField
        label="Answer within"
        hint="An approval nobody answers is taken as No after this long."
        seconds={values.timeout_seconds as number | undefined}
        fallback={schema.properties.timeout_seconds.default}
        unit="hours"
        onChange={(s) => set("timeout_seconds", s)}
      />
    </SectionCard>
  );
}

function ToolList({
  title,
  hint,
  value,
  other,
  known,
  connectors,
  onChange,
}: {
  title: string;
  hint: string;
  value: string[];
  other: string[];
  known: Set<string>;
  connectors: string[];
  onChange: (v: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const id = `tools-${title.replace(/\W/g, "")}`;
  const add = () => {
    const name = draft.trim();
    if (!name || value.includes(name)) return setDraft("");
    onChange([...value, name]);
    setDraft("");
  };
  // A tool of a connector that no longer exists, or not seen yet: still kept, but said.
  const state = (name: string) => {
    if (known.has(name)) return null;
    const server = name.startsWith("mcp__") ? name.slice(5).split("__")[0] : null;
    if (server && !connectors.includes(server)) return "no such connector";
    return "not seen yet";
  };
  const offered = [...known].filter((t) => !value.includes(t) && !other.includes(t)).sort();
  return (
    <div className="space-y-2">
      <div className="text-sm font-medium">{title}</div>
      <Hint>{hint}</Hint>
      <div className="flex flex-wrap gap-1.5">
        {value.length === 0 ? <span className="text-sm text-muted-foreground">none</span> : null}
        {value.map((name) => (
          <span key={name} className="inline-flex items-center gap-1 rounded-md border bg-muted/40 py-0.5 pr-1 pl-2 font-mono text-xs">
            {name}
            {state(name) ? (
              <Badge variant="warning" className="font-sans">
                {state(name)}
              </Badge>
            ) : null}
            {other.includes(name) ? (
              <Badge variant="destructive" className="font-sans">
                also in the other list
              </Badge>
            ) : null}
            <button type="button" className="rounded p-0.5 text-muted-foreground hover:text-foreground" onClick={() => onChange(value.filter((v) => v !== name))} aria-label={`Remove ${name}`}>
              <X className="size-3.5" />
            </button>
          </span>
        ))}
      </div>
      <form
        className="flex max-w-xl gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
      >
        <Input list={id} className="font-mono text-xs md:text-xs" placeholder="mcp__connector__tool" value={draft} onChange={(e) => setDraft(e.target.value)} />
        <datalist id={id}>
          {offered.map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>
        <Button type="submit" variant="outline" disabled={!draft.trim()}>
          <Plus /> Add
        </Button>
      </form>
    </div>
  );
}

// ─── Voice notes ────────────────────────────────────────────────────────────

interface VoiceField {
  variable: string;
  secret: boolean;
  source: "variable" | "environment" | null;
  value: string | null;
}

function VoiceCard() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["settings-voice"], queryFn: () => api<{ fields: VoiceField[] }>("GET", "/api/settings/voice") });
  const [key, setKey] = useState("");
  const [language, setLanguage] = useState<string | null>(null);
  const [checked, setChecked] = useState<{ ok: boolean; detail: string } | null>(null);
  const [busy, setBusy] = useState(false);
  if (!data) return null;
  const field = (name: string) => data.fields.find((f) => f.variable === name)!;
  const k = field("OPENAI_API_KEY");
  const l = field("AIOS_TRANSCRIBE_LANGUAGE");
  const shownLanguage = language ?? (l.source === "variable" ? (l.value ?? "") : "");
  const values = { OPENAI_API_KEY: key.trim(), AIOS_TRANSCRIBE_LANGUAGE: language?.trim() ?? "" };
  const dirty = Boolean(values.OPENAI_API_KEY || (language !== null && language.trim() !== (l.value ?? "")));
  const source = (f: VoiceField) =>
    f.source === "variable" ? <Badge variant="success">set</Badge> : f.source === "environment" ? <Badge variant="warning">from the environment</Badge> : <Badge variant="secondary">not set</Badge>;
  const save = async () => {
    try {
      const state = await api<{ fields: VoiceField[] }>("PUT", "/api/settings/voice", { values });
      queryClient.setQueryData(["settings-voice"], state);
      setKey("");
      setLanguage(null);
      toast.success("Saved. The next voice note uses it.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const check = async () => {
    setBusy(true);
    try {
      setChecked(await api<{ ok: boolean; detail: string }>("POST", "/api/settings/voice/check", { values }));
    } catch (e) {
      setChecked({ ok: false, detail: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <SectionCard
      title="Voice notes"
      description="Voice notes sent in Slack or recorded in the console are written out by OpenAI's Whisper. Applies to the next note, no restart needed."
      dirty={dirty}
      onSave={() => void save()}
    >
      <Label>
        <span className="flex items-center gap-2">
          OpenAI API key <code className="text-xs font-normal text-muted-foreground">OPENAI_API_KEY</code> {source(k)}
        </span>
        <Input
          type="password"
          autoComplete="off"
          className="font-mono"
          placeholder={k.source === "variable" ? "Set. Leave empty to keep it; type to replace it." : k.source === "environment" ? "Taken from the environment. Type to set it here instead." : "sk-…"}
          value={key}
          onChange={(e) => {
            setKey(e.target.value);
            setChecked(null);
          }}
        />
        <Hint>Without one, voice notes are not understood. platform.openai.com → API keys.</Hint>
      </Label>
      <Label>
        <span className="flex items-center gap-2">
          Language <code className="text-xs font-normal text-muted-foreground">AIOS_TRANSCRIBE_LANGUAGE</code> {source(l)}
        </span>
        <Input className="w-40 font-mono" placeholder={l.source === "environment" ? (l.value ?? "") : "e.g. de"} value={shownLanguage} onChange={(e) => setLanguage(e.target.value)} />
        <Hint>Two letters (de, en, fr…). Empty: Whisper finds out itself, which sometimes guesses wrong on short notes.</Hint>
      </Label>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" onClick={check} disabled={busy}>
          {busy ? <Loader2 className="animate-spin" /> : <PlugZap />} Test key
        </Button>
        {checked ? (
          <span className={cn("flex items-center gap-1.5 text-sm", checked.ok ? "text-success" : "text-destructive")}>
            {checked.ok ? <CheckCircle2 className="size-4" /> : <XCircle className="size-4" />} {checked.detail}
          </span>
        ) : null}
      </div>
    </SectionCard>
  );
}

// ─── Data access ────────────────────────────────────────────────────────────

const ACCESS: Record<string, string> = { none: "No access", read: "Read", write: "Read and write" };
const COLLECTION_HINT: Record<string, string> = {
  users: "people ai-os knows, their accounts and notes",
  roles: "roles and their permissions",
  conversations: "chats and their messages",
  approvals: "questions asked and answered",
  memories: "what agents keep for later",
  triggers: "runs started on time or by webhook",
};

export function DataAccessPanel() {
  const { data, isLoading, error } = useSections();
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} />;
  const section = data.sections.collection_access;
  return <DataAccessForm key={JSON.stringify(section.value)} section={section} defaults={data.collections ?? {}} />;
}

function DataAccessForm({ section, defaults }: { section: Section; defaults: Record<string, string> }) {
  const initial = (isPlain(section.value) ? section.value : {}) as Record<string, string>;
  const [values, setValues] = useState<Record<string, string>>(initial);
  const save = useSave();
  const dirty = JSON.stringify(values) !== JSON.stringify(initial);
  return (
    <SectionCard
      title="Data access"
      description="How far agents may reach into ai-os's own data through the data tools, whatever agent asks. Agents, skills, connectors and variables are never reachable: an agent that could change those could grant itself anything. Applies after a restart."
      dirty={dirty}
      onSave={() => void save({ collection_access: Object.keys(values).length ? values : null })}
    >
      <div className="divide-y rounded-lg border">
        {Object.entries(defaults).map(([name, fallback]) => (
          <div key={name} className="flex flex-wrap items-center gap-3 px-3 py-2">
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{name}</div>
              <div className="text-xs text-muted-foreground">{COLLECTION_HINT[name] ?? ""}</div>
            </div>
            <NativeSelect
              className="w-auto min-w-44"
              value={values[name] ?? ""}
              onChange={(e) =>
                setValues((v) => {
                  const next = { ...v };
                  if (e.target.value) next[name] = e.target.value;
                  else delete next[name];
                  return next;
                })
              }
            >
              <option value="">default: {ACCESS[fallback] ?? fallback}</option>
              {Object.entries(ACCESS).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}
