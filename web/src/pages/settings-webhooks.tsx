import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, Pencil, Plus, Send, Trash2, TriangleAlert, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading } from "@/components/page";
import { HistoryButton } from "@/components/history-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Hint, Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { api, type WebhookDestination } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { href } from "@/lib/router";
import { cn } from "@/lib/utils";

type Listing = { enabled: boolean; destinations: WebhookDestination[] };
type BodyFormat = "json" | "text" | "none";

const DEFAULT_FIELDS = {
  type: "object",
  properties: { text: { type: "string", description: "The message" } },
  required: ["text"],
};

/** The webhook channel's destinations, inside its card in Settings → Channels.
 * Unlike the channel's switch, a destination applies at once. */
export function WebhookDestinations() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["webhooks"],
    queryFn: () => api<Listing>("GET", "/api/webhooks"),
  });
  const [editing, setEditing] = useState<WebhookDestination | "new" | null>(null);
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} />;
  return (
    <div className="space-y-2 border-t pt-4">
      <div className="flex items-center gap-2">
        <span className="flex-1 text-sm font-medium">Destinations</span>
        <Button size="sm" variant="outline" onClick={() => setEditing("new")}>
          <Plus /> New destination
        </Button>
      </div>
      {data.destinations.length ? (
        data.destinations.map((d) => (
          <div key={d.name} className={cn("flex items-start gap-3 rounded-lg border p-3", !d.enabled && "opacity-70")}>
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{d.name}</span>
                <Badge variant="outline">{d.method}</Badge>
                <Badge variant={d.approval === "allow" ? "warning" : d.approval === "deny" ? "destructive" : "secondary"}>
                  {d.approval === "ask" ? "asks first" : d.approval === "allow" ? "no approval" : "agents refused"}
                </Badge>
                {d.enabled ? null : <Badge variant="secondary">off</Badge>}
              </div>
              {d.description ? <p className="text-sm text-muted-foreground">{d.description}</p> : null}
              <p className="truncate font-mono text-xs text-muted-foreground">{d.url}</p>
              {d.missing.length ? (
                <p className="flex items-center gap-1 text-xs text-destructive">
                  <TriangleAlert className="size-3" /> Not set:{" "}
                  <a className="underline" href={href("variables")}>
                    {d.missing.join(", ")}
                  </a>
                </p>
              ) : null}
            </div>
            <Button size="sm" variant="outline" onClick={() => setEditing(d)}>
              <Pencil /> Edit
            </Button>
          </div>
        ))
      ) : (
        <p className="text-sm text-muted-foreground">No destinations yet.</p>
      )}
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent side="right" className="gap-0 p-0 sm:max-w-2xl">
          {editing !== null ? <DestinationForm destination={editing === "new" ? null : editing} onDone={() => setEditing(null)} /> : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function bodyFormat(body: unknown): BodyFormat {
  if (body === null || body === undefined || body === "") return "none";
  return typeof body === "string" ? "text" : "json";
}

function sampleFields(schemaText: string): string {
  try {
    const properties = JSON.parse(schemaText).properties ?? {};
    const sample = Object.fromEntries(
      Object.entries(properties as Record<string, { type?: string }>).map(([k, p]) => [
        k,
        p.type === "number" || p.type === "integer" ? 0 : p.type === "boolean" ? false : "Test from ai-os",
      ]),
    );
    return JSON.stringify(sample, null, 2);
  } catch {
    return "{}";
  }
}

function DestinationForm({ destination: d, onDone }: { destination: WebhookDestination | null; onDone: () => void }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [name, setName] = useState("");
  const [description, setDescription] = useState(d?.description ?? "");
  const [method, setMethod] = useState<WebhookDestination["method"]>(d?.method ?? "POST");
  const [url, setUrl] = useState(d?.url ?? "");
  const [headers, setHeaders] = useState<[string, string][]>(Object.entries(d?.headers ?? {}));
  const [fields, setFields] = useState(JSON.stringify(d?.fields ?? DEFAULT_FIELDS, null, 2));
  const [format, setFormat] = useState<BodyFormat>(d ? bodyFormat(d.body) : "json");
  const [body, setBody] = useState(
    d ? (typeof d.body === "string" ? d.body : d.body == null ? "" : JSON.stringify(d.body, null, 2)) : '{\n  "text": "{{text}}"\n}',
  );
  const [approval, setApproval] = useState<WebhookDestination["approval"]>(d?.approval ?? "ask");
  const [enabled, setEnabled] = useState(d?.enabled ?? true);
  const [sample, setSample] = useState(() => sampleFields(fields));
  const [busy, setBusy] = useState<"save" | "test" | null>(null);
  const [tested, setTested] = useState<{ ok: boolean; detail: string } | null>(null);

  /** The destination as typed, or a message saying which part is not JSON. */
  const typed = (): Record<string, unknown> | string => {
    let parsedFields: unknown;
    try {
      parsedFields = JSON.parse(fields);
    } catch {
      return "Fields is not valid JSON.";
    }
    let parsedBody: unknown = null;
    if (format === "json") {
      try {
        parsedBody = JSON.parse(body);
      } catch {
        return "Body is not valid JSON; choose Text to send it as written.";
      }
    } else if (format === "text") parsedBody = body;
    return {
      description: description.trim(),
      method,
      url: url.trim(),
      headers: Object.fromEntries(headers.filter(([k]) => k.trim()).map(([k, v]) => [k.trim(), v])),
      fields: parsedFields,
      body: method === "GET" ? null : parsedBody,
      approval,
      enabled,
    };
  };

  const save = async () => {
    const value = typed();
    if (typeof value === "string") return toast.error(value);
    setBusy("save");
    try {
      if (d) await api("PUT", `/api/webhooks/${encodeURIComponent(d.name)}`, value);
      else await api("POST", "/api/webhooks", { ...value, name: name.trim() });
      toast.success("Saved. Applies to the next turn.");
      void queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const test = async () => {
    const value = typed();
    if (typeof value === "string") return setTested({ ok: false, detail: value });
    let sampleFieldsValue: unknown;
    try {
      sampleFieldsValue = JSON.parse(sample);
    } catch {
      return setTested({ ok: false, detail: "the sample fields are not valid JSON" });
    }
    setBusy("test");
    setTested(null);
    try {
      setTested(
        await api<{ ok: boolean; detail: string }>("POST", "/api/webhooks/test", {
          destination: { ...value, name: d?.name ?? (name.trim() || "test") },
          fields: sampleFieldsValue,
        }),
      );
    } catch (e) {
      setTested({ ok: false, detail: (e as Error).message });
    } finally {
      setBusy(null);
    }
  };

  const remove = async () => {
    if (!d) return;
    const ok = await confirm({ title: `Delete ${d.name}?`, body: "Agents can no longer post to it.", action: "Delete", destructive: true });
    if (!ok) return;
    try {
      await api("DELETE", `/api/webhooks/${encodeURIComponent(d.name)}`);
      void queryClient.invalidateQueries({ queryKey: ["webhooks"] });
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
        <SheetTitle>{d ? d.name : "New destination"}</SheetTitle>
        <SheetDescription>
          {"{{field}}"} is a value the agent gives, ${"{NAME}"} the Variable NAME. Applies to the next turn.
        </SheetDescription>
      </SheetHeader>
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        {d ? null : (
          <Label>
            Name
            <Input required pattern="[a-z][a-z0-9\-]*" value={name} onChange={(e) => setName(e.target.value)} placeholder="n8n-alerts" />
            <Hint>Lower-case letters, digits and dashes. Agents pick the destination by it.</Hint>
          </Label>
        )}
        <Label>
          What it is for
          <Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Posts an alert into the family Teams channel." />
          <Hint>Agents read this to decide when to use it.</Hint>
        </Label>
        <div className="flex gap-2">
          <Label className="w-28 shrink-0">
            Method
            <NativeSelect value={method} onChange={(e) => setMethod(e.target.value as WebhookDestination["method"])}>
              {["POST", "PUT", "PATCH", "GET"].map((m) => (
                <option key={m}>{m}</option>
              ))}
            </NativeSelect>
          </Label>
          <Label className="flex-1">
            URL
            <Input required className="font-mono text-xs" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://n8n.example.com/webhook/${N8N_HOOK_ID}" />
          </Label>
        </div>
        <Hint className="-mt-2">A field in the URL is percent-encoded. A token in the URL belongs in a Variable: ${"{NAME}"}.</Hint>
        <div className="space-y-1.5">
          <div className="text-sm font-medium">Headers</div>
          {headers.map(([k, v], i) => (
            <div key={i} className="flex gap-2">
              <Input
                className="w-48 font-mono text-xs"
                value={k}
                placeholder="Authorization"
                onChange={(e) => setHeaders((all) => all.map((h, j) => (j === i ? [e.target.value, h[1]] : h)))}
              />
              <Input
                className="flex-1 font-mono text-xs"
                value={v}
                placeholder="Bearer ${HOOK_TOKEN}"
                onChange={(e) => setHeaders((all) => all.map((h, j) => (j === i ? [h[0], e.target.value] : h)))}
              />
              <Button type="button" size="icon" variant="ghost" aria-label="Remove header" onClick={() => setHeaders((all) => all.filter((_, j) => j !== i))}>
                <Trash2 />
              </Button>
            </div>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={() => setHeaders((all) => [...all, ["", ""]])}>
            <Plus /> Header
          </Button>
          <Hint className="block">A literal secret in a header whose name says so (key, token, auth…) is moved into a Variable when saved.</Hint>
        </div>
        <Label>
          Fields
          <Textarea
            spellCheck={false}
            rows={8}
            className="font-mono text-xs md:text-xs"
            value={fields}
            onChange={(e) => setFields(e.target.value)}
            onBlur={() => setSample((s) => (s.trim() === "{}" || !s.trim() ? sampleFields(fields) : s))}
          />
          <Hint>JSON schema of what the agent fills in: one property per field, with a description the agent reads.</Hint>
        </Label>
        {method === "GET" ? null : (
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="flex-1 text-sm font-medium">Body</span>
              <NativeSelect className="w-28" value={format} onChange={(e) => setFormat(e.target.value as BodyFormat)} aria-label="Body format">
                <option value="json">JSON</option>
                <option value="text">Text</option>
                <option value="none">None</option>
              </NativeSelect>
            </div>
            {format === "none" ? null : (
              <Textarea spellCheck={false} rows={8} className="font-mono text-xs md:text-xs" value={body} onChange={(e) => setBody(e.target.value)} />
            )}
            <Hint className="block">
              {format === "json"
                ? 'Sent as JSON. A value that is exactly "{{field}}" keeps the field\'s type; inside other text it is put in as text.'
                : format === "text"
                  ? "Sent as written, e.g. a form (a={{a}}&b={{b}}); set Content-Type under Headers."
                  : "No body."}
            </Hint>
          </div>
        )}
        <div className="flex flex-wrap items-end gap-4">
          <Label className="w-56">
            Approval
            <NativeSelect value={approval} onChange={(e) => setApproval(e.target.value as WebhookDestination["approval"])}>
              <option value="ask">Ask before every post</option>
              <option value="allow">Post without asking</option>
              <option value="deny">Agents may not post</option>
            </NativeSelect>
          </Label>
          <label className="flex h-9 items-center gap-2 text-sm">
            <Switch checked={enabled} onCheckedChange={setEnabled} aria-label="Destination on" /> {enabled ? "On" : "Off"}
          </label>
        </div>
        <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
          <Label>
            Test with these fields
            <Textarea spellCheck={false} rows={4} className="font-mono text-xs md:text-xs" value={sample} onChange={(e) => setSample(e.target.value)} />
            <Hint>Really calls the destination, as typed above, saved or not.</Hint>
          </Label>
          <Button type="button" size="sm" variant="outline" onClick={test} disabled={busy !== null}>
            {busy === "test" ? <Loader2 className="animate-spin" /> : <Send />} Send test
          </Button>
          {tested ? (
            <div
              role="status"
              className={cn("flex items-start gap-2 rounded-lg p-3 text-sm", tested.ok ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive")}
            >
              {tested.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" /> : <XCircle className="mt-0.5 size-4 shrink-0" />}
              <span className="break-all">{tested.detail}</span>
            </div>
          ) : null}
        </div>
      </div>
      <div className="flex gap-2 border-t p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <Button type="submit" disabled={busy !== null} className="flex-1 sm:flex-none">
          {busy === "save" ? <Loader2 className="animate-spin" /> : null}
          {d ? "Save" : "Create"}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        {d ? <HistoryButton kind="webhooks" id={d.name} onRestored={onDone} /> : null}
        <span className="flex-1" />
        {d ? (
          <Button type="button" variant="ghost" className="text-destructive" onClick={remove}>
            Delete
          </Button>
        ) : null}
      </div>
    </form>
  );
}
