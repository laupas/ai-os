import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Cloud, MessageSquareLock, KeyRound, Loader2, LockKeyhole, Network, PlugZap, Plus, Save, ShieldCheck, Trash2, Users, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckRow } from "@/components/ui/checkbox";
import { Hint, Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { api, type Settings } from "@/lib/api";
import { cn } from "@/lib/utils";

type Mode = "cloudflare" | "jwt" | "header" | "pick" | "password" | "code" | "sso" | "dev";

const PROXIES: Mode[] = ["cloudflare", "jwt", "header"];

type ProviderKind = "microsoft" | "google" | "oidc";
/** One single sign-on button, as `web.auth.providers` holds it. */
type Provider = { kind: ProviderKind } & Record<string, unknown>;
type Auth = Record<string, unknown> & { mode: Mode };

interface WebAuthState {
  auth: Auth | null;
  older_form: boolean;
  public_url: string | null;
  port: number;
  you: string;
  /** Group values each sign-in provider sent lately, by provider id. */
  seen_groups?: Record<string, string[]>;
}

interface Tried {
  ok: boolean;
  email: string | null;
  detail: string;
}

/** One field of a mode: the key in `web.auth`, and how to ask for it. */
interface FieldSpec {
  key: string;
  label: string;
  hint?: string;
  placeholder?: string;
  lines?: boolean;
}

const SESSION_DAYS: FieldSpec = { key: "session_days", label: "Stay signed in for (days)", placeholder: "30", hint: "How long a browser stays signed in before it asks again." };

const MODES: { mode: Exclude<Mode, "dev">; title: string; body: string; icon: typeof Cloud; fields: FieldSpec[]; warning?: string }[] = [
  {
    mode: "pick",
    title: "No login: pick a user",
    body: "The console asks who you are and lists everyone with a web account. No password.",
    icon: Users,
    fields: [SESSION_DAYS],
    warning:
      "Anyone who can open the console can act as anyone, administrators included. Only for a network where everyone is trusted, never on the internet without a proxy in front.",
  },
  {
    mode: "password",
    title: "Name and password",
    body: "The console's own login page. Each user's password is set under People, or by themselves.",
    icon: LockKeyhole,
    fields: [SESSION_DAYS],
    warning: "Set your own password first (Settings → People → you), or saving is refused. Put the console behind https: a password sent over plain http can be read on the way.",
  },
  {
    mode: "code",
    title: "Code by chat",
    body: "The console asks for your name and sends a one-time code to your Slack, Teams, Signal or mail. No passwords to manage.",
    icon: MessageSquareLock,
    fields: [SESSION_DAYS],
    warning: "Whoever can read someone's chat can sign in as them. Saving is refused unless ai-os can reach you on an enabled channel.",
  },
  {
    mode: "sso",
    title: "Single sign-on",
    body: "Sign in with Microsoft 365, Google or any OpenID Connect provider. ai-os does the sign-in itself, no proxy needed.",
    icon: ShieldCheck,
    fields: [SESSION_DAYS],
    warning:
      "Each person gets in with the address the provider vouches for, which must be their web account under People. Set the client secret as a Variable first, or saving is refused.",
  },
  {
    mode: "cloudflare",
    title: "Cloudflare Access",
    body: "Access signs every request it lets through; ai-os checks that token itself.",
    icon: Cloud,
    fields: [
      { key: "team_domain", label: "Team domain", placeholder: "example.cloudflareaccess.com", hint: "Zero Trust → Settings → Custom pages: your team domain." },
      { key: "audience", label: "Application audience (AUD) tag", hint: "Access → Applications → the ai-os application → Overview." },
    ],
  },
  {
    mode: "jwt",
    title: "Signed token (JWT)",
    body: "Any login proxy that forwards a signed token: oauth2-proxy, Authentik, Pomerium, …",
    icon: KeyRound,
    fields: [
      { key: "header", label: "Header with the token", placeholder: "X-Auth-Request-Access-Token" },
      { key: "jwks_url", label: "Keys (JWKS) address", placeholder: "https://auth.example.com/.well-known/jwks.json" },
      { key: "issuer", label: "Issuer", placeholder: "https://auth.example.com/" },
      { key: "audience", label: "Audience" },
      { key: "email_claim", label: "Claim with the address", placeholder: "email" },
    ],
  },
  {
    mode: "header",
    title: "Trusted header",
    body: "A proxy that forwards the address as a plain header: Authelia, Traefik forward-auth, …",
    icon: Network,
    fields: [
      { key: "header", label: "Header with the address", placeholder: "Remote-Email" },
      {
        key: "trusted_proxies",
        label: "Proxy addresses",
        lines: true,
        placeholder: "172.18.0.0/16",
        hint: "Addresses or networks (CIDR) the proxy connects from, one per line. A plain header is believed only from these, or with the secret below.",
      },
      {
        key: "secret_env",
        label: "Environment variable with a shared secret",
        placeholder: "AIOS_PROXY_SECRET",
        hint: "The variable's name, never its value: aios.yaml is in git.",
      },
      { key: "secret_header", label: "Header carrying that secret", placeholder: "X-Aios-Proxy-Secret" },
    ],
  },
];

export function LoginPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["settings-web-auth"],
    queryFn: () => api<WebAuthState>("GET", "/api/settings/web-auth"),
  });
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} />;
  return <LoginForm key={JSON.stringify(data)} data={data} />;
}

