import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CloudDownload, CloudUpload, Copy, GitBranch, GitCompare, GitMerge, KeyRound, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Hint, Input, Label, NativeSelect } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, type GitBranchRow, type GitOverview, type GitRemoteInfo, type RemoteResult } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { when } from "@/lib/utils";

export const useRemote = () => useQuery({ queryKey: ["git-remote"], queryFn: () => api<GitRemoteInfo>("GET", "/api/git/remote") });

export const useGit = () => useQuery({ queryKey: ["git"], queryFn: () => api<GitOverview>("GET", "/api/git"), refetchInterval: 30_000 });

/** The Git tab of Settings: the configuration repository's remote and branches. */
export function GitPanel() {
  const { data, isLoading, error } = useGit();
  const [creating, setCreating] = useState(false);
  const [merging, setMerging] = useState<string | null>(null);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start gap-3">
        <p className="min-w-0 flex-1 text-sm text-muted-foreground">
          The whole configuration (aios.yaml, agents, skills, connectors, schedules, roles) is a git repository. Each branch is a version of
          it; ai-os runs the one checked out.
        </p>
        <Button onClick={() => setCreating(true)} disabled={!data}>
          <Plus /> New branch
        </Button>
      </div>
      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      <RemoteCard />
      {data && !data.clean ? (
        <Card className="mb-3 border-warning/50 p-3 text-sm">
          The repository has uncommitted edits (made outside the console). Commit or discard them on the host before switching branches.
        </Card>
      ) : null}
      <div className="grid gap-3">
        {data?.branches.map((b) => (
          <BranchCard key={b.name} branch={b} data={data} onMerge={() => setMerging(b.name)} />
        ))}
      </div>
      {data ? <NewBranch open={creating} onOpenChange={setCreating} data={data} /> : null}
      {data && merging ? <MergeDialog source={merging} data={data} onClose={() => setMerging(null)} /> : null}
    </div>
  );
}

function useRefreshAll() {
  const queryClient = useQueryClient();
  // Switching or merging into the running branch changes every configuration page.
  return () => void queryClient.invalidateQueries();
}

