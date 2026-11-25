import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bot,
  GitBranch,
  KeyRound,
  CalendarClock,
  ClipboardList,
  Brain,
  LayoutGrid,
  Search,
  MessagesSquare,
  Mic,
  Plug,
  ScrollText,
  Settings,
  ShieldCheck,
  Sparkles,
  Store,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { AccountBox } from "@/components/account-box";
import { CommandPalette, shortcut } from "@/components/command-palette";
import { RestartBanner } from "@/components/restart-banner";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { api, type Approval, type GitOverview, type Permission } from "@/lib/api";
import { href } from "@/lib/router";
import { can, useMe } from "@/lib/use-me";
import { cn } from "@/lib/utils";

const GROUPS = ["Work", "Build", "Operate"] as const;

interface NavItem {
  id: string;
  label: string;
  icon: LucideIcon;
  group: (typeof GROUPS)[number];
  needs?: Permission;
}

export const NAV: NavItem[] = [
  { id: "chat", label: "Chat", icon: MessagesSquare, group: "Work" },
  { id: "voice", label: "Voice", icon: Mic, group: "Work", needs: "chat" },
  { id: "approvals", label: "Approvals", icon: ShieldCheck, group: "Work", needs: "approve" },
  // Everyone keeps their own memories; shared and other people's need more.
  { id: "memories", label: "Memories", icon: Brain, group: "Work", needs: "chat" },
  { id: "agents", label: "Agents", icon: Bot, group: "Build", needs: "manage_agents" },
  { id: "skills", label: "Skills", icon: Sparkles, group: "Build", needs: "manage_skills" },
  // Everyone who may chat signs in to per-user connectors here; the rest is for manage_connectors.
  { id: "connectors", label: "Connectors", icon: Plug, group: "Build", needs: "chat" },
  { id: "triggers", label: "Triggers", icon: CalendarClock, group: "Build", needs: "manage_triggers" },
  { id: "store", label: "Store", icon: Store, group: "Build", needs: "administer" },
  { id: "variables", label: "Variables", icon: KeyRound, group: "Operate", needs: "manage_variables" },
  { id: "audit", label: "Audit", icon: ClipboardList, group: "Operate", needs: "view_logs" },
  { id: "logs", label: "Logs", icon: ScrollText, group: "Operate", needs: "view_logs" },
  { id: "health", label: "Health", icon: Activity, group: "Operate", needs: "view_logs" },
  { id: "settings", label: "Settings", icon: Settings, group: "Operate", needs: "administer" },
];

/** On a phone these sit in the tab bar at the bottom; everything else is under More. */
const TABS = ["chat", "voice", "approvals"];

export function useNav() {
  const { data: me } = useMe();
  return NAV.filter((item) => !item.needs || can(me, item.needs));
}

function usePending() {
  const { data: me } = useMe();
  const { data } = useQuery({
    queryKey: ["approvals"],
    queryFn: () => api<{ approvals: Approval[] }>("GET", "/api/approvals"),
    enabled: can(me, "approve"),
    refetchInterval: 15_000,
  });
  return data?.approvals.length ?? 0;
}

/** The configuration branch ai-os runs, always in view, since switching it
 * changes every agent at once. `compact`: for the icon rail. */
function RunningBranch({ compact }: { compact?: boolean }) {
  const { data: me } = useMe();
  const { data } = useQuery({
    queryKey: ["git"],
    queryFn: () => api<GitOverview>("GET", "/api/git"),
    enabled: can(me, "administer"),
    refetchInterval: 30_000,
  });
  if (!data) return null;
  return (
    <a
      href={href("settings", "git")}
      className={cn("flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground", compact ? "flex-col gap-0.5" : "mb-2")}
      title={`The configuration branch ai-os runs: ${data.current}`}
    >
      <GitBranch className="size-3.5" />
      <code className={cn(compact && "max-w-12 truncate text-[10px]", data.current === data.protected ? "" : "font-medium text-warning")}>{data.current}</code>
    </a>
  );
}

