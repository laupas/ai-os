import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Eye, Merge, Plus, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { ListView } from "@/components/list-view";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { api, type Memory, type MemoryKind, type MemoryOwner } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { changedAt, groupMemories, KINDS, lookAlikes, type MemoryGroup } from "@/lib/memory-groups";
import { href } from "@/lib/router";
import { can, useMe } from "@/lib/use-me";
import { cn, when } from "@/lib/utils";

const SHARED = "Shared";
const DUPLICATES = "possible duplicates";

function ownerName(userId: string | null, users: MemoryOwner[]): string {
  if (userId === null) return SHARED;
  return users.find((u) => u.id === userId)?.name ?? userId;
}

const bodyOf = (m: Memory) => ({ kind: m.kind, subject: m.subject, text: m.text, user_id: m.user_id });

export function MemoriesPage() {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { data: me } = useMe();
  const { data, isLoading, error } = useQuery({
    queryKey: ["memories"],
    queryFn: () => api<{ memories: Memory[]; users: MemoryOwner[] }>("GET", "/api/memories"),
  });
  const users = data?.users ?? [];
  const memories = useMemo(() => data?.memories ?? [], [data]);
  const groups = useMemo(() => groupMemories(memories), [memories]);
  const alike = useMemo(() => lookAlikes(memories), [memories]);
  const byId = useMemo(() => new Map(memories.map((m) => [m.id, m])), [memories]);
  const [adding, setAdding] = useState(false);
  const [preview, setPreview] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [merging, setMerging] = useState<Memory[] | null>(null);
  const chosen = [...selected].map((id) => byId.get(id)).filter((m): m is Memory => Boolean(m));
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["memories"] });
  const toggle = (id: string, on: boolean) => {
    const next = new Set(selected);
    if (on) next.add(id);
    else next.delete(id);
    setSelected(next);
  };
  // Each change is its own request: a failure names itself, and the others stand.
  const each = async (label: string, run: (m: Memory) => Promise<unknown>) => {
    const results = await Promise.allSettled(chosen.map(run));
    const failed = results.filter((r) => r.status === "rejected") as PromiseRejectedResult[];
    if (failed.length) toast.error(`${failed.length} of ${chosen.length} not ${label}: ${(failed[0].reason as Error).message}`);
    else toast.success(`${chosen.length} ${label}.`);
    setSelected(new Set());
    void refresh();
  };
  const update = (patch: Partial<ReturnType<typeof bodyOf>>) =>
    each("changed", (m) => api("PUT", `/api/memories/${encodeURIComponent(m.id)}`, { ...bodyOf(m), ...patch }));
  const removeChosen = async () => {
    if (!(await confirm({ title: `Delete ${chosen.length} memories?`, action: "Delete", destructive: true }))) return;
    await each("deleted", (m) => api("DELETE", `/api/memories/${encodeURIComponent(m.id)}`));
  };
  const isDuplicate = (g: MemoryGroup) => g.memories.length > 1 || g.memories.some((m) => alike.has(m.id));
  return (
    <Page className="max-w-3xl">
      <PageHeader
        title="Memories"
        description="What ai-os remembers. Preferences go into every turn of their owner (shared ones into everyone's); the names of saved people and projects do too, and what is saved about one comes in full when a message names it. Notes are looked up when needed."
        actions={
          <>
            <Button variant="outline" onClick={() => setPreview(true)}>
              <Eye /> Prompt
            </Button>
            <Button onClick={() => setAdding(true)}>
              <Plus /> Add
            </Button>
          </>
        }
      />
      {adding ? (
        <Card className="p-4">
          <MemoryForm users={users} onDone={() => setAdding(false)} />
        </Card>
      ) : null}
      {chosen.length ? (
        <Card className="sticky top-2 z-10 flex flex-wrap items-center gap-2 p-2 shadow-md">
          <span className="px-2 text-sm tabular-nums">{chosen.length} selected</span>
          <Button size="sm" variant="outline" disabled={chosen.length < 2} onClick={() => setMerging(chosen)}>
            <Merge /> Merge
          </Button>
          <NativeSelect className="h-8 w-auto" value="" aria-label="Change kind" onChange={(e) => e.target.value && void update({ kind: e.target.value as MemoryKind })}>
            <option value="">Kind…</option>
            {KINDS.map((k) => (
              <option key={k}>{k}</option>
            ))}
          </NativeSelect>
          {users.length > 1 || can(me, "manage_shared_memories") ? (
            <NativeSelect className="h-8 w-auto" value="-" aria-label="Change owner" onChange={(e) => e.target.value !== "-" && void update({ user_id: e.target.value || null })}>
              <option value="-">Owner…</option>
              <option value="">{SHARED}</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </NativeSelect>
          ) : null}
          <Button size="sm" variant="ghost" className="text-destructive" onClick={removeChosen}>
            <Trash2 /> Delete
          </Button>
          <span className="flex-1" />
          <Button size="icon-sm" variant="ghost" aria-label="Clear selection" onClick={() => setSelected(new Set())}>
            <X />
          </Button>
        </Card>
      ) : null}
      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {data ? (
        <ListView
          items={groups}
          keyOf={(g) => g.key}
          text={(g) => g.memories.map((m) => `${m.subject ?? ""} ${m.text}`).join(" ")}
          facets={[
            { label: "kinds", value: (g) => g.kind, options: KINDS },
            { label: "owners", value: (g) => g.memories.map((m) => ownerName(m.user_id, users)) },
            { label: "hints", value: (g) => (isDuplicate(g) ? DUPLICATES : null) },
          ]}
          empty="Nothing remembered yet."
        >
          {(g) => (
            <GroupCard
              group={g}
              users={users}
              selected={selected}
              onSelect={toggle}
              alike={alike}
              byId={byId}
              onMerge={(ms) => setMerging(ms)}
            />
          )}
        </ListView>
      ) : null}
      {merging ? (
        <MergeDialog
          memories={merging}
          users={users}
          onClose={(done) => {
            setMerging(null);
            if (done) setSelected(new Set());
          }}
        />
      ) : null}
      {preview ? <PromptDialog users={users} onClose={() => setPreview(false)} /> : null}
    </Page>
  );
}

