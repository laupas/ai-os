import { useQuery } from "@tanstack/react-query";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Health } from "@/lib/api";
import { href } from "@/lib/router";
import { cn, when } from "@/lib/utils";

function uptime(seconds: number) {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return d ? `${d} d ${h} h` : `${h} h ${m} min`;
}

export function HealthPage() {
  const { data: h, isLoading, error } = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("GET", "/api/health"),
    refetchInterval: 30_000,
  });
  if (isLoading) return <Loading />;
  if (error || !h) return <ErrorBox error={error} />;
  const c = h.counts;
  const stats: [string, string | number, string?][] = [
    ["Up", uptime(h.uptime_seconds), `since ${when(h.started_at)}`],
    ["Errors, 24 h", c.errors_24h, c.errors_24h ? "text-destructive" : undefined],
    ["Warnings, 24 h", c.warnings_24h, c.warnings_24h ? "text-warning" : undefined],
    ["Pending approvals", c.pending_approvals],
    ["Conversations", c.conversations],
    ["Schedules on", `${c.schedules_enabled} / ${c.schedules}`],
    ["Memories", c.memories],
    ["Users", c.users],
  ];
  return (
    <Page>
      <PageHeader title="Health" description={`ai-os ${h.version}`} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map(([label, value, extra]) => (
          <Card key={label} className="p-4">
            <div className="text-xs text-muted-foreground">{label}</div>
            <div className={cn("mt-1 text-2xl font-semibold tabular-nums", extra?.startsWith("text-") && extra)}>{value}</div>
            {extra && !extra.startsWith("text-") ? <div className="mt-0.5 text-xs text-muted-foreground">{extra}</div> : null}
          </Card>
        ))}
      </div>
      <Card>
        <CardContent className="divide-y pt-2 md:pt-2">
          {(
            [
              ["Channels", h.channels],
              ["Senders", h.senders],
              ["MCP servers", h.mcp_servers],
            ] as [string, string[]][]
          ).map(([label, items]) => (
            <div key={label} className="flex flex-wrap items-center gap-2 py-3">
              <span className="w-32 text-sm text-muted-foreground">{label}</span>
              {items.length ? items.map((x) => <Badge key={x} variant="secondary">{x}</Badge>) : <span className="text-sm">none</span>}
            </div>
          ))}
          <div className="flex items-center gap-2 py-3">
            <span className="w-32 text-sm text-muted-foreground">Scheduler</span>
            <Badge variant={h.scheduler ? "success" : "destructive"}>{h.scheduler ? "running" : "off"}</Badge>
          </div>
        </CardContent>
      </Card>
      {h.last_problem ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              Latest warning or error ·{" "}
              <a className="font-normal underline" href={href("logs")}>
                all logs
              </a>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-lg bg-muted/50 p-3 font-mono text-xs whitespace-pre-wrap">{h.last_problem}</pre>
          </CardContent>
        </Card>
      ) : null}
    </Page>
  );
}
