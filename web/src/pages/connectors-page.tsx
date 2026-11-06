import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, LogOut, Pencil, Play, Plug, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ListView } from "@/components/list-view";
import { prune, SettingsFields, type Values } from "@/components/schema-form";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { HistoryButton } from "@/components/history-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Hint, Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type CodeConnectorOffer, type Connector, type ProbeResult, type SignInMode, type SignInState } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { href } from "@/lib/router";
import { can, useMe } from "@/lib/use-me";
import { when } from "@/lib/utils";

type Config = Record<string, unknown>;

/** Google's OAuth endpoints; its MCP servers neither publish nor register them. */
const GOOGLE = {
  authorization_endpoint: "https://accounts.google.com/o/oauth2/v2/auth",
  token_endpoint: "https://oauth2.googleapis.com/token",
  params: { access_type: "offline", prompt: "consent" },
};

export function ConnectorsPage() {
  const { data: me } = useMe();
  const admin = can(me, "administer");
  const { data, isLoading, error } = useQuery({
    queryKey: ["connectors"],
    queryFn: () => api<{ connectors: Connector[]; library?: CodeConnectorOffer[] }>("GET", "/api/connectors"),
  });
  const [editing, setEditing] = useState<Connector | "new" | null>(null);
  useSignInResult();
  return (
    <Page className="max-w-3xl">
      <PageHeader
        title="Connectors"
        description={
          admin
            ? "MCP servers ai-os starts for a turn. Which agent may use one, and which of its tools, is set on the agent."
            : "Services ai-os can use for you. Where it says Your account, sign in with your own; ai-os then works in that account only for you."
        }
        actions={
          admin ? (
            <Button onClick={() => setEditing("new")}>
              <Plus /> New connector
            </Button>
          ) : null
        }
      />
      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {data ? (
        <ListView
          items={data.connectors}
          keyOf={(c) => c.id}
          text={(c) => `${c.id} ${c.description} ${c.used_by.join(" ")}`}
          facets={
            admin
              ? [
                  { label: "states", value: (c) => (c.builtin ? "built in" : c.enabled ? "on" : "off"), options: ["on", "off", "built in"] },
                  { label: "sign-ins", value: (c) => c.sign_in_mode ?? "none" },
                  { label: "agents", value: (c) => (c.used_by.length ? c.used_by : "unused") },
                ]
              : []
          }
          empty={admin ? "No connectors yet." : "Nothing here needs you to sign in."}
        >
          {(c) => (admin ? <ConnectorCard connector={c} onEdit={() => setEditing(c)} /> : <MemberCard connector={c} />)}
        </ListView>
      ) : null}
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent side="right" className="gap-0 p-0 sm:max-w-xl">
          {editing !== null ? (
            <ConnectorForm connector={editing === "new" ? null : editing} library={data?.library ?? []} onDone={() => setEditing(null)} />
          ) : null}
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
  if (!c.status) return c.sign_in && !inUse(c) ? <Badge variant="warning">not signed in</Badge> : <Badge variant="secondary">not started yet</Badge>;
  return <Badge variant={c.status === "connected" ? "success" : "destructive"}>{c.status}</Badge>;
}

/** Whether a turn of this viewer would carry a sign-in. */
function inUse(c: Connector): boolean {
  const s = c.sign_in;
  if (!s) return false;
  if (s.mode === "shared") return Boolean(s.shared?.signed_in);
  return Boolean(s.mine?.signed_in || (s.shared_fallback && s.shared?.signed_in));
}

/** A connector as somebody who is not an administrator sees it: what it is and
 * their own sign-in, nothing of its configuration. */
function MemberCard({ connector: c }: { connector: Connector }) {
  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <Plug className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <span className="font-medium">{c.id}</span>
          {c.description ? <p className="mt-1 text-sm text-muted-foreground">{c.description}</p> : null}
        </div>
      </div>
      {c.sign_in ? (
        <div className="mt-3 border-t pt-3">
          <SignIn c={c} admin={false} />
        </div>
      ) : null}
    </Card>
  );
}

/** What the server is, in a few words: its command or its address. */
function target(config: Config | null): string {
  if (!config) return "";
  if (typeof config.code === "string") return `code connector ${config.code}`;
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
      await api("PUT", `/api/connectors/${encodeURIComponent(c.id)}`, {
        description: c.description,
        config: c.config,
        enabled,
        sign_in: c.sign_in_mode,
        shared_fallback: c.shared_fallback,
      });
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
        </div>
      )}
      {c.sign_in ? (
        <div className="mt-3 border-t pt-3">
          <SignIn c={c} admin />
        </div>
      ) : null}
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

