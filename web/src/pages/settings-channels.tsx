import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, CheckCircle2, Webhook, ExternalLink, LifeBuoy, Loader2, MessageSquare, PlugZap, Save, Send, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading } from "@/components/page";
import { VariableFieldInput } from "@/components/variable-field-input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { api, type ChannelSetting, type SetupProblem, type SetupStep } from "@/lib/api";
import { href } from "@/lib/router";
import { cn } from "@/lib/utils";
import { WebhookDestinations } from "./settings-webhooks";


export function ChannelsPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["settings-channels"],
    queryFn: () => api<{ channels: ChannelSetting[] }>("GET", "/api/settings/channels"),
  });
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} />;
  return (
    <div className="max-w-3xl space-y-3">
      <p className="text-sm text-muted-foreground">
        Where ai-os can be talked to, and where agents can send messages. Tokens and numbers are stored as Variables (a secret one
        encrypted); a value in the environment (.env) is used when none is set here. Changes apply after a restart. Who gets a message
        where is each user's channel account, under{" "}
        <a className="underline" href={href("settings", "users")}>
          Users
        </a>
        .
      </p>
      {data.channels.map((c) => (
        <ChannelCard key={JSON.stringify(c)} channel={c} />
      ))}
    </div>
  );
}

function ChannelCard({ channel: c }: { channel: ChannelSetting }) {
  const queryClient = useQueryClient();
  const initialValues = () => Object.fromEntries(c.fields.filter((f) => !f.secret && f.source === "variable").map((f) => [f.variable, f.value ?? ""]));
  const [enabled, setEnabled] = useState(c.enabled);
  const [values, setValues] = useState<Record<string, string>>(initialValues);
  const [busy, setBusy] = useState<"save" | "check" | null>(null);
  const [checked, setChecked] = useState<{ ok: boolean; detail: string } | null>(null);

  const typed = Object.fromEntries(Object.entries(values).filter(([k, v]) => v.trim() && v !== initialValues()[k]));
  const dirty = enabled !== c.enabled || Object.keys(typed).length > 0;

  const save = async () => {
    setBusy("save");
    try {
      const state = await api<{ channels: ChannelSetting[] }>("PUT", `/api/settings/channels/${c.name}`, {
        enabled: enabled !== c.enabled ? enabled : null,
        values: typed,
      });
      queryClient.setQueryData(["settings-channels"], state);
      void queryClient.invalidateQueries({ queryKey: ["restart-needed"] });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success(`${c.title} saved. Restart ai-os to apply it.`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const check = async () => {
    setBusy("check");
    setChecked(null);
    try {
      setChecked(await api<{ ok: boolean; detail: string }>("POST", `/api/settings/channels/${c.name}/check`, { values: typed }));
    } catch (e) {
      setChecked({ ok: false, detail: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  const pending = c.enabled !== c.running;
  return (
    <Card className={cn(!enabled && "opacity-80")}>
      <CardHeader className="flex-row items-start gap-3">
        <div className="flex-1 space-y-1">
          <CardTitle className="flex flex-wrap items-center gap-2">
            {c.title}
            {c.capabilities.includes("chat") ? (
              <Badge variant="secondary">
                <MessageSquare /> chat
              </Badge>
            ) : null}
            {c.capabilities.includes("send") ? (
              <Badge variant="secondary">
                <Send /> sends
              </Badge>
            ) : null}
            {c.capabilities.includes("webhook") ? (
              <Badge variant="secondary">
                <Webhook /> posts
              </Badge>
            ) : null}
            {c.running ? <Badge variant="success">running</Badge> : null}
            {pending ? <Badge variant="warning">{c.enabled ? "on after a restart" : "off after a restart"}</Badge> : null}
          </CardTitle>
          <CardDescription>{c.description}</CardDescription>
        </div>
        <label className="flex items-center gap-2 text-sm">
          {enabled ? "On" : "Off"}
          <Switch checked={enabled} onCheckedChange={setEnabled} aria-label={`${c.title} on`} />
        </label>
      </CardHeader>
      {c.fields.length || c.checkable || dirty || c.setup.length ? (
        <CardContent className="space-y-4">
          {c.setup.length ? <SetupGuide title={c.title} steps={c.setup} problems={c.problems} /> : null}
          {c.fields.map((f) => (
            <VariableFieldInput
              key={f.variable}
              field={f}
              value={values[f.variable] ?? ""}
              onChange={(v) => {
                setValues((all) => ({ ...all, [f.variable]: v }));
                setChecked(null);
              }}
            />
          ))}
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={save} disabled={!dirty || busy !== null}>
              {busy === "save" ? <Loader2 className="animate-spin" /> : <Save />} Save
            </Button>
            {c.checkable ? (
              <Button variant="outline" onClick={check} disabled={busy !== null} title="Try the values, typed or stored, without sending anything">
                {busy === "check" ? <Loader2 className="animate-spin" /> : <PlugZap />} Test
              </Button>
            ) : null}
          </div>
          {checked ? (
            <div
              role="status"
              className={cn("flex items-start gap-2 rounded-lg p-3 text-sm", checked.ok ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive")}
            >
              {checked.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" /> : <XCircle className="mt-0.5 size-4 shrink-0" />}
              <span>
                {checked.ok ? "Works" : "Does not work"}: {checked.detail}
                {checked.ok && Object.keys(typed).length ? ". Not saved yet." : null}
              </span>
            </div>
          ) : null}
          {c.capabilities.includes("webhook") ? <WebhookDestinations /> : null}
        </CardContent>
      ) : null}
    </Card>
  );
}

/** The steps on the provider's side and the usual problems, folded away until asked for. */
function SetupGuide({ title, steps, problems }: { title: string; steps: SetupStep[]; problems: SetupProblem[] }) {
  return (
    <details className="group rounded-lg border bg-muted/30 text-sm">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 font-medium">
        <BookOpen className="size-4" /> How to set up {title}
      </summary>
      <div className="space-y-4 px-3 pb-3">
        <ol className="list-decimal space-y-3 pl-5 text-muted-foreground">
          {steps.map((step) => (
            <li key={step.text}>
              <span className="text-foreground">{step.text}</span>
              {step.link ? (
                <>
                  {" "}
                  <a className="inline-flex items-center gap-1 text-foreground underline" href={step.link} target="_blank" rel="noopener noreferrer">
                    {new URL(step.link).host}
                    <ExternalLink className="size-3" />
                  </a>
                </>
              ) : null}
              {step.details.length ? (
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  {step.details.map((detail) => (
                    <li key={detail}>{detail}</li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ol>
        {problems.length ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 font-medium">
              <LifeBuoy className="size-4" /> Common problems
            </div>
            <dl className="space-y-2">
              {problems.map((problem) => (
                <div key={problem.symptom} className="rounded-md border bg-background p-2">
                  <dt className="font-medium">{problem.symptom}</dt>
                  <dd className="text-muted-foreground">{problem.fix}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}
      </div>
    </details>
  );
}
