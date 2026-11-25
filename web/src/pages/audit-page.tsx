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
  // A phone stacks it: who, action and when; then what, with the commit; then the detail.
  // From 768px it is one line of columns (`contents` lets the first group join them).
  const body = (
    <>
      <span className="col-start-2 row-start-1 justify-self-end text-xs text-muted-foreground tabular-nums md:w-36 md:shrink-0">{stamp(e.at)}</span>
      <span className="col-start-1 row-start-1 flex min-w-0 items-center gap-2 md:contents">
        <span className="min-w-0 truncate text-sm font-medium md:w-28 md:shrink-0 md:font-normal" title={e.actor_email}>
          {e.actor}
        </span>
        <Badge variant={TONE[e.action]} className="md:w-20">
          {e.action}
        </Badge>
      </span>
      <span className="col-start-1 row-start-2 min-w-0 truncate text-sm md:shrink-0">
        <span className="text-muted-foreground">{e.area}</span>
        {e.item !== e.area ? <> / {e.item}</> : null}
      </span>
      {what ? (
        <span className="col-span-2 row-start-3 min-w-0 truncate text-xs text-muted-foreground md:flex-1" title={what}>
          {what}
        </span>
      ) : null}
      {e.commit ? (
        <code className="col-start-2 row-start-2 flex shrink-0 items-center gap-1 justify-self-end text-xs text-muted-foreground md:ml-auto">
          <GitCommitHorizontal className="size-3" />
          {e.commit.slice(0, 7)}
        </code>
      ) : null}
    </>
  );
  const row = "grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0.5 px-3 py-2.5 text-left md:flex md:py-2";
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
