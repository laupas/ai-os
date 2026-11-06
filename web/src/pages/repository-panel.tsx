import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownToLine, ArrowUpFromLine, ChevronDown, ChevronRight, File, FilePlus, Folder, GitCommitHorizontal, History, Pencil, RefreshCw, RotateCcw, Save, Search, Trash2, X } from "lucide-react";
import { lazy, Suspense, useMemo, useState } from "react";
import { toast } from "sonner";
import { Diff } from "@/components/history-button";
import { ErrorBox, Loading } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { cn, when } from "@/lib/utils";
import { useGit } from "./git-page";

// CodeMirror is most of a megabyte: loaded when a file is first opened.
const CodeEditor = lazy(() => import("@/components/code-editor"));

interface TreeFile {
  path: string;
  blob: string;
  size: number;
}

interface RepoFile {
  path: string;
  blob: string;
  text: string | null;
  binary: boolean;
}

interface Commit {
  commit: string;
  author: string;
  email: string;
  date: string;
  subject: string;
  files: [string, string][];
}

/** What is open: a file at the branch's head (editable), at a commit (read only),
 * or new (`ref` empty). `draft` starts the editor with that text, for a restore. */
interface Opened {
  path: string;
  ref: string;
  draft?: string;
}

const STATUS: Record<string, string> = { A: "added", M: "changed", D: "deleted" };

interface RemoteStatus {
  configured: boolean;
  on_remote?: boolean;
  unpushed?: string[];
  behind?: number;
  fetched_at?: string | null;
}

/** The branch against its remote, as of the last fetch. */
function useRemoteStatus(branch: string) {
  return useQuery({
    queryKey: ["repo-remote", branch],
    queryFn: () => api<RemoteStatus>("GET", `/api/repository/remote?branch=${encodeURIComponent(branch)}`),
    enabled: Boolean(branch),
    refetchInterval: 30_000,
  });
}

/** "Not pushed yet" on a commit: only here, in this repository, until a push. */
function LocalBadge({ commit, unpushed }: { commit: string; unpushed: Set<string> }) {
  return unpushed.has(commit) ? (
    <Badge variant="warning" className="shrink-0" title="Committed here, not on the remote yet">
      local
    </Badge>
  ) : null;
}

/** Whether the branch is on the remote, what is not pushed or not pulled yet, and
 * the three buttons for it. Auto-push sends ai-os's own commits; a commit made on
 * the host waits here until pushed. */
function RemoteBar({ branch }: { branch: string }) {
  const queryClient = useQueryClient();
  const { data } = useRemoteStatus(branch);
  const [busy, setBusy] = useState<string | null>(null);
  if (!data) return null;
  if (!data.configured)
    return <p className="text-xs text-muted-foreground">No remote: everything is local. Set one up under Branches.</p>;
  const unpushed = data.unpushed?.length ?? 0;
  const behind = data.behind ?? 0;
  const run = async (action: "push" | "pull" | "fetch") => {
    setBusy(action);
    try {
      if (action === "fetch") await api("POST", "/api/git/fetch");
      else await api("POST", `/api/git/${action}`, { branch });
      toast.success(action === "push" ? `Pushed ${branch}.` : action === "pull" ? `Pulled into ${branch}.` : "Fetched.");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
      for (const key of ["repo-remote", "repo-history", "repo-tree", "repo-file", "git", "git-remote"]) void queryClient.invalidateQueries({ queryKey: [key] });
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm">
      {!data.on_remote ? (
        <Badge variant="warning">not on the remote yet</Badge>
      ) : unpushed || behind ? (
        <>
          {unpushed ? <Badge variant="warning">{unpushed} commit{unpushed === 1 ? "" : "s"} not pushed</Badge> : null}
          {behind ? <Badge variant="secondary">{behind} to pull</Badge> : null}
        </>
      ) : (
        <Badge variant="success">same as the remote</Badge>
      )}
      <span className="min-w-0 flex-1 text-xs text-muted-foreground">{data.fetched_at ? `as of the last fetch, ${when(data.fetched_at)}` : "never fetched"}</span>
      {!data.on_remote || unpushed ? (
        <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => run("push")}>
          <ArrowUpFromLine /> Push
        </Button>
      ) : null}
      {behind ? (
        <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => run("pull")}>
          <ArrowDownToLine /> Pull
        </Button>
      ) : null}
      <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => run("fetch")} aria-label="Fetch">
        <RefreshCw className={cn(busy === "fetch" && "animate-spin")} /> Fetch
      </Button>
    </div>
  );
}

