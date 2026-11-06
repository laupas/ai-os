import { useQuery, useQueryClient } from "@tanstack/react-query";
import { History, RotateCcw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading } from "@/components/page";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { cn, when } from "@/lib/utils";

interface Commit {
  commit: string;
  author: string;
  email: string;
  date: string;
  subject: string;
}

type Kind = "agents" | "skills" | "connectors" | "schedules";

/** The git history of one configuration file: who changed it when, what changed,
 * and bringing an earlier version back (as a new commit). */
export function HistoryButton({ kind, id, label, onRestored }: { kind: Kind; id: string; label?: string; onRestored?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button type="button" variant="ghost" onClick={() => setOpen(true)}>
        <History /> History
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85svh] max-w-2xl overflow-hidden p-0">
          {open ? (
            <HistoryList
              kind={kind}
              id={id}
              label={label ?? id}
              onRestored={() => {
                setOpen(false);
                onRestored?.();
              }}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

function HistoryList({ kind, id, label, onRestored }: { kind: Kind; id: string; label: string; onRestored: () => void }) {
  const base = `/api/history/${kind}/${encodeURIComponent(id)}`;
  const { data, isLoading, error } = useQuery({
    queryKey: ["history", kind, id],
    queryFn: () => api<{ path: string; commits: Commit[] }>("GET", base),
  });
  const [shown, setShown] = useState<string | null>(null);
  return (
    <div className="flex max-h-[85svh] flex-col">
      <div className="border-b p-4">
        <DialogTitle>History of {label}</DialogTitle>
        <DialogDescription>
          {data ? <code className="text-xs">{data.path}</code> : null} Every save is a commit; restoring makes a new one.
        </DialogDescription>
      </div>
      <div className="flex-1 overflow-y-auto">
        {isLoading ? <Loading /> : null}
        {error ? <ErrorBox error={error} /> : null}
        {data?.commits.length === 0 ? <p className="p-4 text-sm text-muted-foreground">No history yet.</p> : null}
        {data?.commits.map((c, i) => (
          <div key={c.commit} className="border-b">
            <button
              type="button"
              className={cn("flex w-full items-baseline gap-3 px-4 py-2.5 text-left hover:bg-accent/50", shown === c.commit && "bg-accent")}
              onClick={() => setShown(shown === c.commit ? null : c.commit)}
            >
              <code className="shrink-0 text-xs text-muted-foreground">{c.commit.slice(0, 7)}</code>
              <span className="min-w-0 flex-1 truncate text-sm">{c.subject}</span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {c.author} · {when(c.date)}
              </span>
            </button>
            {shown === c.commit ? (
              <CommitDetail
                base={base}
                commit={c}
                current={i === 0}
                kind={kind}
                onRestored={onRestored}
              />
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function CommitDetail({
  base,
  commit,
  current,
  kind,
  onRestored,
}: {
  base: string;
  commit: Commit;
  current: boolean;
  kind: Kind;
  onRestored: () => void;
}) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { data, isLoading } = useQuery({
    queryKey: ["history-diff", base, commit.commit],
    queryFn: () => api<{ diff: string }>("GET", `${base}/${commit.commit}`),
  });
  const deleted = commit.subject.endsWith(": delete");
  const restore = async () => {
    const ok = await confirm({
      title: "Restore this version?",
      body: `It becomes the current version, as of ${when(commit.date)}. Nothing is lost: the version it replaces stays in the history.`,
      action: "Restore",
    });
    if (!ok) return;
    try {
      await api("POST", `${base}/restore`, { commit: commit.commit });
      toast.success("Restored. Applies to the next turn.");
      for (const key of [kind === "skills" ? "agents" : kind, "agents", "history"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      onRestored();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <div className="space-y-2 bg-muted/30 px-4 py-3">
      {isLoading ? <Loading /> : <Diff text={data?.diff ?? ""} />}
      {!current && !deleted ? (
        <Button size="sm" variant="outline" onClick={restore}>
          <RotateCcw /> Restore this version
        </Button>
      ) : null}
    </div>
  );
}

export function Diff({ text }: { text: string }) {
  const lines = text.split("\n").filter((l) => !/^(diff --git|index |--- |\+\+\+ |new file mode|deleted file mode)/.test(l));
  if (!lines.some((l) => l.trim())) return <p className="text-xs text-muted-foreground">No change in this file.</p>;
  return (
    <pre className="max-h-80 overflow-auto rounded-md border bg-background p-2 font-mono text-xs leading-relaxed">
      {lines.map((line, i) => (
        <div
          key={i}
          className={cn(
            "whitespace-pre-wrap break-words",
            line.startsWith("+") && "bg-success/10 text-success",
            line.startsWith("-") && "bg-destructive/10 text-destructive",
            line.startsWith("@@") && "text-muted-foreground",
          )}
        >
          {line || " "}
        </div>
      ))}
    </pre>
  );
}
