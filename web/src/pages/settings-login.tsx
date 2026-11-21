import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Cloud, MessageSquareLock, KeyRound, Loader2, LockKeyhole, Network, PlugZap, Save, Users, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Hint, Input, Label, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Mode = "cloudflare" | "jwt" | "header" | "pick" | "password" | "code" | "dev";
type Auth = Record<string, unknown> & { mode: Mode };

interface WebAuthState {
  auth: Auth | null;
  older_form: boolean;
  public_url: string | null;
  port: number;
  you: string;
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

        <Label>
          Public address
          <Input className="font-mono" placeholder="https://ai-os.example.com" value={publicUrl} onChange={(e) => setPublicUrl(e.target.value)} />
          <Hint>Where browsers reach the console, for connector sign-ins (OAuth). Empty: taken from each request.</Hint>
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
