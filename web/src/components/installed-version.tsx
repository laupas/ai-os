import { useQuery } from "@tanstack/react-query";
import { Store } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { api, type InstalledVersions, type StoreKind } from "@/lib/api";
import { can, useMe } from "@/lib/use-me";
import { when } from "@/lib/utils";

const v = (version: string) => (/^\d/.test(version) ? `v${version}` : version);

/** What was installed from the Store, by `kind:id`; empty for whoever may not see it. */
export function useInstalledVersions() {
  const { data: me } = useMe();
  const allowed = can(me, "manage_agents") || can(me, "manage_skills") || can(me, "manage_connectors") || can(me, "manage_triggers");
  return useQuery({
    queryKey: ["store", "installed"],
    queryFn: () => api<InstalledVersions>("GET", "/api/store/installed"),
    enabled: allowed,
    staleTime: 60_000,
  });
}

/** Where an agent, skill, connector or trigger came from in the Store: the source,
 * the version, the template a copy was made from, and a newer version if its
 * source offers one. For one made here that a source offers too, a dashed "also in"
 * badge; nothing for anything else. */
export function InstalledVersion({ kind, id }: { kind: StoreKind; id: string }) {
  const { data } = useInstalledVersions();
  const row = data?.[`${kind}:${id}`];
  if (!row) return null;
  const url = row.source.replace(/^https?:\/\//, "");
  const from = row.source_name || url.replace(/\.git$/, "").split("/").slice(-1)[0];
  if (row.linked === false)
    return (
      <Badge
        variant="outline"
        title={`Not installed from the Store, but ${url} offers a ${kind} ${id} too. Link it to the Store to show where it came from and get its updates.`}
        className="gap-1 border-dashed font-normal text-muted-foreground"
      >
        <Store className="size-3" />
        also in {[from, row.offered ? v(row.offered) : null].filter(Boolean).join(" · ")}
      </Badge>
    );
  const title = `From the Store: ${url}${row.copy_of ? `, template ${row.copy_of}` : ""}, installed ${row.installed_at ? when(row.installed_at) : ""} by ${row.installed_by}`;
  const parts = [from, row.version ? v(row.version) : null, row.copy_of && row.copy_of !== id ? `from ${row.copy_of}` : null];
  return (
    <>
      <Badge variant="outline" title={title} className="gap-1 font-normal">
        <Store className="size-3" />
        {parts.filter(Boolean).join(" · ")}
      </Badge>
      {row.latest ? (
        <Badge variant="warning" title="A newer version is in the Store">
          {v(row.latest)} available
        </Badge>
      ) : null}
    </>
  );
}
