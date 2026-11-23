import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Bot, CalendarClock, Code2, Download, ExternalLink, GitBranch, Plug, Plus, RefreshCw, Sparkles, Trash2, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ListView } from "@/components/list-view";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CheckRow } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Hint, Input, Label } from "@/components/ui/input";
import { VariableFieldInput } from "@/components/variable-field-input";
import {
  api,
  type StoreInstallRequest,
  type StoreInstallResult,
  type StoreItem,
  type StoreKind,
  type StoreRequirement,
  type StoreSource,
  type StoreState,
  type StoreUninstallResult,
} from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { when } from "@/lib/utils";

const KINDS: Record<StoreKind, { label: string; plural: string; icon: LucideIcon }> = {
  agent: { label: "agent", plural: "Agents", icon: Bot },
  connector: { label: "connector", plural: "Connectors", icon: Plug },
  skill: { label: "skill", plural: "Skills", icon: Sparkles },
  trigger: { label: "trigger", plural: "Triggers", icon: CalendarClock },
};

const ref = (r: { kind: StoreKind; id: string }) => `${KINDS[r.kind].label} ${r.id}`;
/** `kind:id` from an install result, as words. */
const named = (key: string) => key.replace(":", " ");
const QUERIES = ["store", "agents", "connectors", "skills", "triggers", "variables"];

const v = (version: string) => (/^\d/.test(version) ? `v${version}` : version);

/** What the main button does: install, add a trigger, update to a newer version, or reinstall. */
const verbOf = (item: StoreItem) =>
  item.update_available ? "Update" : item.installed ? "Reinstall" : item.kind === "trigger" ? "Add" : "Install";

const sourceName = (sources: StoreSource[], url: string) => {
  const s = sources.find((x) => x.url === url);
  return s?.name || url.replace(/^https?:\/\//, "");
};

export function StorePage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["store"],
    queryFn: () => api<StoreState>("GET", "/api/store"),
  });
  const [installing, setInstalling] = useState<StoreItem | null>(null);
  const refresh = useMutation({
    mutationFn: () => api<StoreState>("POST", "/api/store/refresh"),
    onSuccess: (state) => {
      queryClient.setQueryData(["store"], state);
      const failed = state.sources.filter((s) => s.error).length;
      if (failed) toast.error(`${failed} source${failed > 1 ? "s" : ""} could not be fetched.`);
      else toast.success("Sources fetched again.");
    },
    onError: (e) => toast.error(e.message),
  });
  const sources = data?.sources ?? [];
  return (
    <Page>
      <PageHeader
        title="Store"
        description="Agents, connectors, skills and triggers from template repositories. Each one is installed on its own, with what it needs from the same source; then it is yours to change like anything else."
        actions={
          <Button variant="outline" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
            <RefreshCw className={refresh.isPending ? "animate-spin" : undefined} /> Refresh
          </Button>
        }
      />
      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {data ? (
        <>
          <SourcesCard sources={sources} />
          <ListView
            items={data.items}
            keyOf={(i) => `${i.source} ${i.kind} ${i.id}`}
            text={(i) => `${i.title} ${i.id} ${i.description} ${i.category ?? ""} ${i.tags.join(" ")} ${i.author ?? ""}`}
            facets={[
              {
                label: "kinds",
                value: (i) => KINDS[i.kind].plural,
                options: ["Agents", "Connectors", "Skills", "Triggers"],
              },
              { label: "categories", value: (i) => i.category },
              { label: "sources", value: (i) => sourceName(sources, i.source) },
              { label: "states", value: (i) => (i.update_available ? "Updates available" : i.installed ? "Installed" : "Not installed"), options: ["Updates available", "Installed", "Not installed"] },
            ]}
            empty="No items: add a source, or fetch the sources again."
            className="md:grid-cols-2"
          >
            {(item) => <ItemCard item={item} sources={sources} onInstall={() => setInstalling(item)} />}
          </ListView>
        </>
      ) : null}
      <Dialog open={installing !== null} onOpenChange={(open) => !open && setInstalling(null)}>
        <DialogContent className="max-h-[90dvh] max-w-lg overflow-y-auto">
          {installing ? <InstallForm key={`${installing.source} ${installing.kind} ${installing.id}`} item={installing} sources={sources} onDone={() => setInstalling(null)} /> : null}
        </DialogContent>
      </Dialog>
    </Page>
  );
}