/** The configuration repository as files, like a git host's code view: a branch,
 * its tree, a file to read or edit (each save a commit), and the history of the
 * file or of everything, with every commit's diff. */
export function RepositoryPanel() {
  const git = useGit();
  const [branch, setBranch] = useState<string | null>(null);
  const [view, setView] = useState<"files" | "history">("files");
  const [opened, setOpened] = useState<Opened | null>(null);
  const ref = branch ?? git.data?.current ?? "";
  if (git.isLoading) return <Loading />;
  if (git.error || !git.data) return <ErrorBox error={git.error} />;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <NativeSelect
          className="w-auto min-w-40"
          value={ref}
          onChange={(e) => {
            setBranch(e.target.value);
            setOpened(null);
          }}
          aria-label="Branch"
        >
          {git.data.branches.map((b) => (
            <option key={b.name} value={b.name}>
              {b.name}
              {b.current ? " (running)" : ""}
            </option>
          ))}
        </NativeSelect>
        <div className="flex rounded-md border p-0.5">
          {(["files", "history"] as const).map((v) => (
            <Button key={v} size="sm" variant={view === v ? "secondary" : "ghost"} className="h-7 capitalize" onClick={() => setView(v)}>
              {v}
            </Button>
          ))}
        </div>
        <p className="min-w-0 flex-1 text-xs text-muted-foreground">
          {ref === git.data.current
            ? "The running branch: a save applies at once."
            : "Not the running branch: a save applies when it is switched to or merged."}
        </p>
      </div>
      <RemoteBar branch={ref} />
      {view === "files" ? (
        <Files branch={ref} opened={opened} onOpen={setOpened} />
      ) : (
        <CommitList
          refName={ref}
          onOpenFile={(path, commit) => {
            setOpened({ path, ref: commit });
            setView("files");
          }}
        />
      )}
    </div>
  );
}

function Files({ branch, opened, onOpen }: { branch: string; opened: Opened | null; onOpen: (o: Opened | null) => void }) {
  const { data, error, isLoading } = useQuery({
    queryKey: ["repo-tree", branch],
    queryFn: () => api<{ files: TreeFile[] }>("GET", `/api/repository/tree?ref=${encodeURIComponent(branch)}`),
  });
  const [creating, setCreating] = useState<string | null>(null);
  return (
    <div className="grid gap-3 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <Card className="h-fit p-2">
        <div className="mb-2 flex gap-1">
          <Button size="sm" variant="outline" className="flex-1" onClick={() => setCreating("")}>
            <FilePlus /> New file
          </Button>
        </div>
        {creating !== null ? (
          <form
            className="mb-2 flex gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              const path = creating.trim().replace(/^\/+/, "");
              if (!path) return;
              setCreating(null);
              onOpen({ path, ref: "" });
            }}
          >
            <Input autoFocus className="h-8 font-mono text-xs" placeholder="code/mine/server.py" value={creating} onChange={(e) => setCreating(e.target.value)} />
            <Button size="icon" variant="ghost" type="button" className="size-8" onClick={() => setCreating(null)} aria-label="Cancel">
              <X />
            </Button>
          </form>
        ) : null}
        {isLoading ? <Loading /> : null}
        {error ? <ErrorBox error={error} /> : null}
        {data ? <Tree files={data.files} selected={opened?.path} onSelect={(path) => onOpen({ path, ref: branch })} /> : null}
      </Card>
      <div className="min-w-0">
        {opened ? (
          <FileView key={`${opened.ref}:${opened.path}`} branch={branch} opened={opened} onOpen={onOpen} />
        ) : (
          <Card className="p-8 text-center text-sm text-muted-foreground">Choose a file.</Card>
        )}
      </div>
    </div>
  );
}

