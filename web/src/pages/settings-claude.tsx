import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Loader2, PlugZap, Power, Save, Ticket, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Hint, Input, Label } from "@/components/ui/input";
import { api, type ClaudeAuth, type ClaudeSettings, type SignInCheck } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { restartAiOs } from "@/lib/restart";
import { cn } from "@/lib/utils";

const CHOICES: { auth: ClaudeAuth; title: string; body: string; icon: typeof KeyRound; field: string; placeholder: string; hint: string }[] = [
  {
    auth: "subscription",
    title: "Claude subscription",
    body: "A Claude Code token from a Pro or Max plan. Turns count against that plan's limits.",
    icon: Ticket,
    field: "Claude Code token",
    placeholder: "sk-ant-oat01-…",
    hint: "Run claude setup-token on any computer with Claude Code and paste what it prints.",
  },
  {
    auth: "api_key",
    title: "Anthropic API key",
    body: "Billed per use on the Anthropic Console. Recommended for a server.",
    icon: KeyRound,
    field: "API key",
    placeholder: "sk-ant-api03-…",
    hint: "Create one at console.anthropic.com under API keys.",
  },
];

function SourceBadge({ source }: { source: "variable" | "environment" | null }) {
  if (source === "variable") return <Badge variant="success">set</Badge>;
  if (source === "environment") return <Badge variant="warning">from the environment</Badge>;
  return <Badge variant="destructive">not set</Badge>;
}

export function ClaudePanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["settings-claude"],
    queryFn: () => api<ClaudeSettings>("GET", "/api/settings/claude"),
  });
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} />;
  return <ClaudeForm key={data.auth} data={data} />;
}

function ClaudeForm({ data }: { data: ClaudeSettings }) {
  const [auth, setAuth] = useState<ClaudeAuth>(data.auth);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [checking, setChecking] = useState(false);
  const [checked, setChecked] = useState<SignInCheck | null>(null);
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const choice = CHOICES.find((c) => c.auth === auth)!;
  const credential = data.credentials[auth];
  const changed = auth !== data.auth || value.trim() !== "";
  const needsValue = auth !== data.auth && credential.source === null && value.trim() === "";
  const nothingToCheck = credential.source === null && value.trim() === "";

  const check = async () => {
    setChecking(true);
    setChecked(null);
    try {
      setChecked(await api<SignInCheck>("POST", "/api/settings/claude/check", { auth, value: value.trim() || null }));
    } catch (e) {
      setChecked({ ok: false, error: (e as Error).message, model: null, seconds: 0 });
    } finally {
      setChecking(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const state = await api<ClaudeSettings>("PUT", "/api/settings/claude", { auth, value: value.trim() || null });
      queryClient.setQueryData(["settings-claude"], state);
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      void queryClient.invalidateQueries({ queryKey: ["restart-needed"] });
      void queryClient.invalidateQueries({ queryKey: ["health"] });
      setValue("");
      toast.success(state.auth !== state.running_auth ? "Saved. Restart ai-os to switch." : "Saved. The next turn uses it.");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
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
    <Card className="max-w-3xl">
      <CardHeader>
        <CardTitle>Claude</CardTitle>
        <CardDescription>How ai-os signs in to Claude. The token or key is stored encrypted and never shown again.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div role="radiogroup" className="grid gap-3 sm:grid-cols-2">
          {CHOICES.map((c) => {
            const selected = c.auth === auth;
            return (
              <button
                key={c.auth}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => {
                  setAuth(c.auth);
                  setChecked(null);
                }}
                className={cn(
                  "flex flex-col gap-2 rounded-lg border p-4 text-left transition-colors hover:bg-muted/50",
                  selected && "border-primary ring-2 ring-primary/30",
                )}
              >
                <span className="flex items-center gap-2 font-medium">
                  <c.icon className="size-4" /> {c.title}
                  {c.auth === data.running_auth ? <Badge variant="secondary">in use</Badge> : null}
                </span>
                <span className="text-sm text-muted-foreground">{c.body}</span>
                <span className="flex items-center gap-2 text-xs text-muted-foreground">
                  <code>{data.credentials[c.auth].variable}</code> <SourceBadge source={data.credentials[c.auth].source} />
                </span>
              </button>
            );
          })}
        </div>

        <Label>
          {choice.field}
          <Input
            type="password"
            autoComplete="off"
            spellCheck={false}
            className="font-mono"
            placeholder={credential.source === "variable" ? "Set. Leave empty to keep it; paste to replace it." : choice.placeholder}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setChecked(null);
            }}
          />
          <Hint>
            {choice.hint}
            {credential.source === "environment"
              ? ` Now taken from the process environment (.env); one saved here takes precedence.`
              : null}
          </Hint>
        </Label>

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={save} disabled={!changed || needsValue || saving}>
            <Save /> Save
          </Button>
          <Button
            variant="outline"
            onClick={check}
            disabled={nothingToCheck || checking}
            title={value.trim() ? "Try the pasted value, without saving it" : "Try the stored one"}
          >
            {checking ? <Loader2 className="animate-spin" /> : <PlugZap />} Test
          </Button>
          {needsValue ? <Hint>Paste the {choice.field.toLowerCase()} first: none is set yet.</Hint> : null}
          {data.auth !== data.running_auth ? (
            <>
              <span className="text-sm">Saved as {CHOICES.find((c) => c.auth === data.auth)!.title}; applies after a restart.</span>
              <Button variant="outline" onClick={restart}>
                <Power /> Restart now
              </Button>
            </>
          ) : null}
        </div>
        {checked ? (
          <div
            role="status"
            className={cn(
              "flex items-start gap-2 rounded-lg p-3 text-sm",
              checked.ok ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive",
            )}
          >
            {checked.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" /> : <XCircle className="mt-0.5 size-4 shrink-0" />}
            <span>
              {checked.ok
                ? `Works: Claude answered${checked.model ? ` (${checked.model})` : ""} in ${checked.seconds} s.`
                : `Does not work: ${checked.error}`}
              {checked.ok && value.trim() ? " Not saved yet." : null}
            </span>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
