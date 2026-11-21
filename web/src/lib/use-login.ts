import { useQuery } from "@tanstack/react-query";
import { api, type LoginInfo } from "./api";

/** The console's own login. Open to anyone when there is one; behind a proxy it answers only once signed in. */
export function useLogin(enabled = true) {
  return useQuery({ queryKey: ["login"], queryFn: () => api<LoginInfo>("GET", "/api/login"), retry: false, enabled, staleTime: 60_000 });
}