function GroupCard({
  group,
  users,
  selected,
  onSelect,
  alike,
  byId,
  onMerge,
}: {
  group: MemoryGroup;
  users: MemoryOwner[];
  selected: Set<string>;
  onSelect: (id: string, on: boolean) => void;
  alike: Map<string, string[]>;
  byId: Map<string, Memory>;
  onMerge: (memories: Memory[]) => void;
}) {
  const writable = group.memories.filter((m) => m.editable);
  return (
    <Card className="gap-0 p-0">
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2">
        <span className="font-medium">{group.subject || <span className="text-muted-foreground italic">no subject</span>}</span>
        <Badge variant="secondary">{group.kind}</Badge>
        {group.kind === "preference" ? <Badge variant="success">in prompt</Badge> : null}
        {group.kind === "person" || group.kind === "project" ? <Badge variant="outline">named in prompt</Badge> : null}
        <span className="flex-1" />
        {group.memories.length > 1 ? (
          <>
            <Badge variant="warning">{group.memories.length} entries</Badge>
            {writable.length > 1 ? (
              <Button size="sm" variant="ghost" onClick={() => onMerge(writable)}>
                <Merge /> Merge
              </Button>
            ) : null}
          </>
        ) : null}
      </div>
      <div className="divide-y">
        {group.memories.map((m) => (
          <MemoryRow key={m.id} memory={m} users={users} checked={selected.has(m.id)} onCheck={(on) => onSelect(m.id, on)} alike={(alike.get(m.id) ?? []).map((id) => byId.get(id)).filter((x): x is Memory => Boolean(x))} onMerge={onMerge} />
        ))}
      </div>
    </Card>
  );
}

