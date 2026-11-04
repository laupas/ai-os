import { useQuery } from "@tanstack/react-query";
import { api, type Me, type Permission } from "./api";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api<Me>("GET", "/api/me"), staleTime: 60_000, retry: false });
}

export function can(me: Me | undefined, permission: Permission): boolean {
  return Boolean(me?.permissions.includes(permission));
}
