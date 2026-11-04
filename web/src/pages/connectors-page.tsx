import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, LogOut, Pencil, Play, Plug, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { HistoryButton } from "@/components/history-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Hint, Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type Connector, type ProbeResult } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { href } from "@/lib/router";
import { when } from "@/lib/utils";

type Config = Record<string, unknown>;

export function ConnectorsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["connectors"],
    queryFn: () => api<{ connectors: Connector[] }>("GET", "/api/connectors"),
  });
  const [editing, setEditing] = useState<Connector | "new" | null>(null);
  useSignInResult();
  return (
    <Page className="max-w-3xl">
      <PageHeader
        title="Connectors"
        description="MCP servers ai-os starts for a turn. Which agent may use one, and which of its tools, is set on the agent."
        actions={
          <Button onClick={() => setEditing("new")}>
            <Plus /> New connector
          </Button>
        }
      />
      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      <div className="grid gap-3">
        {data?.connectors.map((c) => (
          <ConnectorCard key={c.id} connector={c} onEdit={() => setEditing(c)} />
        ))}
      </div>
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent side="right" className="gap-0 p-0 sm:max-w-xl">
          {editing !== null ? <ConnectorForm connector={editing === "new" ? null : editing} onDone={() => setEditing(null)} /> : null}
        </SheetContent>
      </Sheet>
    </Page>
  );
}

function Status({ c }: { c: Connector }) {
  if (c.builtin) return <Badge variant="success">built in</Badge>;
  if (!c.enabled) return <Badge variant="destructive">switched off</Badge>;
  // What the connector last did decides; not having signed in here is only a hint
  // while nothing is known, since a server may hold a sign-in of its own.
  if (c.status === "needs-auth") return <Badge variant="warning">needs sign-in</Badge>;
  if (!c.status) return c.sign_in && !c.sign_in.signed_in ? <Badge variant="warning">not signed in</Badge> : <Badge variant="secondary">not started yet</Badge>;
  return <Badge variant={c.status === "connected" ? "success" : "destructive"}>{c.status}</Badge>;
}

/** What the server is, in a few words: its command or its address. */
function target(config: Config | null): string {
  if (!config) return "";
  if (typeof config.url === "string") return config.url;
  const args = Array.isArray(config.args) ? config.args.join(" ") : "";
  return `${config.command ?? ""} ${args}`.trim();
}