function MemoryRow({
  memory,
  users,
  checked,
  onCheck,
  alike,
  onMerge,
}: {
  memory: Memory;
  users: MemoryOwner[];
  checked: boolean;
  onCheck: (on: boolean) => void;
  alike: Memory[];
  onMerge: (memories: Memory[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const source = memory.source;
  const writtenBy = source?.user_id && source.user_id !== memory.user_id ? ` by ${ownerName(source.user_id, users)}` : "";
  return (
    <div className={cn("px-4 py-2", checked && "bg-accent/40")}>
      <div className="flex items-start gap-3">
        <Checkbox className="mt-1" checked={checked} disabled={!memory.editable} onCheckedChange={(v) => onCheck(v === true)} aria-label="Select" />
        <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setOpen(!open)} aria-expanded={open}>
          <div className={cn("text-sm whitespace-pre-wrap", !open && "line-clamp-2")}>{memory.text}</div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {open ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
            {memory.user_id === null || users.length > 1 ? <span>{ownerName(memory.user_id, users)}</span> : null}
            <span title={`made ${new Date(memory.created_at).toLocaleString()}`}>
              {memory.updated_at ? "changed" : "made"} {when(changedAt(memory))}
            </span>
            {source ? (
              source.conversation_id ? (
                <a className="underline-offset-2 hover:underline" href={href("chat", source.conversation_id)} onClick={(e) => e.stopPropagation()}>
                  via {source.channel}
                  {writtenBy}
                </a>
              ) : (
                <span>
                  via {source.channel}
                  {writtenBy}
                </span>
              )
            ) : null}
          </div>
        </button>
      </div>
      {alike.length ? (
        <div className="mt-1 ml-7 flex flex-wrap items-center gap-2 text-xs">
          <Badge variant="warning">looks like</Badge>
          {alike.map((a) => (
            <span key={a.id} className="text-muted-foreground">
              {a.subject ?? a.text.slice(0, 40)} ({a.kind})
            </span>
          ))}
          {memory.editable && alike.every((a) => a.editable) ? (
            <Button size="sm" variant="ghost" className="h-6 px-2" onClick={() => onMerge([memory, ...alike])}>
              <Merge /> Merge
            </Button>
          ) : null}
        </div>
      ) : null}
      {open ? (
        <div className="mt-3 ml-7">
          <MemoryForm memory={memory} users={users} onDone={() => setOpen(false)} />
        </div>
      ) : null}
    </div>
  );
}

function MemoryForm({ memory, users, onDone }: { memory?: Memory; users: MemoryOwner[]; onDone?: () => void }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { data: me } = useMe();
  // A shared memory goes into every user's turns: writing one takes its own right.
  const mayShare = can(me, "manage_shared_memories");
  const editable = memory?.editable ?? true;
  const [draft, setDraft] = useState({
    kind: memory?.kind ?? "note",
    subject: memory?.subject ?? "",
    text: memory?.text ?? "",
    owner: memory ? (memory.user_id ?? "") : mayShare ? "" : (users[0]?.id ?? ""),
  });
  const dirty =
    editable &&
    (!memory ||
      draft.kind !== memory.kind ||
      draft.subject !== (memory.subject ?? "") ||
      draft.text !== memory.text ||
      draft.owner !== (memory.user_id ?? ""));
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["memories"] });
  const save = useMutation({
    mutationFn: () => {
      const body = { kind: draft.kind, subject: draft.subject.trim() || null, text: draft.text.trim(), user_id: draft.owner || null };
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
    <div className="space-y-3">
      <MemoryFields draft={draft} setDraft={setDraft} users={users} mayShare={mayShare} editable={editable} />
      <div className="flex gap-2">
        {dirty ? (
          <Button size="sm" onClick={() => save.mutate()} disabled={!draft.text.trim() || save.isPending}>
            {memory ? "Save" : "Add"}
          </Button>
        ) : null}
        {onDone ? (
          <Button size="sm" variant="outline" onClick={onDone}>
            {memory && !dirty ? "Close" : "Cancel"}
          </Button>
        ) : null}
        <span className="flex-1" />
        {memory && editable ? (
          <Button size="sm" variant="ghost" className="text-destructive" onClick={remove}>
            <Trash2 /> Delete
          </Button>
        ) : null}
      </div>
    </div>
  );
}

interface Draft {
  kind: MemoryKind;
  subject: string;
  text: string;
  owner: string;
}

function MemoryFields({
  draft,
  setDraft,
  users,
  mayShare,
  editable = true,
  rows = 3,
}: {
  draft: Draft;
  setDraft: (d: Draft) => void;
  users: MemoryOwner[];
  mayShare: boolean;
  editable?: boolean;
  rows?: number;
}) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <NativeSelect className="h-8 w-32" value={draft.kind} disabled={!editable} onChange={(e) => setDraft({ ...draft, kind: e.target.value as MemoryKind })}>
          {KINDS.map((k) => (
            <option key={k}>{k}</option>
          ))}
        </NativeSelect>
        <NativeSelect className="h-8 w-40" value={draft.owner} disabled={!editable} title="Whose memory this is" onChange={(e) => setDraft({ ...draft, owner: e.target.value })}>
          {mayShare || draft.owner === "" ? <option value="">{SHARED}</option> : null}
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
          {draft.owner && !users.some((u) => u.id === draft.owner) ? <option value={draft.owner}>{draft.owner}</option> : null}
        </NativeSelect>
        <Input className="h-8 min-w-0 flex-1" placeholder="Subject" value={draft.subject} readOnly={!editable} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} />
      </div>
      <Textarea rows={rows} value={draft.text} readOnly={!editable} placeholder="Something to remember" onChange={(e) => setDraft({ ...draft, text: e.target.value })} />
    </>
  );
}

