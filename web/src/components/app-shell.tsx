import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bot,
  GitBranch,
  KeyRound,
  CalendarClock,
  Brain,
  MenuIcon,
  MessagesSquare,
  Plug,
  ScrollText,
  Settings,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { RestartBanner } from "@/components/restart-banner";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { api, type Approval, type GitOverview, type Permission } from "@/lib/api";
import { href } from "@/lib/router";
import { can, useMe } from "@/lib/use-me";
import { cn } from "@/lib/utils";

interface NavItem {
  id: string;
  label: string;
  icon: LucideIcon;
  needs?: Permission;
}

export const NAV: NavItem[] = [
  { id: "chat", label: "Chat", icon: MessagesSquare },
  { id: "approvals", label: "Approvals", icon: ShieldCheck, needs: "approve" },
  { id: "schedules", label: "Schedules", icon: CalendarClock, needs: "administer" },
  { id: "memories", label: "Memories", icon: Brain, needs: "administer" },
  { id: "agents", label: "Agents", icon: Bot, needs: "administer" },
  { id: "skills", label: "Skills", icon: Sparkles, needs: "administer" },
  { id: "connectors", label: "Connectors", icon: Plug, needs: "administer" },
  { id: "variables", label: "Variables", icon: KeyRound, needs: "administer" },
  { id: "logs", label: "Logs", icon: ScrollText, needs: "administer" },
  { id: "health", label: "Health", icon: Activity, needs: "administer" },
  { id: "settings", label: "Settings", icon: Settings, needs: "administer" },
];

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
 * changes every agent at once. */
function RunningBranch() {
  const { data: me } = useMe();
  const { data } = useQuery({
    queryKey: ["git"],
    queryFn: () => api<GitOverview>("GET", "/api/git"),
    enabled: can(me, "administer"),
    refetchInterval: 30_000,
  });
  if (!data) return null;
  return (
    <a href={href("settings", "git")} className="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground" title="The configuration branch ai-os runs">
      <GitBranch className="size-3.5" />
      <code className={data.current === data.protected ? "" : "font-medium text-warning"}>{data.current}</code>
    </a>
  );
}

function NavList({ current, onPick }: { current: string; onPick?: () => void }) {
  const items = useNav();
  const pending = usePending();
  return (
    <nav className="flex flex-col gap-0.5 p-2">
      {items.map(({ id, label, icon: Icon }) => (
        <a
          key={id}
          href={href(id)}
          onClick={onPick}
          className={cn(
            "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground md:py-2",
            current === id && "bg-accent text-foreground",
          )}
        >
          <Icon className="size-4" />
          <span className="flex-1">{label}</span>
          {id === "approvals" && pending > 0 ? (
            <span className="rounded-full bg-destructive px-1.5 text-xs text-white">{pending}</span>
          ) : null}
        </a>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2 font-semibold">
      <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Sparkles className="size-4" />
      </span>
      ai-os
    </div>
  );
}

/** Sidebar on a wide screen; on a phone a top bar whose menu opens the same list as a sheet. */
export function AppShell({ current, hideMobileBar, children }: { current: string; hideMobileBar?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { data: me } = useMe();
  const pending = usePending();
  const title = NAV.find((n) => n.id === current)?.label ?? "ai-os";
  return (
    // overflow-clip, not hidden: iOS scrolls an overflow-hidden box to make room for
    // the keyboard and leaves it there, which is how the top bar went missing.
    // A clipped box is no scroll container, so nothing can move it.
    <div className="fixed inset-x-0 top-0 bottom-[var(--keyboard,0px)] flex overflow-clip">
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-muted/30 md:flex">
        <div className="flex h-14 items-center px-5">
          <Brand />
        </div>
        <div className="flex-1 overflow-y-auto">
          <NavList current={current} />
        </div>
        {me ? (
          <div className="border-t p-4 text-xs text-muted-foreground">
            <RunningBranch />
            <div className="font-medium text-foreground">{me.name}</div>
            <div className="truncate">{me.email}</div>
          </div>
        ) : null}
      </aside>
      <div className="flex min-w-0 flex-1 flex-col overflow-clip">
        {hideMobileBar ? null : (
          <header className="flex h-[calc(3.25rem+env(safe-area-inset-top))] shrink-0 items-center gap-2 border-b bg-background/80 px-2 pt-[env(safe-area-inset-top)] backdrop-blur md:hidden">
            <button
              className="relative flex size-10 items-center justify-center rounded-lg hover:bg-accent"
              onClick={() => setOpen(true)}
              aria-label="Menu"
            >
              <MenuIcon className="size-5" />
              {pending > 0 ? <span className="absolute top-2 right-2 size-2 rounded-full bg-destructive" /> : null}
            </button>
            <span className="font-semibold">{title}</span>
          </header>
        )}
        <RestartBanner />
        <main className="min-h-0 flex-1 overflow-clip">{children}</main>
      </div>
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
          {me ? <div className="border-t p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)] text-xs text-muted-foreground">{me.email}</div> : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