function SourcesCard({ sources }: { sources: StoreSource[] }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [adding, setAdding] = useState(false);
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const add = useMutation({
    mutationFn: () => api<StoreState>("POST", "/api/store/sources", { url: url.trim(), branch: branch.trim() || null }),
    onSuccess: (state) => {
      queryClient.setQueryData(["store"], state);
      const added = state.sources.find((s) => s.url === url.trim());
      if (added?.error) toast.error(`Added, but it could not be fetched: ${added.error}`);
      else toast.success("Source added.");
      setUrl("");
      setBranch("");
      setAdding(false);
    },
    onError: (e) => toast.error(e.message),
  });
  const remove = useMutation({
    mutationFn: (s: StoreSource) => api<StoreState>("DELETE", "/api/store/sources", { url: s.url }),
    onSuccess: (state) => {
      queryClient.setQueryData(["store"], state);
      toast.success("Source removed. What was installed from it stays.");
    },
    onError: (e) => toast.error(e.message),
  });
  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex-1 font-medium">Sources</div>
        {!adding ? (
          <Button size="sm" variant="outline" onClick={() => setAdding(true)}>
            <Plus /> Add source
          </Button>
        ) : null}
      </div>
      {sources.length === 0 ? <p className="text-sm text-muted-foreground">No sources. Add a git repository with templates.</p> : null}
      <div className="divide-y">
        {sources.map((s) => (
          <div key={s.url} className="flex items-start gap-3 py-2 first:pt-0 last:pb-0">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{s.name || "Not fetched yet"}</span>
                {s.branch ? (
                  <Badge variant="outline" className="gap-1">
                    <GitBranch /> {s.branch}
                  </Badge>
                ) : null}
                {s.error ? <Badge variant="destructive">fetch failed</Badge> : s.fetched_at ? <Badge variant="secondary">fetched {when(s.fetched_at)}</Badge> : null}
              </div>
              <div className="truncate font-mono text-xs text-muted-foreground">{s.url}</div>
              {s.description ? <p className="mt-0.5 text-sm text-muted-foreground">{s.description}</p> : null}
              {s.error ? <p className="mt-1 text-xs break-words text-destructive">{s.error}</p> : null}
            </div>
            <Button
              size="icon"
              variant="ghost"
              className="text-destructive"
              aria-label={`Remove ${s.url}`}
              disabled={remove.isPending}
              onClick={async () => {
                if (
                  await confirm({
                    title: `Remove ${s.name || s.url}?`,
                    body: "Its items leave the Store. What was installed from it stays as it is.",
                    action: "Remove",
                    destructive: true,
                  })
                )
                  remove.mutate(s);
              }}
            >
              <Trash2 />
            </Button>
          </div>
        ))}
      </div>
      {adding ? (
        <form
          className="space-y-3 border-t pt-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (url.trim()) add.mutate();
          }}
        >
          <Label>
            Repository URL
            <Input autoFocus spellCheck={false} className="font-mono" placeholder="https://github.com/you/ai-os-templates" value={url} onChange={(e) => setUrl(e.target.value)} />
            <Hint>A public git repository over https, laid out like the configuration repository, with a store.yaml.</Hint>
          </Label>
          <Label>
            Branch
            <Input spellCheck={false} className="font-mono" placeholder="the default branch" value={branch} onChange={(e) => setBranch(e.target.value)} />
          </Label>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setAdding(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!url.trim() || add.isPending}>
              {add.isPending ? "Fetching…" : "Add"}
            </Button>
          </div>
        </form>
      ) : null}
    </Card>
  );
}

function RequirementBadge({ r }: { r: StoreRequirement }) {
  if (r.installed) return <Badge variant="secondary">{ref(r)}</Badge>;
  if (r.in_source) return <Badge variant="outline">{ref(r)}, with it</Badge>;
  return <Badge variant="destructive">{ref(r)}, missing</Badge>;
}