interface Node {
  name: string;
  path: string;
  children: Node[];
  file: boolean;
}

function buildTree(files: TreeFile[]): Node[] {
  const root: Node = { name: "", path: "", children: [], file: false };
  for (const f of files) {
    let node = root;
    const parts = f.path.split("/");
    parts.forEach((part, i) => {
      const path = parts.slice(0, i + 1).join("/");
      let child = node.children.find((c) => c.name === part);
      if (!child) {
        child = { name: part, path, children: [], file: i === parts.length - 1 };
        node.children.push(child);
      }
      node = child;
    });
  }
  const sort = (nodes: Node[]): Node[] =>
    nodes.sort((a, b) => Number(a.file) - Number(b.file) || a.name.localeCompare(b.name)).map((n) => ({ ...n, children: sort(n.children) }));
  return sort(root.children);
}

function Tree({ files, selected, onSelect }: { files: TreeFile[]; selected?: string; onSelect: (path: string) => void }) {
  const [filter, setFilter] = useState("");
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const needle = filter.trim().toLowerCase();
  const nodes = useMemo(() => buildTree(needle ? files.filter((f) => f.path.toLowerCase().includes(needle)) : files), [files, needle]);
  const toggle = (path: string) => setClosed((c) => (c.has(path) ? new Set([...c].filter((p) => p !== path)) : new Set([...c, path])));
  const render = (list: Node[], depth: number) =>
    list.map((n) => (
      <div key={n.path}>
        <button
          type="button"
          className={cn(
            "flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-left text-sm hover:bg-accent",
            selected === n.path && "bg-accent font-medium",
          )}
          style={{ paddingLeft: 6 + depth * 14 }}
          onClick={() => (n.file ? onSelect(n.path) : toggle(n.path))}
        >
          {n.file ? (
            <File className="size-3.5 shrink-0 text-muted-foreground" />
          ) : (
            <>
              {closed.has(n.path) && !needle ? <ChevronRight className="size-3.5 shrink-0" /> : <ChevronDown className="size-3.5 shrink-0" />}
              <Folder className="size-3.5 shrink-0 text-muted-foreground" />
            </>
          )}
          <span className="truncate">{n.name}</span>
        </button>
        {!n.file && (!closed.has(n.path) || needle) ? render(n.children, depth + 1) : null}
      </div>
    ));
  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input className="h-8 pl-8 text-xs" placeholder="Filter files" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </div>
      <div className="max-h-[60svh] overflow-y-auto">{render(nodes, 0)}</div>
    </div>
  );
}

/** One file: read it, edit and save it as a commit, see its history, delete it.
 * Opened at a commit it is read only, with a way to bring that version back. */