/** `rail`: below 1280px only the icons, so a tablet keeps room for the page. */
function NavList({ current, onPick, rail }: { current: string; onPick?: () => void; rail?: boolean }) {
  const items = useNav();
  const pending = usePending();
  const groups = GROUPS.map((group) => ({ group, links: items.filter((n) => n.group === group) })).filter((g) => g.links.length);
  return (
    <nav className="flex flex-col p-2">
      {groups.map(({ group, links }, i) => (
        <div key={group} className="flex flex-col gap-0.5">
          <div className={cn("px-3 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase", i ? "pt-4" : "pt-1", rail && "hidden xl:block")}>
            {group}
          </div>
          {rail && i ? <div className="mx-2 my-2 h-px bg-border xl:hidden" /> : null}
          {links.map(({ id, label, icon: Icon }) => (
            <a
              key={id}
              href={href(id)}
              onClick={onPick}
              title={label}
              aria-label={rail ? label : undefined}
              className={cn(
                "relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground md:py-2",
                rail && "justify-center px-0 xl:justify-start xl:px-3",
                current === id && "bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary",
              )}
            >
              <Icon className="size-4" />
              <span className={cn("flex-1", rail && "hidden xl:inline")}>{label}</span>
              {id === "approvals" && pending > 0 ? (
                <>
                  <span className={cn("rounded-full bg-destructive px-1.5 text-xs text-white", rail && "hidden xl:inline")}>{pending}</span>
                  {rail ? <span className="absolute top-1.5 right-2.5 size-2 rounded-full bg-destructive xl:hidden" /> : null}
                </>
              ) : null}
            </a>
          ))}
        </div>
      ))}
    </nav>
  );
}

/** The phone's way around: the pages used most as tabs at the bottom, in reach of the thumb. */
function TabBar({ current, onMore }: { current: string; onMore: () => void }) {
  const tabs = useNav().filter((n) => TABS.includes(n.id));
  const pending = usePending();
  const tab = "relative flex min-h-14 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-medium";
  const pill = (on: boolean) => cn("flex h-7 w-14 items-center justify-center rounded-full transition-colors", on && "bg-primary/12 text-primary");
  const more = !TABS.includes(current);
  return (
    // Hidden while the on-screen keyboard is up (`keyboard`, see main.tsx): the page needs the room.
    <nav aria-label="Main" className="flex shrink-0 border-t bg-background/95 px-1 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden in-[.keyboard]:hidden">
      {tabs.map(({ id, label, icon: Icon }) => (
        <a key={id} href={href(id)} className={cn(tab, current === id ? "text-foreground" : "text-muted-foreground")} aria-current={current === id ? "page" : undefined}>
          <span className={pill(current === id)}>
            <Icon className="size-5" />
          </span>
          {label}
          {id === "approvals" && pending > 0 ? (
            <span className="absolute top-1 left-1/2 ml-2 rounded-full bg-destructive px-1.5 text-[10px] leading-4 font-semibold text-white">{pending}</span>
          ) : null}
        </a>
      ))}
      <button className={cn(tab, more ? "text-foreground" : "text-muted-foreground")} onClick={onMore}>
        <span className={pill(more)}>
          <LayoutGrid className="size-5" />
        </span>
        More
      </button>
    </nav>
  );
}