function ItemCard({ item, sources, onInstall }: { item: StoreItem; sources: StoreSource[]; onInstall: () => void }) {
  const { icon: Icon, label } = KINDS[item.kind];
  return (
    <Card className="flex flex-col p-4">
      <div className="flex flex-1 items-start gap-3">
        <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <Icon className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{item.title}</span>
            <Badge variant="outline">{label}</Badge>
            {item.version ? <Badge variant="secondary">{v(item.version)}</Badge> : null}
            {item.installed ? <Badge variant="success">{item.installed_version ? `installed ${v(item.installed_version)}` : "installed"}</Badge> : null}
            {item.update_available && item.version ? <Badge variant="warning">Update to {v(item.version)}</Badge> : null}
            {item.code ? (
              <Badge variant="warning" className="gap-1">
                <Code2 /> runs code
              </Badge>
            ) : null}
          </div>
          {item.title !== item.id ? <code className="text-xs text-muted-foreground">{item.id}</code> : null}
          {item.description ? <p className="mt-1 line-clamp-3 text-sm text-muted-foreground">{item.description}</p> : null}
          {item.tags.length ? (
            <div className="mt-2 flex flex-wrap gap-1">
              {item.tags.map((t) => (
                <Badge key={t} variant="outline" className="px-1.5 font-normal text-muted-foreground">
                  {t}
                </Badge>
              ))}
            </div>
          ) : null}
          {item.requires.length ? (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-muted-foreground">Needs</span>
              {item.requires.map((r) => (
                <RequirementBadge key={`${r.kind} ${r.id}`} r={r} />
              ))}
            </div>
          ) : null}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3">
        <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
          {[item.category, sourceName(sources, item.source), item.author ? `by ${item.author}` : null, item.license].filter(Boolean).join(" · ")}
        </span>
        <Homepage item={item} />
        {item.installed && item.removable ? <UninstallButton item={item} /> : null}
        <Button size="sm" variant={item.installed && !item.update_available ? "outline" : "default"} onClick={onInstall}>
          <Download /> {verbOf(item)}
        </Button>
      </div>
    </Card>
  );
}

function UninstallButton({ item }: { item: StoreItem }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const kind = KINDS[item.kind].label;
  const uninstall = useMutation({
    mutationFn: () => api<StoreUninstallResult>("POST", "/api/store/uninstall", { kind: item.kind, id: item.id }),
    onSuccess: (result) => {
      const removed = `Removed ${result.removed.map(named).join(", ") || "nothing"}.`;
      if (result.still_used_by.length) toast.warning(`${removed} Still referred to by ${result.still_used_by.map(named).join(", ")}: edit them.`);
      else toast.success(removed);
      for (const key of QUERIES) void queryClient.invalidateQueries({ queryKey: [key] });
    },
    onError: (e) => toast.error(e.message),
  });
  const ask = async () => {
    const body = [
      item.installed_version
        ? `Removes the ${kind} ${item.id}${item.code ? ", and its code folder in the configuration repository" : ""}.`
        : `The ${kind} ${item.id} was not installed from the Store: it was made by hand, or installed before versions were kept. Removing it removes your own ${kind}${item.code ? " and its code folder" : ""}.`,
      "What it brought along stays, and so do its Variables and sign-ins.",
      item.used_by.length ? `It is still used by ${item.used_by.map(named).join(", ")}; edit those afterwards.` : null,
    ].filter(Boolean);
    if (await confirm({ title: `Uninstall ${item.title}?`, body: body.join(" "), action: "Uninstall", destructive: true })) uninstall.mutate();
  };
  return (
    <Button size="sm" variant="outline" className="text-destructive" disabled={uninstall.isPending} onClick={() => void ask()}>
      <Trash2 /> {uninstall.isPending ? "Removing…" : "Uninstall"}
    </Button>
  );
}

function Homepage({ item }: { item: StoreItem }) {
  if (!item.homepage || !/^https?:\/\//.test(item.homepage)) return null;
  return (
    <a href={item.homepage} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground" title={item.homepage}>
      <ExternalLink className="size-3" /> homepage
    </a>
  );
}

/** Version, author, licence, tags and homepage, at the top of the install dialog. */
function Metadata({ item }: { item: StoreItem }) {
  const facts = [
    item.version ? `version ${v(item.version)}` : null,
    item.installed ? (item.installed_version ? `installed ${v(item.installed_version)}` : "installed") : null,
    item.author ? `by ${item.author}` : null,
    item.license,
  ].filter(Boolean);
  if (!facts.length && !item.tags.length && !item.homepage) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
      {facts.length ? <span>{facts.join(" · ")}</span> : null}
      {item.tags.map((t) => (
        <Badge key={t} variant="outline" className="px-1.5 font-normal text-muted-foreground">
          {t}
        </Badge>
      ))}
      <Homepage item={item} />
    </div>
  );
}

