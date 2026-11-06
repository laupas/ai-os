import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, KeyRound, Pencil, Plus, Variable as VariableIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ListView } from "@/components/list-view";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Hint, Input, Label, Textarea } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { api, type Variable } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { href } from "@/lib/router";
import { when } from "@/lib/utils";

export function VariablesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["variables"],
    queryFn: () => api<{ variables: Variable[] }>("GET", "/api/variables"),
  });
  const [editing, setEditing] = useState<Variable | "new" | null>(null);
  return (
    <Page className="max-w-3xl">
      <PageHeader
        title="Variables"
        description={
          <>
            Values and secrets for connectors, written <code>{"${NAME}"}</code> in a connector's settings, or <code>{"${file:NAME}"}</code>{" "}
            for a server that wants the path of a file holding it. A secret is stored encrypted and never shown again.
          </>
        }
        actions={
          <Button onClick={() => setEditing("new")}>
            <Plus /> New variable
          </Button>
        }
      />
      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {data ? (
        <ListView
          items={data.variables}
          keyOf={(v) => v.name}
          text={(v) => `${v.name} ${v.description} ${v.used_by.join(" ")}`}
          facets={[
            { label: "kinds", value: (v) => (v.file ? "file" : v.secret ? "secret" : "value"), options: ["value", "secret", "file"] },
            { label: "connectors", value: (v) => (v.used_by.length ? v.used_by : "unused") },
          ]}
          empty="No variables yet."
        >
          {(v) => (
          <Card className="p-4">
            <div className="flex items-start gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                {v.file ? <FileText className="size-4" /> : v.secret ? <KeyRound className="size-4" /> : <VariableIcon className="size-4" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <code className="font-medium">{v.name}</code>
                  {v.secret ? <Badge variant="secondary">secret</Badge> : null}
                  {v.file ? <Badge variant="outline">file</Badge> : null}
                </div>
                {v.description ? <p className="mt-1 text-sm text-muted-foreground">{v.description}</p> : null}
                {v.value !== null && !v.file ? <code className="mt-1 block truncate text-xs text-muted-foreground">{v.value}</code> : null}
                <p className="mt-1 text-xs text-muted-foreground">
                  {v.updated_by ? `Set by ${v.updated_by}` : "Set"}
                  {v.updated_at ? ` · ${when(v.updated_at)}` : ""}
                  {" · used by "}
                  {v.used_by.length
                    ? v.used_by.map((c, i) => (
                        <span key={c}>
                          {i ? ", " : ""}
                          <a className="underline" href={href("connectors")}>
                            {c}
                          </a>
                        </span>
                      ))
                    : "no connector"}
                </p>
              </div>
              <Button size="sm" variant="outline" onClick={() => setEditing(v)}>
                <Pencil /> Edit
              </Button>
            </div>
          </Card>
          )}
        </ListView>
      ) : null}
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent side="right" className="gap-0 p-0 sm:max-w-xl">
          {editing !== null ? <VariableForm variable={editing === "new" ? null : editing} onDone={() => setEditing(null)} /> : null}
        </SheetContent>
      </Sheet>
    </Page>
  );
}

function VariableForm({ variable: v, onDone }: { variable: Variable | null; onDone: () => void }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [name, setName] = useState("");
  const [description, setDescription] = useState(v?.description ?? "");
  const [secret, setSecret] = useState(v?.secret ?? true);
  const [file, setFile] = useState(v?.file ?? false);
  const [value, setValue] = useState(v && !v.secret ? (v.value ?? "") : "");
  const [busy, setBusy] = useState(false);
  // A secret's value is never shown; left empty, the stored one is kept.
  const keepsValue = v !== null && v.secret && secret && value === "";
  const done = () => {
    void queryClient.invalidateQueries({ queryKey: ["variables"] });
    void queryClient.invalidateQueries({ queryKey: ["connectors"] });
    onDone();
  };
  const save = async () => {
    setBusy(true);
    try {
      const body = { description: description.trim(), secret, file, value: keepsValue ? null : value };
      if (v) await api("PUT", `/api/variables/${encodeURIComponent(v.name)}`, body);
      else await api("POST", "/api/variables", { ...body, name: name.trim() });
      toast.success("Saved. Applies to the next turn.");
      done();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!v) return;
    const users = v.used_by.length ? ` ${v.used_by.join(", ")} will miss it.` : "";
    if (!(await confirm({ title: `Delete ${v.name}?`, body: `This cannot be undone.${users}`, action: "Delete", destructive: true }))) return;
    try {
      await api("DELETE", `/api/variables/${encodeURIComponent(v.name)}`);
      done();
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
        <SheetTitle>{v ? v.name : "New variable"}</SheetTitle>
        <SheetDescription>Kept in the data dir, never in the configuration repository. Agents cannot read it.</SheetDescription>
      </SheetHeader>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {v ? null : (
          <Label>
            Name
            <Input required pattern="[A-Z][A-Z0-9_]*" className="font-mono" value={name} onChange={(e) => setName(e.target.value.toUpperCase())} placeholder="GMAIL_OAUTH_KEYS" />
            <Hint>Upper-case letters, digits and _. A connector refers to it as {"${"}{name || "NAME"}{"}"}.</Hint>
          </Label>
        )}
        <Label>
          Description
          <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What it is, where it came from" />
        </Label>
        <div className="flex flex-wrap gap-6">
          <label className="flex items-center gap-3 text-sm font-medium">
            <Switch checked={secret} onCheckedChange={setSecret} /> Secret
          </label>
          <label className="flex items-center gap-3 text-sm font-medium">
            <Switch checked={file} onCheckedChange={setFile} /> Use as a file
          </label>
        </div>
        <Label>
          {file ? "File content" : "Value"}
          <Textarea
            rows={file ? 10 : 3}
            spellCheck={false}
            className="font-mono text-xs md:text-xs"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={v?.secret && secret ? "Set. Leave empty to keep it; type to replace it." : file ? "Paste the file, e.g. a JSON key file" : ""}
          />
          <Hint>
            {file ? <>Refer to it as {"${file:"}{v?.name ?? (name || "NAME")}{"}"}: the connector gets the path of a file holding this.</> : null}
            {v && v.secret !== secret ? " Changing whether it is secret needs the value again." : null}
          </Hint>
        </Label>
      </div>
      <div className="flex gap-2 border-t p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <Button type="submit" disabled={busy || (!v && (!name.trim() || !value))} className="flex-1 sm:flex-none">
          {v ? "Save" : "Create"}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <span className="flex-1" />
        {v ? (
          <Button type="button" variant="ghost" className="text-destructive" onClick={remove}>
            Delete
          </Button>
        ) : null}
      </div>
    </form>
  );
}