/** Behind More on a phone: every page not in the tab bar, by group, then the branch and the account. */
function MoreSheet({ current, open, onOpenChange, onSearch }: { current: string; open: boolean; onOpenChange: (open: boolean) => void; onSearch: () => void }) {
  const { data: me } = useMe();
  const items = useNav().filter((n) => !TABS.includes(n.id));
  const groups = GROUPS.map((group) => ({ group, links: items.filter((n) => n.group === group) })).filter((g) => g.links.length);
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="gap-0 p-0">
        <SheetTitle className="sr-only">More</SheetTitle>
        <div className="flex justify-center pt-2 pb-1">
          <span className="h-1.5 w-10 rounded-full bg-border" />
        </div>
        <div className="space-y-1 overflow-y-auto px-3 pb-4">
          <button
            onClick={() => {
              onOpenChange(false);
              onSearch();
            }}
            className="mx-1 mt-1 flex h-11 w-[calc(100%-0.5rem)] items-center gap-2 rounded-xl bg-muted px-3 text-left text-muted-foreground"
          >
            <Search className="size-4" /> Go to a page, agent or conversation
          </button>
          {groups.map(({ group, links }) => (
            <div key={group}>
              <div className="px-3 pt-3 pb-1 text-xs font-semibold tracking-wider text-muted-foreground uppercase">{group}</div>
              <div className="grid grid-cols-2 gap-1">
                {links.map(({ id, label, icon: Icon }) => (
                  <a
                    key={id}
                    href={href(id)}
                    onClick={() => onOpenChange(false)}
                    className={cn("flex min-h-12 items-center gap-3 rounded-xl px-3 text-sm font-medium hover:bg-accent", current === id && "bg-primary/10 text-primary")}
                  >
                    <Icon className="size-5 text-muted-foreground" />
                    {label}
                  </a>
                ))}
              </div>
            </div>
          ))}
          {me ? (
            <div className="mt-3 rounded-xl border p-4 text-xs text-muted-foreground">
              <RunningBranch />
              <AccountBox me={me} />
            </div>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Brand({ rail }: { rail?: boolean }) {
  return (
    <div className="flex items-center gap-2 font-semibold">
      <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Sparkles className="size-4" />
      </span>
      <span className={cn(rail && "hidden xl:inline")}>ai-os</span>
    </div>
  );
}

/** The full sidebar from 1280px, an icon rail from 768px (its account button opens
 * the sidebar as a sheet); on a phone a tab bar at the bottom with the rest under More.
 * `hideTabBar`: a chat thread, where the composer takes the bottom of the screen. */
export function AppShell({ current, hideTabBar, children }: { current: string; hideTabBar?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [more, setMore] = useState(false);
  const [search, setSearch] = useState(false);
  const { data: me } = useMe();
  // A link inside the More or account panel (Appearance, the branch) goes to another page: close them.
  useEffect(() => {
    setOpen(false);
    setMore(false);
  }, [current]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearch((on) => !on);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    // overflow-clip, not hidden: iOS scrolls an overflow-hidden box to make room for
    // the keyboard and leaves it there, which is how the top bar went missing.
    // A clipped box is no scroll container, so nothing can move it.
    <div className="fixed inset-x-0 top-0 bottom-[var(--keyboard,0px)] flex overflow-clip">
      <aside className="hidden w-16 shrink-0 flex-col border-r bg-muted/30 md:flex xl:w-60">
        <div className="flex h-14 items-center justify-center px-2 xl:justify-start xl:px-5">
          <Brand rail />
        </div>
        <div className="px-2 pb-1">
          <button
            onClick={() => setSearch(true)}
            title={`Go to a page, agent or conversation (${shortcut})`}
            aria-label="Search"
            className="flex h-9 w-full items-center justify-center gap-2 rounded-lg border bg-background px-0 text-sm text-muted-foreground transition-colors hover:text-foreground xl:justify-start xl:px-3"
          >
            <Search className="size-4" />
            <span className="hidden flex-1 text-left xl:inline">Search</span>
            <kbd className="hidden rounded border px-1 font-sans text-[11px] xl:inline">{shortcut}</kbd>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <NavList current={current} rail />
        </div>
        {me ? (
          <>
            <div className="hidden border-t p-4 text-xs text-muted-foreground xl:block">
              <RunningBranch />
              <AccountBox me={me} />
            </div>
            <div className="flex flex-col items-center gap-3 border-t py-3 xl:hidden">
              <RunningBranch compact />
              <button
                className="flex size-9 items-center justify-center rounded-full bg-accent text-sm font-semibold hover:bg-accent/70"
                onClick={() => setOpen(true)}
                aria-label="Account"
                title={me.name}
              >
                {me.name.slice(0, 1).toUpperCase()}
              </button>
            </div>
          </>
        ) : null}
      </aside>
      {/* On a phone the page starts below the status bar; with the tab bar below it,
          the page needs no room for the home indicator (`--safe-bottom`). */}
      <div className="flex min-w-0 flex-1 flex-col overflow-clip pt-[env(safe-area-inset-top)] md:pt-0">
        <RestartBanner />
        <main className={cn("min-h-0 flex-1 overflow-clip", !hideTabBar && "max-md:[--safe-bottom:0px]")}>
          {children}
        </main>
        {hideTabBar ? null : <TabBar current={current} onMore={() => setMore(true)} />}
      </div>
      <MoreSheet current={current} open={more} onOpenChange={setMore} onSearch={() => setSearch(true)} />
      <CommandPalette open={search} onOpenChange={setSearch} />
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="gap-0 p-0">
          <div className="flex h-14 items-center px-5">
            <SheetTitle asChild>
              <div>
                <Brand />
              </div>
            </SheetTitle>
          </div>
          <div className="flex-1 overflow-y-auto">
            <NavList current={current} onPick={() => setOpen(false)} />
          </div>
          {me ? (
            <div className="border-t p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)] text-xs text-muted-foreground">
              <RunningBranch />
              <AccountBox me={me} />
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