function FileView({ branch, opened, onOpen }: { branch: string; opened: Opened; onOpen: (o: Opened | null) => void }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const isNew = opened.ref === "";
  const atCommit = !isNew && opened.ref !== branch;
  const { data, error, isLoading } = useQuery({
    queryKey: ["repo-file", opened.ref, opened.path],
    queryFn: () => api<RepoFile>("GET", `/api/repository/file?ref=${encodeURIComponent(opened.ref)}&path=${encodeURIComponent(opened.path)}`),
    enabled: !isNew,
  });
  const [editing, setEditing] = useState(isNew || opened.draft !== undefined);
  const [draft, setDraft] = useState<string | null>(opened.draft ?? (isNew ? "" : null));
  const [message, setMessage] = useState(opened.draft !== undefined ? `${opened.path}: restore an earlier version` : "");
  const [showHistory, setShowHistory] = useState(false);
  const [busy, setBusy] = useState(false);
  const text = draft ?? data?.text ?? "";
  const dirty = draft !== null && (isNew || draft !== data?.text);

  const refresh = () => {
    for (const key of ["repo-tree", "repo-file", "repo-history", "repo-remote", "git", "settings", "agents", "connectors", "schedules", "audit"])
      void queryClient.invalidateQueries({ queryKey: [key] });
  };
  const write = async (body: { text: string | null; base: string | null }, done: string) => {
    setBusy(true);
    try {
      await api("PUT", "/api/repository/file", { branch, path: opened.path, message, ...body });
      toast.success(done);
      setEditing(false);
      setDraft(null);
      setMessage("");
      refresh();
      if (body.text === null) onOpen(null);
      else if (isNew) onOpen({ path: opened.path, ref: branch });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = () => write({ text, base: isNew ? null : (data?.blob ?? null) }, `Committed on ${branch}.`);
  const remove = async () => {
    if (!(await confirm({ title: `Delete ${opened.path}?`, body: `A commit on ${branch}; the history keeps it.`, action: "Delete", destructive: true })))
      return;
    await write({ text: null, base: data?.blob ?? null }, `Deleted on ${branch}.`);
  };
  /** An old version, put into the editor on the branch, to be saved like any edit. */
  const restore = () => {
    onOpen({ path: opened.path, ref: branch, draft: data?.text ?? "" });
    toast.info("The earlier version is in the editor; commit it to bring it back.");
  };

  return (
    <Card className="flex min-h-[70svh] flex-col gap-2 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <code className="min-w-0 flex-1 truncate text-sm font-medium">{opened.path}</code>
        {atCommit ? <Badge variant="outline">at {opened.ref.slice(0, 7)}</Badge> : null}
        {isNew ? <Badge variant="secondary">new</Badge> : null}
        {!isNew ? (
          <Button size="sm" variant={showHistory ? "secondary" : "ghost"} onClick={() => setShowHistory(!showHistory)}>
            <History /> History
          </Button>
        ) : null}
        {atCommit ? (
          <>
            <Button size="sm" variant="outline" onClick={restore} disabled={!data?.text}>
              <RotateCcw /> Restore this version
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onOpen({ path: opened.path, ref: branch })}>
              Current
            </Button>
          </>
        ) : editing ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setEditing(false);
              setDraft(null);
              if (isNew) onOpen(null);
            }}
          >
            Cancel
          </Button>
        ) : (
          <>
            <Button size="sm" variant="outline" onClick={() => setEditing(true)} disabled={!data || data.binary}>
              <Pencil /> Edit
            </Button>
            <Button size="sm" variant="ghost" className="text-destructive" onClick={remove} disabled={!data || busy}>
              <Trash2 />
            </Button>
          </>
        )}
      </div>
      {error ? <ErrorBox error={error} /> : null}
      {isLoading ? <Loading /> : null}
      {showHistory ? <FileHistory refName={branch} path={opened.path} onOpen={(commit) => onOpen({ path: opened.path, ref: commit })} /> : null}
      {data?.binary ? (
        <p className="text-sm text-muted-foreground">A binary file; it is not shown here.</p>
      ) : data || isNew ? (
        <div className="min-h-0 flex-1">
          <Suspense fallback={<Loading />}>
            <CodeEditor path={opened.path} value={text} readOnly={!editing} onChange={setDraft} />
          </Suspense>
        </div>
      ) : null}
      {editing ? (
        <form
          className="flex flex-wrap items-center gap-2 border-t pt-2"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <Input className="min-w-48 flex-1" placeholder={`${opened.path}: ${isNew ? "add" : "update"}`} value={message} onChange={(e) => setMessage(e.target.value)} />
          <Button type="submit" disabled={busy || !dirty}>
            <Save /> Commit to {branch}
          </Button>
        </form>
      ) : null}
    </Card>
  );
}

