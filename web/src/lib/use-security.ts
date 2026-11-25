import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { can, useMe } from "@/lib/use-me";

/** The secrets key in use and the secrets it opens (Settings → Security). */
export interface SecurityStatus {
  origin: "setting" | "data_dir";
  fingerprint: string;
  previous_fingerprints: string[];
  legacy_file: boolean;
  total: number;
  on_previous: number;
  unreadable: string[];
}

export interface HandedKey {
  key: string;
  fingerprint: string;
}

export function useSecurity() {
  const { data: me } = useMe();
  return useQuery({
    queryKey: ["security"],
    queryFn: () => api<SecurityStatus>("GET", "/api/security"),
    enabled: can(me, "administer"),
    refetchInterval: 60_000,
  });
}

/** What needs an administrator, in one sentence; null when nothing does. */
export function securityProblem(status: SecurityStatus | undefined): string | null {
  if (!status) return null;
  if (status.origin === "data_dir") return "The secrets key is in the data dir, where every copy of the data carries it. Move it into AIOS_SECRETS_KEY.";
  if (status.unreadable.length)
    return `${status.unreadable.length} stored secret${status.unreadable.length === 1 ? "" : "s"} cannot be opened with the key in use.`;
  if (status.previous_fingerprints.length && !status.on_previous)
    return "Every secret is on the new key: remove AIOS_SECRETS_KEY_PREVIOUS and restart.";
  return null;
}
