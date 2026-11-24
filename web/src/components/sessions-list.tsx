import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut, Monitor } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface Session {
  id: string;
  mode: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  user_agent: string;
  address: string;
  current: boolean;
}

/** "Firefox on macOS" from a user agent, roughly; enough to tell one's browsers apart. */
function device(agent: string): string {
  const browser = /Edg\//.test(agent) ? "Edge" : /Firefox\//.test(agent) ? "Firefox" : /Chrome\//.test(agent) ? "Chrome" : /Safari\//.test(agent) ? "Safari" : "A browser";
  const os = /iPhone|iPad/.test(agent) ? "iOS" : /Android/.test(agent) ? "Android" : /Mac OS X/.test(agent) ? "macOS" : /Windows/.test(agent) ? "Windows" : /Linux/.test(agent) ? "Linux" : "";
  return os ? `${browser} on ${os}` : browser;
}

const when = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

/** The browsers signed in with the console's own login: the caller's, or `userId`'s for an administrator. Each can be signed out. */
export function SessionsList({ userId }: { userId?: string }) {
  const queryClient = useQueryClient();
  const query = userId ? `?user=${encodeURIComponent(userId)}` : "";
  const key = ["sessions", userId ?? "me"];
  const { data } = useQuery({ queryKey: key, queryFn: () => api<{ own_login: boolean; sessions: Session[] }>("GET", `/api/sessions${query}`) });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: key });
  const end = async (id: string) => {
    try {
      await api("DELETE", `/api/sessions/${encodeURIComponent(id)}${query}`);
      refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const endAll = async () => {
    try {
      const r = await api<{ ended: number }>("POST", `/api/sessions/end-all${query}`);
      toast.success(r.ended === 1 ? "1 browser signed out." : `${r.ended} browsers signed out.`);
      refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  if (!data) return null;
  if (!data.own_login) {
    return <p className="text-xs text-muted-foreground">Signing in is done by the login proxy in front of ai-os; end sessions there.</p>;
  }
  const others = data.sessions.filter((s) => !s.current);
  return (
    <div className="space-y-2">
      {data.sessions.length === 0 ? <p className="text-xs text-muted-foreground">Not signed in anywhere.</p> : null}
      {data.sessions.map((s) => (
        <div key={s.id} className="flex items-start gap-2 rounded-md border p-2 text-sm">
          <Monitor className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{device(s.user_agent)}</span>
              {s.current ? <Badge variant="secondary">this browser</Badge> : null}
            </div>
            <div className="text-xs text-muted-foreground">
              {s.address ? `${s.address} · ` : ""}last active {when(s.last_seen_at)} · signed in {when(s.created_at)} ({s.mode})
            </div>
          </div>
          {s.current ? null : (
            <Button size="sm" variant="ghost" onClick={() => void end(s.id)}>
              <LogOut /> Sign out
            </Button>
          )}
        </div>
      ))}
      {(userId ? data.sessions.length : others.length) > 0 ? (
        <Button size="sm" variant="outline" onClick={() => void endAll()}>
          <LogOut /> {userId ? "Sign out everywhere" : "Sign out all other browsers"}
        </Button>
      ) : null}
    </div>
  );
}
