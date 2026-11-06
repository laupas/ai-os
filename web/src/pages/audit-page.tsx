import { useQuery } from "@tanstack/react-query";
import { GitCommitHorizontal, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { Diff } from "@/components/history-button";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, NativeSelect } from "@/components/ui/input";
import { api, type AuditEntry } from "@/lib/api";
import { cn } from "@/lib/utils";

const TONE = {
  created: "success",
  changed: "secondary",
  deleted: "destructive",
  performed: "outline",
} as const;

const stamp = (iso: string) =>
  new Date(iso).toLocaleString([], { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

/** Who changed which setting when: the audit trail (users, variables, sign-ins,
 * git actions) together with the configuration repository's commits. */
export function AuditPage() {
  const [area, setArea] = useState("");
  const [filter, setFilter] = useState("");
  const { data, error, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["audit"],
    queryFn: () => api<{ entries: AuditEntry[] }>("GET", "/api/audit?limit=1000"),
  });
  const areas = useMemo(() => [...new Set(data?.entries.map((e) => e.area))].sort(), [data]);
  const needle = filter.trim().toLowerCase();
  const rows = (data?.entries ?? []).filter(
    (e) =>
      (!area || e.area === area) &&
      (!needle ||
        [e.actor, e.actor_email, e.item, e.detail ?? "", e.fields.join(" ")].some((s) => s.toLowerCase().includes(needle))),
  );
  return (
    <Page className="max-w-6xl">
      <PageHeader
        title="Audit"
        description="Who changed what, and when. Configuration in the git repository is read from its history, including commits made on the host."
        actions={
          <>
            <NativeSelect className="w-40" value={area} onChange={(e) => setArea(e.target.value)}>
              <option value="">All areas</option>
              {areas.map((a) => (
                <option key={a}>{a}</option>
              ))}
            </NativeSelect>
            <Input className="w-48" placeholder="Filter" value={filter} onChange={(e) => setFilter(e.target.value)} />
            <Button variant="outline" size="icon" onClick={() => refetch()} aria-label="Reload">
              <RefreshCw className={cn(isFetching && "animate-spin")} />
            </Button>
          </>
        }
      />
      {error ? <ErrorBox error={error} /> : null}
      {isLoading ? <Loading /> : null}
      {data && rows.length === 0 ? <p className="text-sm text-muted-foreground">Nothing recorded.</p> : null}
      <div className="divide-y rounded-xl border">
        {rows.map((e, i) => (
          <AuditRow key={`${e.at}-${e.area}-${e.item}-${i}`} entry={e} />
        ))}
      </div>
    </Page>
  );
}

function AuditRow({ entry: e }: { entry: AuditEntry }) {
  const [open, setOpen] = useState(false);
  const diff = useQuery({
    queryKey: ["audit-diff", e.commit],
    queryFn: () => api<{ diff: string }>("GET", `/api/audit/commits/${e.commit}`),
    enabled: open && Boolean(e.commit),
  });
  const what = e.detail ?? (e.fields.length ? e.fields.join(", ") : null);
  const body = (
    <>
      <span className="w-36 shrink-0 text-xs text-muted-foreground tabular-nums">{stamp(e.at)}</span>
      <span className="w-28 shrink-0 truncate text-sm" title={e.actor_email}>
        {e.actor}
      </span>
      <Badge variant={TONE[e.action]} className="w-20">
        {e.action}
      </Badge>
      <span className="min-w-0 shrink-0 text-sm">
        <span className="text-muted-foreground">{e.area}</span>
        {e.item !== e.area ? <> / {e.item}</> : null}
      </span>
      <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground" title={what ?? undefined}>
        {what}
      </span>
      {e.commit ? (
        <code className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
          <GitCommitHorizontal className="size-3" />
          {e.commit.slice(0, 7)}
        </code>
      ) : null}
    </>
  );
  const row = "flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-left md:flex-nowrap";
  if (!e.commit) return <div className={row}>{body}</div>;
  return (
    <div>
      <button type="button" className={cn(row, "hover:bg-accent/50", open && "bg-accent")} onClick={() => setOpen(!open)}>
        {body}
      </button>
      {open ? (
        <div className="bg-muted/30 px-4 py-3">{diff.isLoading ? <Loading /> : <Diff text={diff.data?.diff ?? ""} />}</div>
      ) : null}
    </div>
  );
}
