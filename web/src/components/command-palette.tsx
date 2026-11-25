import { useQuery } from "@tanstack/react-query";
import { CornerDownLeft, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNav } from "@/components/app-shell";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { api, type ConversationSummary } from "@/lib/api";
import { href } from "@/lib/router";
import { cn, when } from "@/lib/utils";
import { useAgents } from "@/pages/agents-page";
import { SECTIONS } from "@/pages/settings-page";

interface Hit {
  group: string;
  label: string;
  hint?: string;
  to: string;
}

const PER_GROUP = 6;

export const shortcut = /Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘K" : "Ctrl K";

/** ⌘K (Ctrl K): go to a page, a settings section, an agent or a conversation by typing
 * part of its name. Only what the user may open is offered. */
export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const nav = useNav();
  const may = (id: string) => nav.some((n) => n.id === id);
  // The same queries as the pages, so their data is shared rather than fetched twice.
  const agents = useAgents({ enabled: open && may("agents") });
  const conversations = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api<{ conversations: ConversationSummary[] }>("GET", "/api/conversations?limit=500"),
    enabled: open,
  });
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const list = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  const hits = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matches = (text: string) => !needle || text.toLowerCase().includes(needle);
    const pages: Hit[] = [
      ...nav.map((n) => ({ group: "Pages", label: n.label, hint: n.group, to: href(n.id) })),
      { group: "Pages", label: "Appearance", hint: "Account", to: href("appearance") },
    ].filter((p) => matches(`${p.label} ${p.label === "Appearance" ? "theme colour color dark light" : ""}`));
    const sections: Hit[] = may("settings")
      ? SECTIONS.flatMap((g) => g.items)
          .filter((s) => needle && matches(`settings ${s.label}`))
          .map((s) => ({ group: "Settings", label: s.label, hint: "Settings", to: href("settings", s.id) }))
      : [];
    const agentHits: Hit[] = (agents.data?.agents ?? [])
      .filter((a) => needle && matches(`${a.name} ${a.description}`))
      .map((a) => ({ group: "Agents", label: a.name, hint: a.model ?? undefined, to: href("agents", a.name) }));
    const chats: Hit[] = (conversations.data?.conversations ?? [])
      .filter((c) => matches([c.title, c.preview, c.agent, ...c.participants].filter(Boolean).join(" ")))
      .map((c) => ({ group: needle ? "Conversations" : "Recent conversations", label: c.title || c.preview || "(no messages)", hint: when(c.last_at || c.updated_at), to: href("chat", c.id) }));
    return [pages, sections, agentHits, chats].flatMap((group) => group.slice(0, PER_GROUP));
  }, [query, nav, agents.data, conversations.data]);

  const current = Math.min(active, Math.max(0, hits.length - 1));
  useEffect(() => {
    list.current?.querySelector(`[data-index="${current}"]`)?.scrollIntoView({ block: "nearest" });
  }, [current]);

  const pick = (hit: Hit | undefined) => {
    if (!hit) return;
    onOpenChange(false);
    location.hash = hit.to;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl gap-0 overflow-hidden p-0 sm:top-[12vh] sm:translate-y-0" aria-describedby={undefined}>
        <DialogTitle className="sr-only">Go to</DialogTitle>
        <div className="flex items-center gap-2 border-b px-4">
          <Search className="size-4 shrink-0 text-muted-foreground" />
          <input
            autoFocus
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((current + 1) % Math.max(1, hits.length));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((current - 1 + hits.length) % Math.max(1, hits.length));
              } else if (e.key === "Enter") {
                e.preventDefault();
                pick(hits[current]);
              }
            }}
            placeholder="Go to a page, agent or conversation"
            aria-label="Go to"
            role="combobox"
            aria-expanded="true"
            aria-controls="command-results"
            aria-activedescendant={hits.length ? `command-${current}` : undefined}
            className="h-13 min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted-foreground"
          />
        </div>
        <div ref={list} id="command-results" role="listbox" className="max-h-[min(26rem,55dvh)] overflow-y-auto p-2">
          {hits.length === 0 ? <p className="px-3 py-6 text-center text-sm text-muted-foreground">Nothing found.</p> : null}
          {hits.map((hit, i) => (
            <div key={`${hit.group}-${hit.to}`}>
              {i === 0 || hits[i - 1].group !== hit.group ? (
                <div className="px-3 pt-2 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{hit.group}</div>
              ) : null}
              <button
                id={`command-${i}`}
                data-index={i}
                role="option"
                aria-selected={i === current}
                onMouseMove={() => setActive(i)}
                onClick={() => pick(hit)}
                className={cn(
                  "flex min-h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm pointer-coarse:min-h-12",
                  i === current && "bg-primary/10 text-primary",
                )}
              >
                <span className="min-w-0 flex-1 truncate">{hit.label}</span>
                {hit.hint ? <span className="shrink-0 text-xs text-muted-foreground">{hit.hint}</span> : null}
                {i === current ? <CornerDownLeft className="size-3.5 shrink-0 pointer-coarse:hidden" /> : null}
              </button>
            </div>
          ))}
        </div>
        <div className="hidden gap-4 border-t px-4 py-2 text-xs text-muted-foreground sm:flex">
          <span>↑ ↓ to move</span>
          <span>Enter to open</span>
          <span>Esc to close</span>
        </div>
      </DialogContent>
    </Dialog>
  );
}
