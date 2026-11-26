import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { api, type InstalledVersions, type StoreKind } from "@/lib/api";
import { can, useMe } from "@/lib/use-me";
import { when } from "@/lib/utils";

const v = (version: string) => (/^\d/.test(version) ? `v${version}` : version);

/** What was installed from the Store, by `kind:id`; empty for whoever may not see it. */
export function useInstalledVersions() {
  const { data: me } = useMe();
  const allowed = can(me, "manage_agents") || can(me, "manage_skills") || can(me, "manage_connectors");
  return useQuery({
    queryKey: ["store", "installed"],
    queryFn: () => api<InstalledVersions>("GET", "/api/store/installed"),
    enabled: allowed,
    staleTime: 60_000,
  });
}

/** The version an agent, skill or connector was installed in from the Store, and
 * a newer one if its source offers it. Nothing for one made by hand. */
export function InstalledVersion({ kind, id }: { kind: StoreKind; id: string }) {
  const { data } = useInstalledVersions();
  const row = data?.[`${kind}:${id}`];
  if (!row) return null;
  const from = row.source.replace(/^https?:\/\//, "");
  const title = `Installed from ${from}, ${when(row.installed_at)} by ${row.installed_by}`;
  return (
    <>
      <Badge variant="outline" title={title}>
        {row.version ? v(row.version) : "from the Store"}
      </Badge>
      {row.latest ? (
        <Badge variant="warning" title="A newer version is in the Store">
          {v(row.latest)} available
        </Badge>
      ) : null}
    </>
  );
}