/** Several memories into one: the oldest keeps its id and creation date. */
function MergeDialog({ memories, users, onClose }: { memories: Memory[]; users: MemoryOwner[]; onClose: (done: boolean) => void }) {
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const ordered = [...memories].sort((a, b) => a.created_at.localeCompare(b.created_at));
  const first = ordered[0];
  const [draft, setDraft] = useState<Draft>({
    kind: first.kind,
    subject: ordered.find((m) => m.subject)?.subject ?? "",
    text: [...new Set(ordered.map((m) => m.text.trim()))].join("\n"),
    owner: first.user_id ?? "",
  });
  const merge = useMutation({
    mutationFn: () =>
      api("POST", "/api/memories/merge", {
        ids: ordered.map((m) => m.id),
        kind: draft.kind,
        subject: draft.subject.trim() || null,
        text: draft.text.trim(),
        user_id: draft.owner || null,
      }),
    onSuccess: () => {
      toast.success(`Merged ${ordered.length} into one.`);
      void queryClient.invalidateQueries({ queryKey: ["memories"] });
      onClose(true);
    },
    onError: (e) => toast.error(e.message),
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose(false)}>
      <DialogContent className="max-w-xl">
        <DialogTitle>Merge {ordered.length} memories</DialogTitle>
        <DialogDescription>Edit the text into one entry. The others are deleted.</DialogDescription>
        <div className="space-y-3">
          <MemoryFields draft={draft} setDraft={setDraft} users={users} mayShare={can(me, "manage_shared_memories")} rows={8} />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onClose(false)}>
            Cancel
          </Button>
          <Button onClick={() => merge.mutate()} disabled={!draft.text.trim() || merge.isPending}>
            <Merge /> Merge
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function PromptDialog({ users, onClose }: { users: MemoryOwner[]; onClose: () => void }) {
  // Empty: the caller's own.
  const [userId, setUserId] = useState("");
  const { data, error, isLoading } = useQuery({
    queryKey: ["memories", "prompt", userId],
    queryFn: () => api<{ text: string }>("GET", userId ? `/api/memories/prompt?user_id=${encodeURIComponent(userId)}` : "/api/memories/prompt"),
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogTitle>What a turn is told</DialogTitle>
        <DialogDescription>The memory part of the system prompt. A message that names a saved person or project also gets what is saved about them.</DialogDescription>
        {users.length > 1 ? (
          <NativeSelect value={userId} onChange={(e) => setUserId(e.target.value)} aria-label="User">
            <option value="">You</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </NativeSelect>
        ) : null}
        {isLoading ? <Loading /> : null}
        {error ? <ErrorBox error={error} /> : null}
        {data ? <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">{data.text || "Nothing from memories."}</pre> : null}
      </DialogContent>
    </Dialog>
  );
}