function InstallForm({ item, sources, onDone }: { item: StoreItem; sources: StoreSource[]; onDone: () => void }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [trusted, setTrusted] = useState(false);
  const withIt = item.requires.filter((r) => r.in_source && !r.installed);
  const kept = item.requires.filter((r) => r.installed);
  const missing = item.requires.filter((r) => !r.in_source && !r.installed);
  const install = useMutation({
    mutationFn: (body: StoreInstallRequest) => api<StoreInstallResult>("POST", "/api/store/install", body),
    onSuccess: (result) => {
      const parts = [`Installed ${result.installed.map(named).join(", ") || "nothing"}${result.version ? ` (${v(result.version)})` : ""}.`];
      if (result.kept.length) parts.push(`Kept as they were: ${result.kept.map(named).join(", ")}.`);
      if (result.moved_secrets.length) parts.push(`Moved to Variables: ${result.moved_secrets.join(", ")}.`);
      if (result.missing.length) toast.warning(`${parts.join(" ")} Still missing: ${result.missing.map(named).join(", ")}.`);
      else toast.success(parts.join(" "));
      for (const key of QUERIES) void queryClient.invalidateQueries({ queryKey: [key] });
      onDone();
    },
    onError: (e) => toast.error(e.message),
  });
  const verb = verbOf(item);
  const submit = async () => {
    // An update replaces it too, but is what the administrator came for: no question.
    if (
      item.installed &&
      !item.update_available &&
      !(await confirm({
        title: `Reinstall ${item.title}?`,
        body: `This replaces the ${KINDS[item.kind].label} ${item.id} with the template, and with it any change made to it here. What it needs stays as it is.`,
        action: "Reinstall",
        destructive: true,
      }))
    )
      return;
    install.mutate({ source: item.source, kind: item.kind, id: item.id, variables, replace: item.installed, trust_code: trusted });
  };
  return (
    <form
      className="grid min-w-0 gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <div className="space-y-1">
        <DialogTitle>
          {verb} {item.title}
        </DialogTitle>
        <DialogDescription>
          The {KINDS[item.kind].label} <code>{item.id}</code> from {sourceName(sources, item.source)}.
          {item.kind === "trigger" ? " It runs for you, and each time it is added it is a new trigger." : null}
          {item.update_available && item.version
            ? ` Updating to ${v(item.version)} replaces it, and any change made to it here. What it needs stays as it is.`
            : null}
        </DialogDescription>
        <Metadata item={item} />
      </div>
      {item.description ? <p className="text-sm">{item.description}</p> : null}
      {item.notes.trim() ? <div className="rounded-md bg-muted p-3 text-sm whitespace-pre-wrap">{item.notes.trim()}</div> : null}
      {withIt.length || kept.length || missing.length ? (
        <div className="space-y-1.5 text-sm">
          {withIt.length ? (
            <p>
              <span className="text-muted-foreground">Installed with it: </span>
              {withIt.map(ref).join(", ")}
            </p>
          ) : null}
          {kept.length ? (
            <p>
              <span className="text-muted-foreground">Already here, kept as they are: </span>
              {kept.map(ref).join(", ")}
            </p>
          ) : null}
          {missing.length ? (
            <p className="text-destructive">
              Not in this source and not here: {missing.map(ref).join(", ")}. It installs, but does not work until you add them.
            </p>
          ) : null}
        </div>
      ) : null}
      {item.variables.length ? (
        <div className="space-y-3 rounded-md border p-3">
          <div className="text-sm font-medium">Variables</div>
          <Hint className="block">Stored as Variables, a secret one encrypted. Leave one empty to keep what is set, or to set it later on the Variables page.</Hint>
          {item.variables.map((f) => (
            <VariableFieldInput key={f.variable} field={f} value={variables[f.variable] ?? ""} onChange={(v) => setVariables({ ...variables, [f.variable]: v })} />
          ))}
        </div>
      ) : null}
      {item.code ? (
        <div className="space-y-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
          <div className="flex items-center gap-2 font-medium text-destructive">
            <AlertTriangle className="size-4" /> This runs code on this server
          </div>
          <p>
            A code connector is a program from this source, copied into your configuration repository and started by ai-os. It sees only the variables
            it declares, but it runs with ai-os's network access. Install it only from a source you trust, and read its code first.
          </p>
          <CheckRow label="I trust this source to run code on this server" checked={trusted} onChange={setTrusted} />
        </div>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" variant={item.installed && !item.update_available ? "destructive" : "default"} disabled={install.isPending || (item.code && !trusted)}>
          <Download /> {install.isPending ? "Installing…" : verb}
        </Button>
      </div>
    </form>
  );
}