function LoginForm({ data }: { data: WebAuthState }) {
  const queryClient = useQueryClient();
  const initial: Auth = data.auth && data.auth.mode !== "dev" ? data.auth : { mode: "cloudflare" };
  const [auth, setAuth] = useState<Auth>(initial);
  const [publicUrl, setPublicUrl] = useState(data.public_url ?? "");
  const [busy, setBusy] = useState<"check" | "save" | null>(null);
  const [tried, setTried] = useState<Tried | null>(null);
  const spec = MODES.find((m) => m.mode === auth.mode) ?? MODES[0];
  const dirty = data.older_form || JSON.stringify(auth) !== JSON.stringify(initial) || publicUrl !== (data.public_url ?? "");

  // Only what is filled in is sent: what is left out gets its default.
  const body = () => {
    const out: Auth = { mode: auth.mode };
    for (const f of spec.fields) {
      const v = auth[f.key];
      if (Array.isArray(v) ? v.length : typeof v === "string" ? v.trim() : v != null) out[f.key] = typeof v === "string" ? v.trim() : v;
    }
    if (auth.mode === "sso") out.providers = ((auth.providers as Provider[] | undefined) ?? []).map(cleanProvider);
    if (PROXIES.includes(auth.mode) && auth.create_users === true) {
      out.create_users = true;
      out.domains = (auth.domains as string[] | undefined) ?? [];
      if (auth.default_group && auth.default_group !== "member") out.default_group = auth.default_group;
    }
    return { auth: out, public_url: publicUrl.trim() || null };
  };
  const set = (key: string, value: unknown) => {
    setAuth((a) => ({ ...a, [key]: value }));
    setTried(null);
  };
  const check = async () => {
    setBusy("check");
    try {
      setTried(await api<Tried>("POST", "/api/settings/web-auth/check", body()));
    } catch (e) {
      setTried({ ok: false, email: null, detail: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };
  const save = async () => {
    setBusy("save");
    try {
      const r = await api<{ detail: string }>("PUT", "/api/settings/web-auth", body());
      void queryClient.invalidateQueries({ queryKey: ["settings-web-auth"] });
      void queryClient.invalidateQueries({ queryKey: ["restart-needed"] });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success(`Saved: ${r.detail}. Restart ai-os to apply it.`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (data.auth?.mode === "dev") {
    return (
      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Console login</CardTitle>
          <CardDescription>
            This ai-os runs in <code>dev</code> mode: every request is {String(data.auth.dev_email)}. That is for your own machine only, and is
            changed in aios.yaml.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="max-w-3xl">
      <CardHeader>
        <CardTitle>Console login</CardTitle>
        <CardDescription>
          How the console learns who is asking: from its own login page, or from a login proxy in front of it whose word ai-os checks. A new
          setting is first tried, and only saved if you ({data.you}) could still get in. Applies after a restart.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {data.older_form ? (
          <p className="rounded-lg bg-muted/60 p-3 text-sm">
            aios.yaml has this in the older form (<code>access_team_domain</code>, <code>access_aud</code>); saving writes it as{" "}
            <code>web.auth</code>, with the same meaning.
          </p>
        ) : null}
        <div role="radiogroup" className="grid gap-3 sm:grid-cols-3">
          {MODES.map((m) => {
            const selected = m.mode === auth.mode;
            return (
              <button
                key={m.mode}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => {
                  setAuth(m.mode === initial.mode ? initial : { mode: m.mode });
                  setTried(null);
                }}
                className={cn("flex flex-col gap-1.5 rounded-lg border p-3 text-left transition-colors hover:bg-muted/50", selected && "border-primary ring-2 ring-primary/30")}
              >
                <span className="flex items-center gap-2 text-sm font-medium">
                  <m.icon className="size-4" /> {m.title}
                  {m.mode === data.auth?.mode ? <Badge variant="secondary">in use</Badge> : null}
                </span>
                <span className="text-xs text-muted-foreground">{m.body}</span>
              </button>
            );
          })}
        </div>

        {spec.warning ? <p className="rounded-lg bg-warning/15 p-3 text-sm">{spec.warning}</p> : null}

        {auth.mode === "sso" ? (
          <ProvidersEditor
            providers={(auth.providers as Provider[] | undefined) ?? []}
            seen={data.seen_groups ?? {}}
            onChange={(providers) => set("providers", providers)}
            callback={`${(publicUrl.trim() || window.location.origin).replace(/\/$/, "")}/api/login/sso/callback`}
          />
        ) : null}

        {spec.fields.map((f) => (
          <Label key={f.key}>
            {f.label}
            {f.lines ? (
              <Textarea
                rows={3}
                className="font-mono text-xs md:text-xs"
                placeholder={f.placeholder}
                value={((auth[f.key] as string[] | undefined) ?? []).join("\n")}
                onChange={(e) => set(f.key, e.target.value.split("\n").map((l) => l.trim()).filter(Boolean))}
              />
            ) : (
              <Input className="font-mono" placeholder={f.placeholder} value={String(auth[f.key] ?? "")} onChange={(e) => set(f.key, e.target.value)} />
            )}
            {f.hint ? <Hint>{f.hint}</Hint> : null}
          </Label>
        ))}

        {PROXIES.includes(auth.mode) ? (
          <NewPeople
            value={auth}
            set={set}
            withDomains
            hint="Instead of refusing an address the proxy lets through and nobody has, ai-os makes a user with it. Only addresses in these domains: ai-os cannot see whom your proxy lets in."
          />
        ) : null}

        <Label>
          Public address
          <Input className="font-mono" placeholder="https://ai-os.example.com" value={publicUrl} onChange={(e) => setPublicUrl(e.target.value)} />
          <Hint>Where browsers reach the console, for connector sign-ins and single sign-on. Empty: taken from each request.</Hint>
        </Label>
        <Hint>
          Port {data.port}: fixed here, since a proxy in front may send to it; change it in aios.yaml.
        </Hint>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={check} disabled={busy !== null}>
            {busy === "check" ? <Loader2 className="animate-spin" /> : <PlugZap />} Test with this browser
          </Button>
          <Button onClick={save} disabled={!dirty || busy !== null}>
            {busy === "save" ? <Loader2 className="animate-spin" /> : <Save />} Save
          </Button>
        </div>
        {tried ? (
          <div role="status" className={cn("flex items-start gap-2 rounded-lg p-3 text-sm", tried.ok ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive")}>
            {tried.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" /> : <XCircle className="mt-0.5 size-4 shrink-0" />}
            <span>{tried.ok ? `Works: ${tried.detail}.` : `Would not work: ${tried.detail}.`}</span>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

const PROVIDER_KINDS: { kind: ProviderKind; title: string; secret: string }[] = [
  { kind: "microsoft", title: "Microsoft 365", secret: "AIOS_SSO_MICROSOFT_SECRET" },
  { kind: "google", title: "Google", secret: "AIOS_SSO_GOOGLE_SECRET" },
  { kind: "oidc", title: "OpenID Connect", secret: "AIOS_SSO_SECRET" },
];

/** What a provider's form asks for, by kind. */
const PROVIDER_FIELDS: Record<ProviderKind, FieldSpec[]> = {
  microsoft: [
    {
      key: "tenant",
      label: "Tenant",
      placeholder: "example.com or the directory id",
      hint: "Entra ID → Overview: the tenant id, or a domain of it. consumers for personal Microsoft accounts. Accounts of any organisation (common) are not accepted.",
    },
    { key: "client_id", label: "Application (client) id", hint: "Entra ID → App registrations → New registration, platform Web." },
  ],
  google: [{ key: "client_id", label: "Client id", placeholder: "….apps.googleusercontent.com", hint: "Google Cloud → APIs & Services → Credentials → OAuth client id, type Web application." }],
  oidc: [
    { key: "issuer", label: "Issuer", placeholder: "https://auth.example.com/application/o/ai-os/", hint: "Where /.well-known/openid-configuration is found: Authentik, Keycloak, Okta, Auth0, Zitadel, …" },
    { key: "client_id", label: "Client id" },
  ],
};

const COMMON_FIELDS: FieldSpec[] = [
  { key: "client_secret_variable", label: "Variable with the client secret", hint: "Its name; set the secret itself under Variables. Never in aios.yaml, which is in git." },
  { key: "domains", label: "Only these domains", lines: true, placeholder: "example.com", hint: "One per line. Empty: any address the provider vouches for that is someone's web account." },
  { key: "label", label: "Button text", placeholder: "Microsoft", hint: "After \"Sign in with\". Empty: the provider's name." },
  { key: "id", label: "Id", placeholder: "work", hint: "Only needed for two sign-ins of the same kind." },
];

function cleanProvider(p: Provider): Provider {
  const out: Provider = { kind: p.kind };
  for (const [k, v] of Object.entries(p)) {
    if (k === "kind") continue;
    if (Array.isArray(v) ? v.length : typeof v === "string" ? v.trim() : v != null) out[k] = typeof v === "string" ? v.trim() : v;
  }
  return out;
}

function ProvidersEditor({ providers, seen, onChange, callback }: { providers: Provider[]; seen: Record<string, string[]>; onChange: (p: Provider[]) => void; callback: string }) {
  const update = (i: number, key: string, value: unknown) => onChange(providers.map((p, j) => (j === i ? { ...p, [key]: value } : p)));
  return (
    <div className="space-y-3">
      <div className="rounded-lg bg-muted/60 p-3 text-sm">
        Register this redirect address with each provider:
        <code className="mt-1 block break-all font-mono text-xs">{callback}</code>
      </div>
      {providers.map((p, i) => {
        const kind = PROVIDER_KINDS.find((k) => k.kind === p.kind) ?? PROVIDER_KINDS[2];
        return (
          <div key={i} className="space-y-3 rounded-lg border p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">{kind.title}</span>
              <Button variant="ghost" size="sm" onClick={() => onChange(providers.filter((_, j) => j !== i))}>
                <Trash2 /> Remove
              </Button>
            </div>
            {[...PROVIDER_FIELDS[p.kind], ...COMMON_FIELDS].map((f) => (
              <Label key={f.key}>
                {f.label}
                {f.lines ? (
                  <Textarea
                    rows={2}
                    className="font-mono text-xs md:text-xs"
                    placeholder={f.placeholder}
                    value={((p[f.key] as string[] | undefined) ?? []).join("\n")}
                    onChange={(e) => update(i, f.key, e.target.value.split("\n").map((l) => l.trim()).filter(Boolean))}
                  />
                ) : (
                  <Input className="font-mono" placeholder={f.placeholder} value={String(p[f.key] ?? "")} onChange={(e) => update(i, f.key, e.target.value)} />
                )}
                {f.hint ? <Hint>{f.hint}</Hint> : null}
              </Label>
            ))}
            <GroupMap provider={p} seen={seen[String(p.id ?? p.kind)] ?? []} set={(key, value) => update(i, key, value)} />
            <NewPeople
              value={p}
              set={(key, value) => update(i, key, value)}
              hint="Instead of refusing an address nobody has, ai-os makes a user with it. Needs Only these domains, unless a Microsoft tenant of your own limits who can sign in."
            />
          </div>
        );
      })}
      <div className="flex flex-wrap gap-2">
        {PROVIDER_KINDS.map((k) => (
          <Button key={k.kind} variant="outline" size="sm" onClick={() => onChange([...providers, { kind: k.kind, client_secret_variable: k.secret }])}>
            <Plus /> {k.title}
          </Button>
        ))}
      </div>
    </div>
  );
}

/** Whether, and as what, someone a login vouches for and nobody has yet becomes a user. */
function NewPeople({ value, set, hint, withDomains }: { value: Record<string, unknown>; set: (key: string, value: unknown) => void; hint: string; withDomains?: boolean }) {
  // Groups such a user may go into: those that chat and do not administer (the server checks it again).
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: () => api<Settings>("GET", "/api/settings") });
  const groups = (settings?.groups ?? []).filter((g) => g.permissions.includes("chat") && !g.permissions.includes("administer") && !g.permissions.includes("manage_users"));
  const on = value.create_users === true;
  return (
    <div className="space-y-2 rounded-lg bg-muted/40 p-3">
      <CheckRow label="Add new people on their first sign-in" checked={on} onChange={(v) => set("create_users", v || undefined)} />
      <Hint>{hint}</Hint>
      {on && withDomains ? (
        <Label>
          Only these domains
          <Textarea
            rows={2}
            className="font-mono text-xs md:text-xs"
            placeholder="example.com"
            value={((value.domains as string[] | undefined) ?? []).join("\n")}
            onChange={(e) => set("domains", e.target.value.split("\n").map((l) => l.trim()).filter(Boolean))}
          />
          <Hint>One per line.</Hint>
        </Label>
      ) : null}
      {on ? (
        <Label>
          Their group
          <NativeSelect className="max-w-xs" value={String(value.default_group ?? "member")} onChange={(e) => set("default_group", e.target.value === "member" ? undefined : e.target.value)}>
            {(groups.length ? groups : [{ id: "member", name: "Members" }]).map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </NativeSelect>
          <Hint>Only groups that can chat and do not administer ai-os. Change someone's groups later under Users.</Hint>
        </Label>
      ) : null}
    </div>
  );
}

/** Which ai-os group a value of the provider's groups claim puts someone in, kept in step on every sign-in. */
function GroupMap({ provider: p, seen, set }: { provider: Provider; seen: string[]; set: (key: string, value: unknown) => void }) {
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: () => api<Settings>("GET", "/api/settings") });
  // Groups that administer are never filled from a token (the server refuses them too).
  const groups = (settings?.groups ?? []).filter((g) => !g.permissions.includes("administer") && !g.permissions.includes("manage_users"));
  const map = Object.entries((p.group_map as Record<string, string> | undefined) ?? {});
  const write = (entries: [string, string][]) => set("group_map", entries.length ? Object.fromEntries(entries) : undefined);
  const listId = `seen-${String(p.id ?? p.kind)}`;
  if (p.kind === "google") {
    return <Hint>Google sends no groups in its sign-in, so people's groups are set under Users.</Hint>;
  }
  return (
    <div className="space-y-2 rounded-lg bg-muted/40 p-3">
      <div className="text-sm font-medium">Groups from {p.kind === "microsoft" ? "Microsoft" : "the provider"}</div>
      <Label>
        Claim with the groups
        <Input className="max-w-xs font-mono" placeholder="groups" value={String(p.groups_claim ?? "")} onChange={(e) => set("groups_claim", e.target.value || undefined)} />
        <Hint>
          {p.kind === "microsoft"
            ? "roles for app roles (recommended: readable names you define in the app registration), groups for Entra groups (their object ids)."
            : "Usually groups."}
        </Hint>
      </Label>
      <datalist id={listId}>
        {seen.map((v) => (
          <option key={v} value={v} />
        ))}
      </datalist>
      {map.map(([value, group], j) => (
        <div key={j} className="flex items-center gap-2">
          <Input
            className="min-w-0 flex-1 font-mono text-xs"
            list={listId}
            placeholder="value in the token"
            value={value}
            onChange={(e) => write(map.map((m, k) => (k === j ? [e.target.value, m[1]] : m)))}
          />
          <span className="text-sm text-muted-foreground">puts them in</span>
          <NativeSelect className="w-40" value={group} onChange={(e) => write(map.map((m, k) => (k === j ? [m[0], e.target.value] : m)))}>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </NativeSelect>
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Remove" onClick={() => write(map.filter((_, k) => k !== j))}>
            <Trash2 />
          </Button>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" onClick={() => write([...map, [seen.find((v) => !map.some((m) => m[0] === v)) ?? "", groups[0]?.id ?? "member"]])}>
        <Plus /> Map a group
      </Button>
      <Hint>
        {seen.length ? `Seen lately: ${seen.join(", ")}. ` : "Values appear here once someone has signed in. "}
        On every sign-in a mapped group is added when the token has its value and taken away when it has not; groups given by hand under Users stay.
        Groups that administer ai-os are never filled this way.
      </Hint>
    </div>
  );
}
