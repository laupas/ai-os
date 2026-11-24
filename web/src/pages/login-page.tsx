import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, LogIn, Sparkles, User as UserIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { api, type LoginInfo } from "@/lib/api";

/** Why a single sign-on came back without signing in, from `?login_error=`; read once and taken off the address. */
function takeLoginError(): string | null {
  const params = new URLSearchParams(window.location.search);
  const message = params.get("login_error");
  if (message) {
    params.delete("login_error");
    const rest = params.toString();
    window.history.replaceState(null, "", `${window.location.pathname}${rest ? `?${rest}` : ""}${window.location.hash}`);
  }
  return message;
}

/** The console's own login page: pick a user, a name and a password, a name and a code sent to one's chat, or single sign-on. */
export function LoginScreen({ info }: { info: LoginInfo }) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(takeLoginError);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState<string | null>(null);

  const signIn = async (body: Record<string, string>, key: string) => {
    setBusy(key);
    setError(null);
    try {
      const r = await api<{ ok: boolean; pending?: boolean; detail?: string }>("POST", "/api/login", body);
      if (r.pending) {
        setSent(r.detail ?? "A code is on its way.");
        setBusy(null);
        return;
      }
      await queryClient.resetQueries();
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  };

  return (
    <div className="flex min-h-dvh items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Sparkles className="size-4" />
            </span>
            Sign in to ai-os
          </CardTitle>
          <CardDescription>
            {info.mode === "pick"
              ? "Who are you?"
              : info.mode === "sso"
                ? "With the account your organisation gave you."
                : info.mode === "code"
                ? "With your name or address; ai-os sends you a code on your chat."
                : "With your name or address and your console password."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {info.mode === "pick" ? (
            <div className="grid gap-2">
              {(info.users ?? []).map((u) => (
                <Button key={u.id} variant="outline" className="justify-start" disabled={busy !== null} onClick={() => void signIn({ user_id: u.id }, u.id)}>
                  {busy === u.id ? <Loader2 className="animate-spin" /> : <UserIcon />} {u.name}
                </Button>
              ))}
              {info.users?.length ? null : <p className="text-sm text-muted-foreground">Nobody has a web account yet.</p>}
            </div>
          ) : info.mode === "sso" ? (
            <div className="grid gap-2">
              {(info.providers ?? []).map((p) => (
                <Button key={p.id} asChild variant="outline" className="justify-start" onClick={() => setBusy(p.id)}>
                  <a href={`/api/login/sso/start/${encodeURIComponent(p.id)}`}>
                    {busy === p.id ? <Loader2 className="animate-spin" /> : p.kind === "oidc" ? <KeyRound /> : <ProviderMark kind={p.kind} />} Sign in
                    with {p.label}
                  </a>
                </Button>
              ))}
            </div>
          ) : info.mode === "code" ? (
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                void signIn(sent ? { username, code } : { username }, "code");
              }}
            >
              <Label>
                Name or address
                <Input autoFocus={!sent} autoComplete="username" value={username} disabled={Boolean(sent)} onChange={(e) => setUsername(e.target.value)} />
              </Label>
              {sent ? (
                <>
                  <p className="text-sm text-muted-foreground">{sent.charAt(0).toUpperCase() + sent.slice(1)}.</p>
                  <Label>
                    Code
                    <Input autoFocus inputMode="numeric" autoComplete="one-time-code" className="font-mono tracking-widest" value={code} onChange={(e) => setCode(e.target.value)} />
                  </Label>
                </>
              ) : null}
              <Button type="submit" className="w-full" disabled={busy !== null || !username.trim() || (Boolean(sent) && !code.trim())}>
                {busy ? <Loader2 className="animate-spin" /> : <LogIn />} {sent ? "Sign in" : "Send me a code"}
              </Button>
              {sent ? (
                <Button
                  type="button"
                  variant="ghost"
                  className="w-full"
                  onClick={() => {
                    setSent(null);
                    setCode("");
                  }}
                >
                  Another name, or send again
                </Button>
              ) : null}
            </form>
          ) : (
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                void signIn({ username, password }, "password");
              }}
            >
              <Label>
                Name or address
                <Input autoFocus autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
              </Label>
              <Label>
                Password
                <Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
              </Label>
              <Button type="submit" className="w-full" disabled={busy !== null || !username.trim() || !password}>
                {busy ? <Loader2 className="animate-spin" /> : <LogIn />} Sign in
              </Button>
            </form>
          )}
          {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}

/** Microsoft's four squares or Google's G, drawn small, so the buttons look like what people know. */
function ProviderMark({ kind }: { kind: "microsoft" | "google" }) {
  if (kind === "microsoft") {
    return (
      <svg viewBox="0 0 16 16" aria-hidden="true" className="size-4">
        <rect x="0" y="0" width="7.5" height="7.5" fill="#F25022" />
        <rect x="8.5" y="0" width="7.5" height="7.5" fill="#7FBA00" />
        <rect x="0" y="8.5" width="7.5" height="7.5" fill="#00A4EF" />
        <rect x="8.5" y="8.5" width="7.5" height="7.5" fill="#FFB900" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="size-4">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}