function BranchCard({ branch: b, data, onMerge }: { branch: GitBranchRow; data: GitOverview; onMerge: () => void }) {
  const refreshAll = useRefreshAll();
  const { data: remote } = useRemote();
  const onRemote = remote?.url ? remote.branches[b.name] : undefined;
  const push = async () => {
    try {
      const result = await api<RemoteResult>("POST", "/api/git/push", { branch: b.name });
      toast.success(result.message || "Pushed.");
    } catch (e) {
      toast.error((e as Error).message);
    }
    refreshAll();
  };
  const pull = async () => {
    const response = await fetch("/api/git/pull", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Aios": "1" },
      body: JSON.stringify({ branch: b.name }),
    });
    if (response.status === 409) toast.error(`Not pulled: both sides changed ${(await response.json()).conflicts.join(", ")}`);
    else if (!response.ok) toast.error(await response.text());
    else toast.success(`${b.name} is up to date with the remote.`);
    refreshAll();
  };
  const confirm = useConfirm();
  const [files, setFiles] = useState<{ status: string; path: string }[] | null>(null);
  const [busy, setBusy] = useState(false);
  const switchTo = async () => {
    if (!(await confirm({ title: `Switch to ${b.name}?`, body: "ai-os runs this branch's agents, skills, connectors and schedules from the next turn.", action: "Switch" })))
      return;
    setBusy(true);
    try {
      await api("POST", "/api/git/switch", { branch: b.name });
      toast.success(`ai-os now runs ${b.name}.`);
      refreshAll();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const compare = async () => {
    if (files) return setFiles(null);
    try {
      const result = await api<{ files: { status: string; path: string }[] }>("GET", `/api/git/compare?branch=${encodeURIComponent(b.name)}`);
      setFiles(result.files);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const remove = async (force = false) => {
    const ok = await confirm({
      title: `Delete ${b.name}?`,
      body: force ? "Its changes that are on no other branch are lost for good." : "Only possible when its changes are merged somewhere.",
      action: "Delete",
      destructive: true,
    });
    if (!ok) return;
    try {
      await api("POST", "/api/git/delete", { branch: b.name, force });
      refreshAll();
    } catch (e) {
      const message = (e as Error).message;
      if (!force && message.includes("delete it anyway")) return remove(true);
      toast.error(message);
    }
  };
  const label: Record<string, string> = { A: "added", M: "changed", D: "deleted", R: "renamed" };
  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <GitBranch className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <code className="font-medium">{b.name}</code>
            {b.current ? <Badge variant="success">running</Badge> : null}
            {b.name === data.protected ? <Badge variant="secondary">main</Badge> : null}
            {!b.current && (b.ahead || b.behind) ? (
              <span className="text-xs text-muted-foreground">
                {b.ahead} ahead, {b.behind} behind {data.current}
              </span>
            ) : null}
            {!b.current && !b.ahead && !b.behind ? <span className="text-xs text-muted-foreground">same as {data.current}</span> : null}
          </div>
          {remote?.url ? (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {onRemote === null
                ? "not on the remote yet"
                : onRemote === undefined
                  ? ""
                  : onRemote.ahead === 0 && onRemote.behind === 0
                    ? "same as on the remote"
                    : `remote: ${onRemote.ahead} to push, ${onRemote.behind} to pull`}
            </p>
          ) : null}
          <p className="mt-1 truncate text-sm">{b.subject}</p>
          <p className="text-xs text-muted-foreground">
            {b.author} · {when(b.date)} · <code>{b.commit.slice(0, 7)}</code>
          </p>
        </div>
      </div>
      {files ? (
        <div className="mt-3 rounded-md border bg-muted/30 p-2 text-xs">
          {files.length === 0 ? (
            <span className="text-muted-foreground">No changes since it left {data.current}.</span>
          ) : (
            <>
              <div className="mb-1 text-muted-foreground">
                Changed on {b.name} since it left {data.current}:
              </div>
              {files.map((f) => (
                <div key={f.path}>
                  <span className="inline-block w-16 text-muted-foreground">{label[f.status] ?? f.status}</span>
                  <code>{f.path}</code>
                </div>
              ))}
            </>
          )}
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2 border-t pt-3">
        {!b.current ? (
          <Button size="sm" onClick={switchTo} disabled={busy || !data.clean}>
            <GitBranch /> Switch to it
          </Button>
        ) : null}
        {!b.current ? (
          <Button size="sm" variant="outline" onClick={compare}>
            <GitCompare /> {files ? "Hide changes" : "Changes"}
          </Button>
        ) : null}
        <Button size="sm" variant="outline" onClick={onMerge} disabled={data.branches.length < 2}>
          <GitMerge /> Merge into…
        </Button>
        {remote?.url && (onRemote === null || (onRemote && onRemote.ahead > 0)) ? (
          <Button size="sm" variant="outline" onClick={push}>
            <CloudUpload /> Push
          </Button>
        ) : null}
        {remote?.url && onRemote && onRemote.behind > 0 ? (
          <Button size="sm" variant="outline" onClick={pull}>
            <CloudDownload /> Pull
          </Button>
        ) : null}
        <span className="flex-1" />
        {!b.current && b.name !== data.protected ? (
          <Button size="sm" variant="ghost" className="text-destructive" onClick={() => remove()}>
            <Trash2 /> Delete
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

function NewBranch({ open, onOpenChange, data }: { open: boolean; onOpenChange: (open: boolean) => void; data: GitOverview }) {
  const refreshAll = useRefreshAll();
  const [name, setName] = useState("");
  const [start, setStart] = useState(data.current);
  const [switchNow, setSwitchNow] = useState(true);
  const create = async () => {
    try {
      await api("POST", "/api/git/branches", { name: name.trim(), start });
      if (switchNow) await api("POST", "/api/git/switch", { branch: name.trim() });
      toast.success(switchNow ? `Created ${name}; ai-os now runs it.` : `Created ${name}.`);
      setName("");
      onOpenChange(false);
      refreshAll();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>New branch</DialogTitle>
        <DialogDescription>A copy of a branch to change without touching the original.</DialogDescription>
        <Label>
          Name
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="try-new-prompts" autoFocus />
          <Hint>Letters, digits, . _ - and at most one /.</Hint>
        </Label>
        <Label>
          From
          <NativeSelect value={start} onChange={(e) => setStart(e.target.value)}>
            {data.branches.map((b) => (
              <option key={b.name} value={b.name}>
                {b.name}
                {b.current ? " (running)" : ""}
              </option>
            ))}
          </NativeSelect>
        </Label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={switchNow} onChange={(e) => setSwitchNow(e.target.checked)} disabled={!data.clean} /> Switch ai-os to it now
        </label>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={create} disabled={!name.trim()}>
            Create
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function MergeDialog({ source, data, onClose }: { source: string; data: GitOverview; onClose: () => void }) {
  const refreshAll = useRefreshAll();
  const targets = data.branches.filter((b) => b.name !== source);
  const [into, setInto] = useState(targets.find((b) => b.name === data.protected)?.name ?? targets[0]?.name ?? "");
  const [conflicts, setConflicts] = useState<string[] | null>(null);
  const running = into === data.current;
  const merge = async () => {
    try {
      const response = await fetch("/api/git/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Aios": "1" },
        body: JSON.stringify({ source, into }),
      });
      if (response.status === 409) return setConflicts((await response.json()).conflicts);
      if (!response.ok) throw new Error(await response.text());
      toast.success(`Merged ${source} into ${into}.${running ? " ai-os runs the result from the next turn." : ""}`);
      onClose();
      refreshAll();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogTitle>Merge {source}</DialogTitle>
        <DialogDescription>Brings the changes of {source} into another branch. A conflict is undone, never left half-merged.</DialogDescription>
        <Label>
          Into
          <NativeSelect value={into} onChange={(e) => (setInto(e.target.value), setConflicts(null))}>
            {targets.map((b) => (
              <option key={b.name} value={b.name}>
                {b.name}
                {b.current ? " (running)" : ""}
              </option>
            ))}
          </NativeSelect>
          <Hint>{running ? "This is the branch ai-os runs: the merged configuration applies from the next turn." : "ai-os keeps running " + data.current + "; nothing changes until you switch."}</Hint>
        </Label>
        {conflicts ? (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs">
            <div className="font-medium">Not merged: both branches changed the same lines in</div>
            {conflicts.map((f) => (
              <code key={f} className="block">
                {f}
              </code>
            ))}
            <div className="mt-1 text-muted-foreground">Make them agree on one of the branches first (edit, or restore from History), then merge again.</div>
          </div>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={merge} disabled={!into}>
            <GitMerge /> Merge
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** owner/repo of a GitHub address, for links to its settings. */
function githubRepo(url: string): string | null {
  const m = url.match(/github\.com[:/]([^/]+\/[^/.]+?)(\.git)?$/);
  return m ? m[1] : null;
}

function RemoteCard() {
  const { data: remote, isLoading } = useRemote();
  const refreshAll = useRefreshAll();
  const [editing, setEditing] = useState(false);
  const [url, setUrl] = useState("");
  const [auth, setAuth] = useState<"ssh" | "token">("ssh");
  const [token, setToken] = useState("");
  const [autoPush, setAutoPush] = useState(true);
  const [busy, setBusy] = useState(false);
  if (isLoading || !remote) return null;
  const configured = Boolean(remote.url);
  const startEditing = () => {
    setUrl(remote.url);
    setAuth(remote.auth === "token" ? "token" : "ssh");
    setToken("");
    setAutoPush(configured ? remote.auto_push : true);
    setEditing(true);
  };
  const act = async (label: string, run: () => Promise<unknown>) => {
    setBusy(true);
    try {
      const result = (await run()) as RemoteResult | undefined;
      toast.success(result?.message ? `${label}: ${result.message}` : `${label}: done`);
    } catch (e) {
      toast.error(`${label}: ${(e as Error).message}`);
    } finally {
      setBusy(false);
      refreshAll();
    }
  };
  const save = () =>
    act("Saved", async () => {
      await api("PUT", "/api/git/remote", { url: url.trim(), auth, token: token || null, auto_push: autoPush });
      setEditing(false);
    });
  const repo = githubRepo(editing ? url : remote.url);
  const copy = (text: string) => navigator.clipboard.writeText(text).then(() => toast.success("Copied."));
  return (
    <Card className="mb-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Remote</span>
        {configured ? <code className="truncate text-xs text-muted-foreground">{remote.url}</code> : null}
        {configured ? <Badge variant="outline">{remote.auth === "token" ? "GitHub token" : remote.auth === "ssh" ? "SSH key" : "no sign-in"}</Badge> : null}
        {configured && remote.auto_push ? <Badge variant="success">auto-push</Badge> : null}
        <span className="flex-1" />
        {!editing ? (
          <Button size="sm" variant="outline" onClick={startEditing}>
            {configured ? "Edit" : "Set up"}
          </Button>
        ) : null}
      </div>
      {!configured && !editing ? (
        <p className="mt-1 text-sm text-muted-foreground">No remote yet: the configuration exists only on this Mac. Push it to a private repository for an off-site copy.</p>
      ) : null}
      {configured && !editing ? (
        <>
          {remote.last ? (
            <p className={`mt-2 break-words text-xs ${remote.last.ok ? "text-muted-foreground" : "text-destructive"}`}>
              Last {remote.last.action}: {remote.last.ok ? "ok" : "failed"} · {when(remote.last.at)}
              {remote.last.message ? ` · ${remote.last.message}` : ""}
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2 border-t pt-3">
            <Button size="sm" variant="outline" disabled={busy} onClick={() => act("Connection", () => api("POST", "/api/git/remote/test"))}>
              <RefreshCw /> Test connection
            </Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => act("Fetch", () => api("POST", "/api/git/fetch"))}>
              <CloudDownload /> Fetch
            </Button>
            <Button size="sm" disabled={busy} onClick={() => act("Push", () => api("POST", "/api/git/push", {}))}>
              <CloudUpload /> Push all branches
            </Button>
          </div>
        </>
      ) : null}
      {editing ? (
        <div className="mt-3 space-y-4">
          <Tabs value={auth} onValueChange={(v) => setAuth(v as "ssh" | "token")}>
            <TabsList>
              <TabsTrigger value="ssh">SSH key</TabsTrigger>
              <TabsTrigger value="token">GitHub token</TabsTrigger>
            </TabsList>
          </Tabs>
          <Label>
            Repository address
            <Input
              className="font-mono"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder={auth === "ssh" ? "git@github.com:owner/ai-os-config.git" : "https://github.com/owner/ai-os-config.git"}
            />
            <Hint>An empty private repository works best: ai-os pushes every branch into it.</Hint>
          </Label>
          {auth === "ssh" ? (
            <div className="space-y-2 text-sm">
              <div className="font-medium">SSH key</div>
              {remote.public_key ? (
                <div className="flex items-start gap-2">
                  <code className="min-w-0 flex-1 break-all rounded-md border bg-muted/40 p-2 text-xs">{remote.public_key}</code>
                  <Button size="icon-sm" variant="outline" onClick={() => copy(remote.public_key!)} aria-label="Copy">
                    <Copy />
                  </Button>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">No key yet.</p>
              )}
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => act("Key", () => api("POST", "/api/git/remote/key"))}
                  disabled={busy}
                >
                  <KeyRound /> {remote.public_key ? "Make a new key" : "Generate a key"}
                </Button>
                {repo ? (
                  <a className="text-xs underline" href={`https://github.com/${repo}/settings/keys/new`} target="_blank" rel="noreferrer">
                    Add it on GitHub as a deploy key, with write access
                  </a>
                ) : null}
              </div>
              <Hint>The private half stays in ai-os, encrypted. A new key replaces the old one, which then has to be removed on GitHub.</Hint>
            </div>
          ) : (
            <Label>
              GitHub token
              <Input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder={remote.has_token ? "Set. Leave empty to keep it." : "github_pat_…"} />
              <Hint>
                A fine-grained token for this one repository with <em>Contents: read and write</em>:{" "}
                <a className="underline" href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noreferrer">
                  create one
                </a>
                . Stored encrypted, never shown again.
              </Hint>
            </Label>
          )}
          <label className="flex items-center gap-3 text-sm font-medium">
            <Switch checked={autoPush} onCheckedChange={setAutoPush} /> Push every change automatically
          </label>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={save} disabled={busy || !url.trim()}>
              Save
            </Button>
            <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <span className="flex-1" />
            {configured ? (
              <Button size="sm" variant="ghost" className="text-destructive" onClick={() => act("Removed", async () => (await api("DELETE", "/api/git/remote"), setEditing(false)))}>
                Remove remote
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}
    </Card>
  );
}