function FileHistory({ refName, path, onOpen }: { refName: string; path: string; onOpen: (commit: string) => void }) {
  const unpushed = new Set(useRemoteStatus(refName).data?.unpushed ?? []);
  const { data, isLoading } = useQuery({
    queryKey: ["repo-history", refName, path],
    queryFn: () => api<{ commits: Commit[] }>("GET", `/api/repository/history?ref=${encodeURIComponent(refName)}&path=${encodeURIComponent(path)}&limit=30`),
  });
  const [shown, setShown] = useState<string | null>(null);
  if (isLoading) return <Loading />;
  return (
    <div className="max-h-72 divide-y overflow-y-auto rounded-md border">
      {data?.commits.map((c) => (
        <div key={c.commit}>
          <div className={cn("flex items-center gap-2 px-2 py-1.5 text-xs", shown === c.commit && "bg-accent")}>
            <button type="button" className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={() => setShown(shown === c.commit ? null : c.commit)}>
              <code className="text-muted-foreground">{c.commit.slice(0, 7)}</code>
              <LocalBadge commit={c.commit} unpushed={unpushed} />
              <span className="min-w-0 flex-1 truncate">{c.subject}</span>
              <span className="shrink-0 text-muted-foreground">
                {c.author} · {when(c.date)}
              </span>
            </button>
            <Button size="sm" variant="ghost" className="h-6 px-2 text-xs" onClick={() => onOpen(c.commit)}>
              Open
            </Button>
          </div>
          {shown === c.commit ? <CommitDiff commit={c.commit} /> : null}
        </div>
      ))}
    </div>
  );
}

function CommitDiff({ commit }: { commit: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["repo-diff", commit],
    queryFn: () => api<{ diff: string }>("GET", `/api/repository/commits/${commit}`),
  });
  return <div className="bg-muted/30 px-3 py-2">{isLoading ? <Loading /> : <Diff text={data?.diff ?? ""} />}</div>;
}

/** Every commit of the branch, newest first, a page at a time. */
function CommitList({ refName, onOpenFile }: { refName: string; onOpenFile: (path: string, commit: string) => void }) {
  const unpushed = new Set(useRemoteStatus(refName).data?.unpushed ?? []);
  const [pages, setPages] = useState(1);
  const limit = 50 * pages;
  const { data, isLoading, error } = useQuery({
    queryKey: ["repo-history", refName, "", limit],
    queryFn: () => api<{ commits: Commit[]; more: boolean }>("GET", `/api/repository/history?ref=${encodeURIComponent(refName)}&limit=${Math.min(limit, 200)}`),
  });
  const [shown, setShown] = useState<string | null>(null);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  return (
    <div className="space-y-3">
      <div className="divide-y rounded-xl border">
        {data?.commits.map((c) => (
          <div key={c.commit}>
            <button
              type="button"
              className={cn("flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-left hover:bg-accent/50 md:flex-nowrap", shown === c.commit && "bg-accent")}
              onClick={() => setShown(shown === c.commit ? null : c.commit)}
            >
              <code className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
                <GitCommitHorizontal className="size-3" />
                {c.commit.slice(0, 7)}
              </code>
              <LocalBadge commit={c.commit} unpushed={unpushed} />
              <span className="min-w-0 flex-1 truncate text-sm">{c.subject}</span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {c.author} · {when(c.date)} · {c.files.length} file{c.files.length === 1 ? "" : "s"}
              </span>
            </button>
            {shown === c.commit ? (
              <div className="space-y-2 bg-muted/30 px-3 py-2">
                <div className="flex flex-wrap gap-1.5">
                  {c.files.map(([status, path]) => (
                    <Button
                      key={path}
                      size="sm"
                      variant="outline"
                      className="h-6 px-2 font-mono text-xs"
                      disabled={status === "D"}
                      onClick={() => onOpenFile(path, c.commit)}
                      title={STATUS[status] ?? status}
                    >
                      {status} {path}
                    </Button>
                  ))}
                </div>
                <CommitDiff commit={c.commit} />
              </div>
            ) : null}
          </div>
        ))}
      </div>
      {data?.more && limit < 200 ? (
        <div className="text-center">
          <Button variant="outline" onClick={() => setPages(pages + 1)}>
            Older commits
          </Button>
        </div>
      ) : null}
    </div>
  );
}
