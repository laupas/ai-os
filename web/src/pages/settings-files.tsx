import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpen, Plus, Save, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Hint, Input } from "@/components/ui/input";
import { api } from "@/lib/api";

interface PathStatus {
  problem: string | null;
  exists: boolean;
  real: string | null;
}

interface FilesState {
  read_roots: string[];
  write_roots: string[];
  paths: Record<string, PathStatus>;
  mounts: string[];
  protected: string[];
}

export function FilesPanel() {
  const { data, isLoading, error } = useQuery({ queryKey: ["settings-files"], queryFn: () => api<FilesState>("GET", "/api/settings/files") });
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} />;
  return <FilesForm key={JSON.stringify([data.read_roots, data.write_roots])} data={data} />;
}

function FilesForm({ data }: { data: FilesState }) {
  const queryClient = useQueryClient();
  const [read, setRead] = useState(data.read_roots);
  const [write, setWrite] = useState(data.write_roots);
  const [paths, setPaths] = useState(data.paths);
  const dirty = JSON.stringify([read, write]) !== JSON.stringify([data.read_roots, data.write_roots]);

  // What each folder is where ai-os runs, asked again when the lists change.
  useEffect(() => {
    const unknown = [...read, ...write].filter((p) => !(p in paths));
    if (!unknown.length) return;
    void api<{ paths: Record<string, PathStatus> }>("POST", "/api/settings/files/check", { read_roots: unknown })
      .then((r) => setPaths((all) => ({ ...all, ...r.paths })))
      .catch(() => undefined);
  }, [read, write, paths]);

  const save = async () => {
    try {
      await api("PUT", "/api/settings/files", { read_roots: read, write_roots: write });
      void queryClient.invalidateQueries({ queryKey: ["settings-files"] });
      void queryClient.invalidateQueries({ queryKey: ["restart-needed"] });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success("Saved and committed. Restart ai-os to apply it.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const used = new Set([...read, ...write]);
  const offered = data.mounts.filter((m) => !used.has(m));
  return (
    <Card className="max-w-3xl">
      <CardHeader className="flex-row items-start gap-3">
        <div className="flex-1">
          <CardTitle>Files</CardTitle>
          <CardDescription>
            The folders agents' file tools (Read, Grep, Glob, Edit, Write) may reach; nothing else is. A folder that would reach ai-os's own
            data, code or the system is refused. In Docker, a folder must be mounted into the container to be there. Applies at once.
          </CardDescription>
        </div>
        <Button onClick={save} disabled={!dirty}>
          <Save /> Save
        </Button>
      </CardHeader>
      <CardContent className="space-y-5">
        <RootList title="Read and write" hint="Agents may read and change files here." value={write} paths={paths} onChange={setWrite} />
        <RootList title="Read only" hint="Agents may read files here, not change them." value={read} paths={paths} onChange={setRead} />
        {offered.length ? (
          <div className="space-y-1.5">
            <div className="text-sm font-medium">Mounted into the container</div>
            <div className="flex flex-wrap gap-1.5">
              {offered.map((m) => (
                <span key={m} className="inline-flex items-center gap-1 rounded-md border py-0.5 pr-1 pl-2 font-mono text-xs">
                  <FolderOpen className="size-3.5 text-muted-foreground" /> {m}
                  <Button size="sm" variant="ghost" className="h-6 px-1.5 text-xs" onClick={() => setRead([...read, m])}>
                    read
                  </Button>
                  <Button size="sm" variant="ghost" className="h-6 px-1.5 text-xs" onClick={() => setWrite([...write, m])}>
                    write
                  </Button>
                </span>
              ))}
            </div>
          </div>
        ) : (
          <Hint>No other folder is mounted into the container; add one under volumes in docker-compose.yml to share it.</Hint>
        )}
        <Hint>Never reachable: {data.protected.join(", ")}.</Hint>
      </CardContent>
    </Card>
  );
}

function RootList({
  title,
  hint,
  value,
  paths,
  onChange,
}: {
  title: string;
  hint: string;
  value: string[];
  paths: Record<string, PathStatus>;
  onChange: (v: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const path = draft.trim().replace(/\/+$/, "") || draft.trim();
    if (path && !value.includes(path)) onChange([...value, path]);
    setDraft("");
  };
  return (
    <div className="space-y-2">
      <div className="text-sm font-medium">{title}</div>
      <Hint>{hint}</Hint>
      <div className="space-y-1.5">
        {value.length === 0 ? <div className="text-sm text-muted-foreground">none</div> : null}
        {value.map((p) => {
          const s = paths[p];
          return (
            <div key={p} className="flex flex-wrap items-center gap-2 rounded-md border px-2 py-1">
              <code className="text-xs">{p}</code>
              {s?.problem ? (
                <Badge variant="destructive">{s.problem.replace(`${p}: `, "")}</Badge>
              ) : s && !s.exists ? (
                <Badge variant="warning">not there</Badge>
              ) : null}
              {s?.real ? <span className="text-xs text-muted-foreground">→ {s.real}</span> : null}
              <button type="button" className="ml-auto rounded p-0.5 text-muted-foreground hover:text-foreground" onClick={() => onChange(value.filter((x) => x !== p))} aria-label={`Remove ${p}`}>
                <X className="size-3.5" />
              </button>
            </div>
          );
        })}
      </div>
      <form
        className="flex max-w-xl gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
      >
        <Input className="font-mono text-xs md:text-xs" placeholder="/vault" value={draft} onChange={(e) => setDraft(e.target.value)} />
        <Button type="submit" variant="outline" disabled={!draft.trim()}>
          <Plus /> Add
        </Button>
      </form>
    </div>
  );
}