function ConnectorCard({ connector: c, onEdit }: { connector: Connector; onEdit: () => void }) {
  const queryClient = useQueryClient();
  const [showTools, setShowTools] = useState(false);
  const [starting, setStarting] = useState(false);
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const start = async () => {
    setStarting(true);
    setProbe(null);
    try {
      const result = await api<ProbeResult>("POST", `/api/connectors/${encodeURIComponent(c.id)}/start`);
      setProbe(result);
      void queryClient.invalidateQueries({ queryKey: ["connectors"] });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setStarting(false);
    }
  };
  const toggle = async (enabled: boolean) => {
    try {
      await api("PUT", `/api/connectors/${encodeURIComponent(c.id)}`, { description: c.description, config: c.config, enabled });
      void queryClient.invalidateQueries({ queryKey: ["connectors"] });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <Plug className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{c.id}</span>
            <Status c={c} />
          </div>
          {c.description ? <p className="mt-1 text-sm text-muted-foreground">{c.description}</p> : null}
          {c.missing_variables?.length ? (
            <p className="mt-1 text-xs text-destructive">
              Missing{" "}
              {c.missing_variables.map((n, i) => (
                <span key={n}>
                  {i ? ", " : ""}
                  <a className="underline" href={href("variables")}>
                    {n}
                  </a>
                </span>
              ))}
              : set {c.missing_variables.length === 1 ? "it" : "them"} under Variables.
            </p>
          ) : null}
          {c.config ? <code className="mt-1 block truncate text-xs text-muted-foreground">{target(c.config)}</code> : null}
          <p className="mt-1 text-xs text-muted-foreground">
            Used by{" "}
            {c.used_by.length
              ? c.used_by.map((a, i) => (
                  <span key={a}>
                    {i ? ", " : ""}
                    <a className="underline" href={href("agents", a)}>
                      {a}
                    </a>
                  </span>
                ))
              : "no agent"}
            {" · "}
            <button className="underline" onClick={() => setShowTools(!showTools)}>
              {c.tools.length} tool{c.tools.length === 1 ? "" : "s"}
            </button>
            {c.seen_at ? ` · seen ${when(c.seen_at)}` : ""}
          </p>
        </div>
        {c.builtin ? null : <Switch checked={c.enabled} onCheckedChange={toggle} aria-label="Enabled" />}
      </div>
      {showTools ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {c.tools.length ? (
            c.tools.map((t) => (
              <code key={t} className="rounded bg-muted px-1.5 py-0.5 text-xs">
                {t}
              </code>
            ))
          ) : (
            <span className="text-xs text-muted-foreground">Known once a turn has started it.</span>
          )}
        </div>
      ) : null}
      {probe ? (
        <div
          className={`mt-3 rounded-md border p-2 text-xs ${probe.status === "connected" ? "border-success/40 bg-success/10" : "border-destructive/40 bg-destructive/10"}`}
        >
          <div className="font-medium">
            {probe.status === "connected"
              ? `Started in ${probe.seconds}s${probe.server ? ` · ${probe.server}` : ""} · ${probe.tools.length} tool${probe.tools.length === 1 ? "" : "s"}`
              : `${probe.status} after ${probe.seconds}s`}
          </div>
          {probe.error ? <div className="mt-1 break-words font-mono text-destructive">{probe.error}</div> : null}
          {probe.status === "connected" ? (
            <div className="mt-1 text-muted-foreground">It started and answered. Whether each tool works shows on its first real use.</div>
          ) : null}
        </div>
      ) : !starting && c.error ? (
        <div className="mt-2 break-words font-mono text-xs text-destructive">{c.error}</div>
      ) : null}
      {c.builtin ? null : (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3">
          <Button size="sm" variant="outline" onClick={onEdit}>
            <Pencil /> Edit
          </Button>
          <Button size="sm" variant="outline" onClick={start} disabled={starting}>
            {starting ? <Loader2 className="animate-spin" /> : <Play />} {starting ? "Starting…" : "Start"}
          </Button>
          {c.sign_in ? <SignIn c={c} /> : null}
        </div>
      )}
    </Card>
  );
}

// Key=value lines for env, "Name: value" lines for headers.
const toLines = (o: unknown, sep: string) =>
  o && typeof o === "object"
    ? Object.entries(o as Record<string, unknown>)
        .map(([k, v]) => `${k}${sep}${v}`)
        .join("\n")
    : "";
function fromLines(text: string, sep: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const at = line.indexOf(sep.trim());
    if (!line.trim()) continue;
    if (at < 1) throw new Error(`"${line.trim()}" needs a ${sep.trim()}`);
    out[line.slice(0, at).trim()] = line.slice(at + 1).trim();
  }
  return out;
}

