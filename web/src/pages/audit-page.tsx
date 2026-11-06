import { useQuery } from "@tanstack/react-query";
import { GitCommitHorizontal, RefreshCw } from "lucide-react";
import { useState } from "react";
import { ListView } from "@/components/list-view";
import { Diff } from "@/components/history-button";
import { ErrorBox, Loading, Page, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  const { data, error, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["audit"],
    queryFn: () => api<{ entries: AuditEntry[] }>("GET", "/api/audit?limit=5000"),
  });
  return (
    <Page className="max-w-6xl">
      <PageHeader
        title="Audit"
        description="Who changed what, and when. Configuration in the git repository is read from its history, including commits made on the host."
        actions={
          <Button variant="outline" size="icon" onClick={() => refetch()} aria-label="Reload">
            <RefreshCw className={cn(isFetching && "animate-spin")} />
          </Button>
        }
      />
      {error ? <ErrorBox error={error} /> : null}
      {isLoading ? <Loading /> : null}
      {data ? (
        <ListView
          items={data.entries}
          keyOf={(e) => `${e.at}-${e.area}-${e.item}-${e.commit ?? ""}`}
          text={(e) => [e.actor, e.actor_email, e.item, e.detail ?? "", e.fields.join(" ")].join(" ")}
          facets={[
            { label: "areas", value: (e) => e.area },
            { label: "actions", value: (e) => e.action, options: ["created", "changed", "deleted", "performed"] },
            { label: "people", value: (e) => e.actor },
          ]}
          pageSize={50}
          empty="Nothing recorded yet."
          className="gap-0 divide-y rounded-xl border"
        >
          {(e) => <AuditRow entry={e} />}
        </ListView>
      ) : null}
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
