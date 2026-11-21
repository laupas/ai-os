import { useQueryClient } from "@tanstack/react-query";
import { Loader2, LogIn, Sparkles, User as UserIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { api, type LoginInfo } from "@/lib/api";

/** The console's own login page: pick a user, a name and a password, or a name and a code sent to one's chat. */
export function LoginScreen({ info }: { info: LoginInfo }) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
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
