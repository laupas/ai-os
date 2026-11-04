import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Empty, ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { api, type Memory, type MemoryKind } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { when } from "@/lib/utils";

const KINDS: MemoryKind[] = ["preference", "person", "project", "note"];

export function MemoriesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["memories"],
    queryFn: () => api<{ memories: Memory[] }>("GET", "/api/memories"),
  });
  const [filter, setFilter] = useState("");
  const [kind, setKind] = useState<MemoryKind | "all">("all");
  const [adding, setAdding] = useState(false);
  const q = filter.toLowerCase();
  const shown = (data?.memories ?? []).filter(
    (m) => (kind === "all" || m.kind === kind) && (!q || `${m.subject ?? ""} ${m.text}`.toLowerCase().includes(q)),
  );
  return (
    <Page className="max-w-3xl">
      <PageHeader
        title="Memories"
        description="What ai-os remembers. Preferences go into every agent's prompt."
        actions={
          <Button onClick={() => setAdding(true)}>
            <Plus /> Add
          </Button>
        }
      />
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Filter" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <NativeSelect className="w-36" value={kind} onChange={(e) => setKind(e.target.value as MemoryKind | "all")}>
          <option value="all">All kinds</option>
          {KINDS.map((k) => (
            <option key={k}>{k}</option>
          ))}
        </NativeSelect>
      </div>
      {adding ? <MemoryCard onDone={() => setAdding(false)} /> : null}
      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {data && shown.length === 0 ? <Empty>Nothing matches.</Empty> : null}
      {shown.map((m) => (
        <MemoryCard key={m.id} memory={m} />
      ))}
    </Page>
  );
}

function MemoryCard({ memory, onDone }: { memory?: Memory; onDone?: () => void }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [draft, setDraft] = useState({ kind: memory?.kind ?? "note", subject: memory?.subject ?? "", text: memory?.text ?? "" });
  const dirty = !memory || draft.kind !== memory.kind || draft.subject !== (memory.subject ?? "") || draft.text !== memory.text;
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["memories"] });
  const save = useMutation({
    mutationFn: () => {
      const body = { kind: draft.kind, subject: draft.subject.trim() || null, text: draft.text.trim() };
      return memory ? api("PUT", `/api/memories/${encodeURIComponent(memory.id)}`, body) : api("POST", "/api/memories", body);
    },
    onSuccess: () => {
      toast.success("Saved.");
      void refresh();
      onDone?.();
    },
    onError: (e) => toast.error(e.message),
  });
  const remove = async () => {
    if (!memory || !(await confirm({ title: "Delete this memory?", action: "Delete", destructive: true }))) return;
    try {
      await api("DELETE", `/api/memories/${encodeURIComponent(memory.id)}`);
      void refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <NativeSelect className="h-8 w-32" value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as MemoryKind })}>
          {KINDS.map((k) => (
            <option key={k}>{k}</option>
          ))}
        </NativeSelect>
        <Input className="h-8 min-w-0 flex-1" placeholder="Subject" value={draft.subject} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} />
        {memory ? <Badge variant="outline">{when(memory.created_at)}</Badge> : null}
      </div>
      <Textarea rows={2} value={draft.text} placeholder="Something to remember" onChange={(e) => setDraft({ ...draft, text: e.target.value })} />
      <div className="flex gap-2">
        {dirty ? (
          <Button size="sm" onClick={() => save.mutate()} disabled={!draft.text.trim() || save.isPending}>
            {memory ? "Save" : "Add"}
          </Button>
        ) : null}
        {onDone ? (
          <Button size="sm" variant="outline" onClick={onDone}>
            Cancel
          </Button>
        ) : null}
        <span className="flex-1" />
        {memory ? (
          <Button size="sm" variant="ghost" className="text-destructive" onClick={remove}>
            <Trash2 /> Delete
          </Button>
        ) : null}
      </div>
    </Card>
  );
}
