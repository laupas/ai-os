import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { api, type Conversation, type ConversationEvent, type Message } from "@/lib/api";

export interface LiveApproval {
  id: string;
  question: string;
  options: string[];
  after: number; // shown after this many messages
}

export interface LiveState {
  conversation: Conversation | null;
  messages: Message[];
  streamed: string;
  steps: string[];
  running: boolean;
  approvals: LiveApproval[];
  error: unknown;
}

const EMPTY: LiveState = {
  conversation: null,
  messages: [],
  streamed: "",
  steps: [],
  running: false,
  approvals: [],
  error: null,
};

const byTime = (a: Message, b: Message) => a.created_at.localeCompare(b.created_at);

/** Adds messages by id. A recorded reply ends the streamed preview, recorded steps
 * end the live activity card. */
function mergeInto(s: LiveState, incoming: Message[]): LiveState {
  const known = new Map(s.messages.map((m) => [m.id, m]));
  for (const m of incoming) known.set(m.id, { ...known.get(m.id), ...m, author: m.author ?? known.get(m.id)?.author });
  return {
    ...s,
    messages: [...known.values()].sort(byTime),
    streamed: incoming.some((m) => m.role === "assistant") ? "" : s.streamed,
    steps: incoming.some((m) => m.role === "activity") ? [] : s.steps,
  };
}

/** One conversation, kept current over its event stream.
 *
 * Messages and approvals carry ids, so one that arrives both in a reload and as an
 * event is shown once. The history is reloaded every time the stream (re)connects,
 * which covers whatever happened while it was not connected; the server replays the
 * steps and text of a turn that is still running. */
export function useLiveConversation(id: string): LiveState {
  const queryClient = useQueryClient();
  const [state, setState] = useState<LiveState>(EMPTY);

  const load = useCallback(async () => {
    try {
      const conversation = await api<Conversation>("GET", `/api/conversations/${encodeURIComponent(id)}`);
      setState((s) => {
        // Approvals asked while this tab was away come with the history, not as events.
        const known = new Set(s.approvals.map((a) => a.id));
        const after = conversation.messages.length;
        const waiting = (conversation.approvals ?? []).filter((a) => !known.has(a.id)).map((a) => ({ ...a, after }));
        return mergeInto({ ...s, conversation, error: null, approvals: [...s.approvals, ...waiting] }, conversation.messages);
      });
    } catch (error) {
      setState((s) => ({ ...s, error }));
    }
  }, [id]);

  useEffect(() => {
    setState(EMPTY);
    void load();
    const source = new EventSource(`/api/conversations/${encodeURIComponent(id)}/events`);
    source.onopen = () => void load();
    source.onmessage = (raw) => {
      const event = JSON.parse(raw.data) as ConversationEvent;
      if (event.kind === "message" && event.message) {
        const message = event.message;
        setState((s) => {
          // An event names no author; a conversation of one person can.
          const people = s.conversation?.participants ?? [];
          const author = message.role === "user" && people.length === 1 ? people[0] : null;
          return mergeInto({ ...s, running: s.running || message.role === "user" }, [{ ...message, author }]);
        });
        if (message.role === "assistant") void queryClient.invalidateQueries({ queryKey: ["conversations"] });
      } else if (event.kind === "delta") {
        setState((s) => ({ ...s, running: true, streamed: (event.restart ? "" : s.streamed) + event.text }));
      } else if (event.kind === "progress") {
        setState((s) => ({
          ...s,
          running: true,
          steps: s.steps.at(-1) === event.text ? s.steps : [...s.steps, event.text],
        }));
      } else if (event.kind === "done") {
        setState((s) => ({ ...s, running: false }));
      } else if (event.kind === "approval" && event.approval_id) {
        const { approval_id, text, options } = event;
        setState((s) =>
          s.approvals.some((a) => a.id === approval_id)
            ? s
            : { ...s, approvals: [...s.approvals, { id: approval_id, question: text, options, after: s.messages.length }] },
        );
      }
    };
    return () => source.close();
  }, [id, load, queryClient]);

  return state;
}
