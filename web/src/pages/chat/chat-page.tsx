import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bot, ChevronDown, Eraser, MessageSquarePlus, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, type ChatAgent, type ConversationSummary } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { go, href } from "@/lib/router";
import { useMe } from "@/lib/use-me";
import { cn, when } from "@/lib/utils";
import { Composer } from "./composer";
import { ActivityCard, AskCard, MessageView, StreamingView } from "./message-views";
import { useLiveConversation } from "./use-live-conversation";

/** List and thread side by side on a wide screen; one at a time on a phone.
 * `#/chat/new` is the new-conversation view: on a phone it needs an address of its
 * own, since `#/chat` there is the list. */
export function ChatPage({ id }: { id?: string }) {
  return (
    <div className="flex h-full overflow-clip">
      <aside className={cn("w-full shrink-0 border-r md:w-80 lg:w-96", id ? "hidden md:flex" : "flex")}>
        <ConversationList current={id} />
      </aside>
      <section className={cn("min-w-0 flex-1 flex-col overflow-clip", id ? "flex" : "hidden md:flex")}>
        {id && id !== "new" ? <Thread key={id} id={id} /> : <NewConversation />}
      </section>
    </div>
  );
}

function ConversationList({ current }: { current?: string }) {
  const { data: me } = useMe();
  const { data, isLoading, error } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api<{ conversations: ConversationSummary[] }>("GET", "/api/conversations"),
    refetchInterval: 30_000,
  });
  const [prune, setPrune] = useState(false);
  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <h2 className="flex-1 font-semibold">Conversations</h2>
        <Button size="icon-sm" variant="ghost" onClick={() => setPrune(true)} aria-label="Clean up" title="Delete old conversations">
          <Eraser />
        </Button>
        {me?.chat ? (
          <Button size="sm" asChild>
            <a href={href("chat", "new")}>
              <MessageSquarePlus /> New
            </a>
          </Button>
        ) : null}
      </div>
      <div className="flex-1 overflow-y-auto pb-[env(safe-area-inset-bottom)]">
        {isLoading ? <Loading /> : null}
        {error ? <ErrorBox error={error} /> : null}
        {data?.conversations.length === 0 ? <p className="p-6 text-sm text-muted-foreground">No conversations yet.</p> : null}
        {data?.conversations.map((c) => (
          <a
            key={c.id}
            href={href("chat", c.id)}
            className={cn(
              "block border-b px-4 py-3 transition-colors hover:bg-accent/50",
              c.id === current && "bg-accent",
            )}
          >
            <div className="flex items-baseline gap-2">
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{c.title || c.preview || "(no messages)"}</span>
              <span className="shrink-0 text-xs text-muted-foreground">{when(c.last_at || c.updated_at)}</span>
            </div>
            <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
              {c.agent ? (
                <Badge variant="outline" className="gap-1 px-1.5 py-0 font-normal">
                  <Bot className="size-3" /> {c.agent}
                </Badge>
              ) : null}
              {c.channels.map((ch) => (
                <Badge key={ch} variant="secondary" className="px-1.5 py-0 font-normal">
                  {ch}
                </Badge>
              ))}
              <span className="truncate">{c.participants.join(", ")}</span>
            </div>
          </a>
        ))}
      </div>
      <PruneDialog open={prune} onOpenChange={setPrune} />
    </div>
  );
}

function PruneDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient();
  const [days, setDays] = useState("30");
  const mutation = useMutation({
    mutationFn: () => api<{ deleted: number }>("POST", "/api/conversations/prune", { days: Number(days) }),
    onSuccess: ({ deleted }) => {
      toast.success(`Deleted ${deleted} conversation${deleted === 1 ? "" : "s"}.`);
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
      onOpenChange(false);
    },
    onError: (error) => toast.error(error.message),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Clean up conversations</DialogTitle>
        <DialogDescription>Delete every conversation you can see with nothing new for a number of days.</DialogDescription>
        <div className="flex items-center gap-2 text-sm">
          Older than <Input type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} className="w-24" /> days
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={() => mutation.mutate()} disabled={!(Number(days) >= 1) || mutation.isPending}>
            Delete
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ThreadHeader({ title, sub, actions }: { title: string; sub?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="flex shrink-0 items-center gap-2 border-b bg-background/80 px-2 pt-[env(safe-area-inset-top)] backdrop-blur md:px-4 md:pt-0">
      <div className="flex h-[3.25rem] min-w-0 flex-1 items-center gap-1 md:h-14">
        <Button variant="ghost" size="icon" className="md:hidden" asChild>
          <a href={href("chat")} aria-label="Back">
            <ArrowLeft />
          </a>
        </Button>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">{title}</div>
          {sub ? <div className="truncate text-xs text-muted-foreground">{sub}</div> : null}
        </div>
        {actions}
      </div>
    </div>
  );
}

const ORCHESTRATOR = "orchestrator";

function NewConversation() {
  const { data: me } = useMe();
  const queryClient = useQueryClient();
  const { data: agentList } = useQuery({
    queryKey: ["chat-agents"],
    queryFn: () => api<{ agents: ChatAgent[] }>("GET", "/api/chat/agents"),
  });
  const [agent, setAgent] = useState(ORCHESTRATOR);
  const chosen = agentList?.agents.find((a) => a.name === agent);
  const direct = agent !== ORCHESTRATOR;
  const start = async (text: string) => {
    try {
      const { id } = await api<{ id: string }>("POST", "/api/conversations", { text, agent: direct ? agent : null });
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
      go("chat", id);
    } catch (error) {
      toast.error((error as Error).message);
    }
  };
  return (
    <>
      <ThreadHeader title="New conversation" />
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        <span className="flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
          <Sparkles className="size-6" />
        </span>
        <h2 className="text-lg font-semibold">How can ai-os help{me ? `, ${me.name}` : ""}?</h2>
        <p className="line-clamp-3 max-w-sm text-sm text-muted-foreground">
          {direct
            ? `${chosen?.description ?? ""} This conversation stays with ${agent}.`
            : "ai-os hands your request to the right agent. Pick one below to talk to it directly."}
        </p>
      </div>
      {me?.chat ? (
        <Composer
          onSend={start}
          autoFocus
          placeholder={direct ? `Message ${agent}…` : undefined}
          toolbar={
            agentList && agentList.agents.length > 1 ? (
              <label
                className={cn(
                  "relative inline-flex h-7 items-center gap-1 rounded-full border px-2.5 text-xs font-medium",
                  direct ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground",
                )}
              >
                <Bot className="size-3.5" />
                {direct ? agent : "Any agent"}
                <ChevronDown className="size-3" />
                {/* The native picker: a wheel on a phone, a list on a desktop. */}
                <select
                  aria-label="Talk to"
                  value={agent}
                  onChange={(e) => setAgent(e.target.value)}
                  className="absolute inset-0 cursor-pointer opacity-0"
                >
                  {agentList.agents.map((a) => (
                    <option key={a.name} value={a.name}>
                      {a.name === ORCHESTRATOR ? "Any agent (ai-os decides)" : a.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null
          }
        />
      ) : (
        <p className="p-4 text-center text-sm text-muted-foreground">
          Chatting here needs <code>web</code> in the <code>channels</code> of config.yaml.
        </p>
      )}
    </>
  );
}

function Thread({ id }: { id: string }) {
  const live = useLiveConversation(id);
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const scroller = useRef<HTMLDivElement>(null);
  const stuck = useRef(true); // following the bottom

  useEffect(() => {
    const el = scroller.current;
    if (el && stuck.current) el.scrollTop = el.scrollHeight;
  }, [live.messages, live.streamed, live.steps, live.approvals]);

  const stop = async () => {
    try {
      await api("POST", `/api/conversations/${encodeURIComponent(id)}/stop`);
    } catch (error) {
      toast.error((error as Error).message);
    }
  };
  const send = async (text: string) => {
    stuck.current = true;
    try {
      await api("POST", `/api/conversations/${encodeURIComponent(id)}/messages`, { text });
    } catch (error) {
      toast.error((error as Error).message);
    }
  };
  const remove = async () => {
    if (!(await confirm({ title: "Delete this conversation?", body: "Its history is deleted for good.", action: "Delete", destructive: true })))
      return;
    try {
      await api("DELETE", `/api/conversations/${encodeURIComponent(id)}`);
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
      go("chat");
    } catch (error) {
      toast.error((error as Error).message);
    }
  };

  const c = live.conversation;
  if (live.error) return <ErrorBox error={live.error} />;
  const first = live.messages.find((m) => m.role === "user");
  return (
    <>
      <ThreadHeader
        title={c?.title || first?.text.slice(0, 80) || "Conversation"}
        sub={c ? `${c.agent ? `with ${c.agent} · ` : ""}${c.channels.join(" · ")} · ${c.participants.join(", ")}` : undefined}
        actions={
          <Button variant="ghost" size="icon" onClick={remove} aria-label="Delete conversation">
            <Trash2 />
          </Button>
        }
      />
      <div
        ref={scroller}
        className="flex-1 overflow-y-auto"
        onScroll={(e) => {
          const el = e.currentTarget;
          stuck.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
      >
        <div className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-6 md:px-6">
          {!c ? <Loading /> : null}
          {live.messages.map((m, i) => (
            <div key={m.id} className="contents">
              <MessageView message={m} />
              {live.approvals
                .filter((a) => a.after === i + 1)
                .map((a) => (
                  <AskCard key={a.id} id={a.id} question={a.question} options={a.options} />
                ))}
            </div>
          ))}
          {live.approvals
            .filter((a) => a.after > live.messages.length || a.after === 0)
            .map((a) => (
              <AskCard key={a.id} id={a.id} question={a.question} options={a.options} />
            ))}
          {live.steps.length ? <ActivityCard steps={live.steps} running={live.running} onStop={stop} /> : null}
          {live.streamed.trim() ? <StreamingView text={live.streamed} /> : null}
          {live.running && !live.steps.length && !live.streamed.trim() ? (
            <div className="flex gap-1 py-2" aria-label="Working">
              {[0, 150, 300].map((delay) => (
                <span key={delay} className="size-2 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: `${delay}ms` }} />
              ))}
            </div>
          ) : null}
        </div>
      </div>
      {c?.writable ? <Composer onSend={send} onStop={stop} busy={live.running} /> : null}
      {c && !c.writable ? (
        <div className="border-t p-3 text-center text-xs text-muted-foreground">
          <Badge variant="outline">read-only</Badge> the web channel is not enabled in config.yaml
        </div>
      ) : null}
    </>
  );
}