function ConnectorForm({ connector: c, library, onDone }: { connector: Connector | null; library: CodeConnectorOffer[]; onDone: () => void }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const original: Config = c?.config ?? {};
  const [name, setName] = useState("");
  const [description, setDescription] = useState(c?.description ?? "");
  const [enabled, setEnabled] = useState(c?.enabled ?? true);
  const [kind, setKind] = useState(typeof original.code === "string" ? "code" : typeof original.url === "string" ? "url" : "command");
  const [codeName, setCodeName] = useState(String(original.code ?? library[0]?.name ?? ""));
  const [settings, setSettings] = useState<Values>((original.settings as Values) ?? {});
  const offer = library.find((o) => o.name === codeName);
  const [command, setCommand] = useState(String(original.command ?? ""));
  const [args, setArgs] = useState(Array.isArray(original.args) ? original.args.join("\n") : "");
  const [env, setEnv] = useState(toLines(original.env, "="));
  const [url, setUrl] = useState(String(original.url ?? ""));
  const [transport, setTransport] = useState(original.type === "sse" ? "sse" : "http");
  const [headers, setHeaders] = useState(toLines(original.headers, ": "));
  const oauth = (original.oauth ?? {}) as Config;
  const [ownClient, setOwnClient] = useState(Object.keys(oauth).length > 0);
  const [authUrl, setAuthUrl] = useState(String(oauth.authorization_endpoint ?? ""));
  const [tokenUrl, setTokenUrl] = useState(String(oauth.token_endpoint ?? ""));
  const [clientId, setClientId] = useState(String(oauth.client_id ?? ""));
  const [clientSecret, setClientSecret] = useState(String(oauth.client_secret ?? ""));
  const [authMethod, setAuthMethod] = useState(String(oauth.auth_method ?? "client_secret_post"));
  const [scopes, setScopes] = useState(Array.isArray(oauth.scopes) ? oauth.scopes.join("\n") : "");
  const [params, setParams] = useState(toLines(oauth.params, "="));
  const [signInMode, setSignInMode] = useState<SignInMode>(c?.sign_in_mode ?? "shared");
  const [fallback, setFallback] = useState(c?.shared_fallback ?? false);
  const useGoogle = () => {
    setAuthUrl(GOOGLE.authorization_endpoint);
    setTokenUrl(GOOGLE.token_endpoint);
    setAuthMethod("client_secret_post");
    setParams(toLines(GOOGLE.params, "="));
    if (!clientId) setClientId("${GOOGLE_CLIENT_ID}");
    if (!clientSecret) setClientSecret("${GOOGLE_CLIENT_SECRET}");
  };
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
    for (const key of ["command", "args", "env", "url", "type", "headers", "oauth", "code", "settings"]) delete config[key];
    if (kind === "code") {
      if (!codeName) throw new Error("Choose a code connector.");
      config.code = codeName;
      const kept = prune(settings);
      if (Object.keys(kept).length) config.settings = kept;
    } else if (kind === "command") {
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
      if (ownClient) {
        if (!authUrl.trim() || !tokenUrl.trim() || !clientId.trim())
          throw new Error("An own OAuth client needs the sign-in address, the token address and a client id.");
        const own: Config = { authorization_endpoint: authUrl.trim(), token_endpoint: tokenUrl.trim(), client_id: clientId.trim() };
        if (clientSecret.trim()) own.client_secret = clientSecret.trim();
        if (authMethod !== "client_secret_post") own.auth_method = authMethod;
        const list = scopes.split(/\s+/).map((x) => x.trim()).filter(Boolean);
        if (list.length) own.scopes = list;
        const extra = fromLines(params, "=");
        if (Object.keys(extra).length) own.params = extra;
        config.oauth = own;
      }
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
      const body = { description: description.trim(), config: build(), enabled, sign_in: signInMode, shared_fallback: signInMode === "per_user" && fallback };
      type Saved = { moved_secrets?: string[]; added_agents?: string[] };
      const saved = c
        ? await api<Saved>("PUT", `/api/connectors/${encodeURIComponent(c.id)}`, body)
        : await api<Saved>("POST", "/api/connectors", { ...body, name: name.trim() });
      const added = saved?.added_agents ?? [];
      toast.success(
        c ? "Saved. Applies to the next turn." : added.length ? `Added, with its agents ${added.join(", ")}.` : "Added. Now grant it to an agent.",
      );
      if (added.length) void queryClient.invalidateQueries({ queryKey: ["agents"] });
      const moved = saved?.moved_secrets ?? [];
      if (moved.length)
        toast.info(`Moved ${moved.length === 1 ? "a secret" : `${moved.length} secrets`} into encrypted variables: ${moved.join(", ")}.`);
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
              {/* A code connector stays one: its settings belong to its code. */}
              {c?.code ? (
                <TabsTrigger value="code">Code</TabsTrigger>
              ) : (
                <>
                  <TabsTrigger value="command">Command</TabsTrigger>
                  <TabsTrigger value="url">URL</TabsTrigger>
                  {library.length ? <TabsTrigger value="code">Code</TabsTrigger> : null}
                </>
              )}
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
        ) : kind === "code" ? (
          <CodeFields
            connector={c}
            library={library}
            codeName={codeName}
            onCodeName={(n) => {
              setCodeName(n);
              setSettings({});
            }}
            offer={offer}
            settings={settings}
            onSettings={setSettings}
          />
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
            <div className="space-y-3 rounded-md border p-3">
              <Label>
                Whose account
                <NativeSelect value={signInMode} onChange={(e) => setSignInMode(e.target.value as SignInMode)}>
                  <option value="shared">One shared account, signed in by an administrator</option>
                  <option value="per_user">Each user's own account</option>
                </NativeSelect>
                <Hint>
                  Shared: every user's turns work in the one account (Homey). Each user's own: everybody signs in on this page, and a turn uses
                  only the account of the user it is for; a schedule runs as its user.
                </Hint>
              </Label>
              {signInMode === "per_user" ? (
                <label className="flex items-center gap-3 text-sm">
                  <Switch checked={fallback} onCheckedChange={setFallback} /> Users who have not signed in use the shared account
                </label>
              ) : null}
              <label className="flex items-center gap-3 text-sm font-medium">
                <Switch checked={ownClient} onCheckedChange={setOwnClient} /> Sign in with an own OAuth client
              </label>
              <Hint>
                Off: Sign in asks the server where to sign in and registers ai-os by itself (Homey). On: for a server that does neither, such as
                Google's MCP servers, with a client you created there. Its redirect URI is <code>{`${window.location.origin}/api/oauth/callback`}</code>.
              </Hint>
              {ownClient ? (
                <>
                  <Button type="button" size="sm" variant="outline" onClick={useGoogle}>
                    Fill in Google
                  </Button>
                  <Label>
                    Sign-in address
                    <Input className="font-mono" value={authUrl} onChange={(e) => setAuthUrl(e.target.value)} placeholder="https://accounts.google.com/o/oauth2/v2/auth" />
                  </Label>
                  <Label>
                    Token address
                    <Input className="font-mono" value={tokenUrl} onChange={(e) => setTokenUrl(e.target.value)} placeholder="https://oauth2.googleapis.com/token" />
                  </Label>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Label>
                      Client id
                      <Input className="font-mono" value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="${GOOGLE_CLIENT_ID}" />
                    </Label>
                    <Label>
                      Client secret
                      <Input className="font-mono" value={clientSecret} onChange={(e) => setClientSecret(e.target.value)} placeholder="${GOOGLE_CLIENT_SECRET}" />
                    </Label>
                  </div>
                  <Hint>Write the secret as a variable, not as the value itself: the configuration is a git repository.</Hint>
                  <Label>
                    Client authentication
                    <NativeSelect value={authMethod} onChange={(e) => setAuthMethod(e.target.value)}>
                      <option value="client_secret_post">In the request body (Google)</option>
                      <option value="client_secret_basic">HTTP Basic</option>
                      <option value="none">None (public client)</option>
                    </NativeSelect>
                  </Label>
                  <Label>
                    Scopes, one per line
                    <Textarea rows={3} spellCheck={false} className="font-mono text-xs md:text-xs" value={scopes} onChange={(e) => setScopes(e.target.value)} placeholder="https://www.googleapis.com/auth/contacts.readonly" />
                  </Label>
                  <Label>
                    Extra sign-in parameters, key=value per line
                    <Textarea rows={2} spellCheck={false} className="font-mono text-xs md:text-xs" value={params} onChange={(e) => setParams(e.target.value)} placeholder={"access_type=offline\nprompt=consent"} />
                    <Hint>Google needs access_type=offline, or the sign-in cannot renew itself.</Hint>
                  </Label>
                </>
              ) : null}
            </div>
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

/** A code connector: which one, what it brings, and its settings. */
function CodeFields({
  connector: c,
  library,
  codeName,
  onCodeName,
  offer,
  settings,
  onSettings,
}: {
  connector: Connector | null;
  library: CodeConnectorOffer[];
  codeName: string;
  onCodeName: (name: string) => void;
  offer: CodeConnectorOffer | undefined;
  settings: Values;
  onSettings: (v: Values) => void;
}) {
  // A new one has no row yet, so its settings' schema arrives with the first save.
  const part = c?.code;
  return (
    <div className="space-y-4">
      {c ? (
        <p className="text-sm">
          Runs <code>{part?.name}</code>
          {part && !part.found ? <span className="text-destructive">, which is not there any more</span> : null}.
        </p>
      ) : (
        <Label>
          Code connector
          <NativeSelect value={codeName} onChange={(e) => onCodeName(e.target.value)}>
            {library.map((o) => (
              <option key={o.name}>{o.name}</option>
            ))}
          </NativeSelect>
        </Label>
      )}
      {(part?.description ?? offer?.description) ? <p className="text-sm text-muted-foreground">{part?.description ?? offer?.description}</p> : null}
      {!c && offer?.agents.length ? (
        <Hint>Adding it also adds its agents, where there is none of that name yet: {offer.agents.join(", ")}.</Hint>
      ) : null}
      {part?.found && Object.keys(part.schema.properties ?? {}).length ? (
        <div className="space-y-3 rounded-md border p-3">
          <div className="text-sm font-medium">Settings</div>
          <Hint>
            An empty field uses its default. What aios.yaml fixes under <code>{`connectors.${c?.id}.settings`}</code> is shown and cannot be changed
            here, by you or by an agent.
          </Hint>
          <SettingsFields schema={part.schema} values={settings} onChange={onSettings} fixed={part.fixed} />
        </div>
      ) : !c ? (
        <Hint>Its settings can be changed once it is added.</Hint>
      ) : null}
    </div>
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

function SignIn({ c, admin }: { c: Connector; admin: boolean }) {
  const s = c.sign_in!;
  const perUser = s.mode === "per_user";
  return (
    <div className="space-y-2">
      {perUser ? <Account c={c} account="mine" label="Your account" state={s.mine} canChange /> : null}
      {s.shared ? (
        <Account
          c={c}
          account="shared"
          label={perUser ? (s.shared_fallback ? "Shared account, for users who have not signed in" : "Shared account (not used)") : "Shared account"}
          state={s.shared}
          canChange={admin}
        />
      ) : null}
      {admin && perUser ? (
        <p className="text-xs text-muted-foreground">
          {s.users ?? 0} user{s.users === 1 ? "" : "s"} signed in with their own account.
        </p>
      ) : null}
    </div>
  );
}

function Account({
  c,
  account,
  label,
  state,
  canChange,
}: {
  c: Connector;
  account: "mine" | "shared";
  label: string;
  state: SignInState | null;
  canChange: boolean;
}) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);
  const path = `/api/connectors/${encodeURIComponent(c.id)}/sign-in?account=${account}`;
  const signedIn = Boolean(state?.signed_in);
  const start = async () => {
    setBusy(true);
    try {
      const { url } = await api<{ url: string }>("POST", path);
      window.location.assign(url); // the server's sign-in page, which sends the browser back
    } catch (e) {
      toast.error((e as Error).message);
      setBusy(false);
    }
  };
  const signOut = async () => {
    const body =
      account === "mine" ? "ai-os can no longer use this account for you until you sign in again." : "Its agents lose access until somebody signs in again.";
    if (!(await confirm({ title: `Sign ${c.id} out?`, body, action: "Sign out", destructive: true }))) return;
    try {
      await api("DELETE", path);
      void queryClient.invalidateQueries({ queryKey: ["connectors"] });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm">{label}:</span>
      <Badge variant={signedIn ? "success" : "warning"}>{signedIn ? "signed in" : "not signed in"}</Badge>
      {signedIn ? (
        <span className="text-xs text-muted-foreground">
          {[
            state?.by && account === "shared" ? `by ${state.by}` : null,
            state?.at ? when(state.at) : null,
            state?.renewable ? "renews itself" : state?.expires_at ? `until ${when(state.expires_at)}` : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        </span>
      ) : null}
      {canChange ? (
        <>
          <span className="flex-1" />
          <Button size="sm" variant={signedIn ? "outline" : "default"} onClick={start} disabled={busy}>
            <KeyRound /> {signedIn ? "Sign in again" : "Sign in"}
          </Button>
          {signedIn ? (
            <Button size="sm" variant="ghost" className="text-destructive" onClick={signOut}>
              <LogOut /> Sign out
            </Button>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