function ConnectorForm({ connector: c, onDone }: { connector: Connector | null; onDone: () => void }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const original: Config = c?.config ?? {};
  const [name, setName] = useState("");
  const [description, setDescription] = useState(c?.description ?? "");
  const [enabled, setEnabled] = useState(c?.enabled ?? true);
  const [kind, setKind] = useState(typeof original.url === "string" ? "url" : "command");
  const [command, setCommand] = useState(String(original.command ?? ""));
  const [args, setArgs] = useState(Array.isArray(original.args) ? original.args.join("\n") : "");
  const [env, setEnv] = useState(toLines(original.env, "="));
  const [url, setUrl] = useState(String(original.url ?? ""));
  const [transport, setTransport] = useState(original.type === "sse" ? "sse" : "http");
  const [headers, setHeaders] = useState(toLines(original.headers, ": "));
  const [raw, setRaw] = useState(false);
  const [json, setJson] = useState(JSON.stringify(original, null, 2));
  const [busy, setBusy] = useState(false);

  // The fields on top of the original, so a key this form does not know survives.
  const build = (): Config => {
    if (raw) {
      try {
        return JSON.parse(json);
      } catch (e) {
        throw new Error(`Not valid JSON: ${(e as Error).message}`);
      }
    }
    const config: Config = { ...original };
    for (const key of ["command", "args", "env", "url", "type", "headers"]) delete config[key];
    if (kind === "command") {
      if (!command.trim()) throw new Error("Give the command to start.");
      config.command = command.trim();
      const list = args.split("\n").map((a) => a.trim()).filter(Boolean);
      if (list.length) config.args = list;
      const vars = fromLines(env, "=");
      if (Object.keys(vars).length) config.env = vars;
    } else {
      if (!url.trim()) throw new Error("Give the server's address.");
      config.type = transport;
      config.url = url.trim();
      const h = fromLines(headers, ": ");
      if (Object.keys(h).length) config.headers = h;
    }
    return config;
  };
  const switchRaw = (on: boolean) => {
    try {
      if (on) setJson(JSON.stringify(build(), null, 2));
      setRaw(on);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const save = async () => {
    setBusy(true);
    try {
      const body = { description: description.trim(), config: build(), enabled };
      if (c) await api("PUT", `/api/connectors/${encodeURIComponent(c.id)}`, body);
      else await api("POST", "/api/connectors", { ...body, name: name.trim() });
      toast.success(c ? "Saved. Applies to the next turn." : "Added. Now grant it to an agent.");
      void queryClient.invalidateQueries({ queryKey: ["connectors"] });
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!c) return;
    if (!(await confirm({ title: `Delete ${c.id}?`, body: "Agents keep their grant, which then does nothing.", action: "Delete", destructive: true })))
      return;
    try {
      await api("DELETE", `/api/connectors/${encodeURIComponent(c.id)}`);
      void queryClient.invalidateQueries({ queryKey: ["connectors"] });
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <form
      className="flex h-full flex-col"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <SheetHeader className="border-b">
        <SheetTitle>{c ? c.id : "New connector"}</SheetTitle>
        <SheetDescription>
          Keep secrets out: write <code>{"${NAME}"}</code>, or <code>{"${file:NAME}"}</code> for a file, and set NAME under{" "}
          <a className="underline" href={href("variables")}>
            Variables
          </a>
          .
        </SheetDescription>
      </SheetHeader>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {c ? null : (
          <Label>
            Name
            <Input required pattern="[a-z][a-z0-9_\-]*" value={name} onChange={(e) => setName(e.target.value)} placeholder="homey" />
            <Hint>Tools appear to agents as mcp__name__tool.</Hint>
          </Label>
        )}
        <Label>
          Description
          <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What it reaches" />
        </Label>
        <label className="flex items-center gap-3 text-sm font-medium">
          <Switch checked={enabled} onCheckedChange={setEnabled} /> Enabled
        </label>
        <div className="flex items-center gap-2">
          <Tabs
            value={raw ? "json" : kind}
            onValueChange={(v) => {
              if (v === "json") return switchRaw(true);
              setRaw(false);
              setKind(v);
            }}
          >
            <TabsList>
              <TabsTrigger value="command">Command</TabsTrigger>
              <TabsTrigger value="url">URL</TabsTrigger>
              <TabsTrigger value="json">JSON</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
        {raw ? (
          <Label>
            Settings
            <Textarea rows={14} spellCheck={false} className="font-mono text-xs md:text-xs" value={json} onChange={(e) => setJson(e.target.value)} />
            <Hint>Claude Code's .mcp.json shape for one server.</Hint>
          </Label>
        ) : kind === "command" ? (
          <>
            <Label>
              Command
              <Input className="font-mono" value={command} onChange={(e) => setCommand(e.target.value)} placeholder="npx" />
            </Label>
            <Label>
              Arguments, one per line
              <Textarea rows={3} spellCheck={false} className="font-mono text-xs md:text-xs" value={args} onChange={(e) => setArgs(e.target.value)} placeholder={"-y\n@cocal/google-calendar-mcp"} />
            </Label>
            <Label>
              Environment, KEY=value per line
              <Textarea rows={4} spellCheck={false} className="font-mono text-xs md:text-xs" value={env} onChange={(e) => setEnv(e.target.value)} placeholder="TOKEN=${GCAL_TOKEN}" />
            </Label>
          </>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
              <Label>
                Address
                <Input className="font-mono" type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://mcp.example.com" />
              </Label>
              <Label>
                Transport
                <NativeSelect value={transport} onChange={(e) => setTransport(e.target.value)}>
                  <option value="http">HTTP</option>
                  <option value="sse">SSE</option>
                </NativeSelect>
              </Label>
            </div>
            <Label>
              Headers, Name: value per line
              <Textarea rows={3} spellCheck={false} className="font-mono text-xs md:text-xs" value={headers} onChange={(e) => setHeaders(e.target.value)} placeholder="Authorization: Bearer ${API_TOKEN}" />
            </Label>
          </>
        )}
      </div>
      <div className="flex gap-2 border-t p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <Button type="submit" disabled={busy || (!c && !name.trim())} className="flex-1 sm:flex-none">
          {c ? "Save" : "Add"}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        {c ? <HistoryButton kind="connectors" id={c.id} onRestored={onDone} /> : null}
        <span className="flex-1" />
        {c ? (
          <Button type="button" variant="ghost" className="text-destructive" onClick={remove}>
            Delete
          </Button>
        ) : null}
      </div>
    </form>
  );
}

/** After an OAuth sign-in the server sends the browser back here with the outcome
 * in the query; say it once and take it off the address. */
function useSignInResult() {
  const queryClient = useQueryClient();
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const done = params.get("signed_in");
    const failed = params.get("sign_in_error");
    if (!done && !failed) return;
    if (done) toast.success(`${done} is signed in. Its agents can use it from the next turn.`);
    if (failed) toast.error(`Sign-in did not work: ${failed}`);
    window.history.replaceState(null, "", window.location.pathname + window.location.hash);
    void queryClient.invalidateQueries({ queryKey: ["connectors"] });
  }, [queryClient]);
}

function SignIn({ c }: { c: Connector }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);
  const s = c.sign_in!;
  const start = async () => {
    setBusy(true);
    try {
      const { url } = await api<{ url: string }>("POST", `/api/connectors/${encodeURIComponent(c.id)}/sign-in`);
      window.location.assign(url); // the server's sign-in page, which sends the browser back
    } catch (e) {
      toast.error((e as Error).message);
      setBusy(false);
    }
  };
  const signOut = async () => {
    if (!(await confirm({ title: `Sign ${c.id} out?`, body: "Its agents lose access until somebody signs in again.", action: "Sign out", destructive: true })))
      return;
    try {
      await api("DELETE", `/api/connectors/${encodeURIComponent(c.id)}/sign-in`);
      void queryClient.invalidateQueries({ queryKey: ["connectors"] });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <>
      <Button size="sm" variant={s.signed_in ? "outline" : "default"} onClick={start} disabled={busy}>
        <KeyRound /> {s.signed_in ? "Sign in again" : "Sign in"}
      </Button>
      {s.signed_in ? (
        <>
          <span className="text-xs text-muted-foreground">
            Signed in{s.by ? ` by ${s.by}` : ""}
            {s.at ? ` · ${when(s.at)}` : ""}
            {s.renewable ? " · renews itself" : s.expires_at ? ` · until ${when(s.expires_at)}` : ""}
          </span>
          <span className="flex-1" />
          <Button size="sm" variant="ghost" className="text-destructive" onClick={signOut}>
            <LogOut /> Sign out
          </Button>
        </>
      ) : null}
    </>
  );
}
