import { useQuery } from "@tanstack/react-query";
import { Power } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { href } from "@/lib/router";
import { restartAiOs } from "@/lib/restart";
import { can, useMe } from "@/lib/use-me";

/** aios.yaml is read once, at start: when it differs from what ai-os started with
 * (a save, a branch switch, a pull), say so where it cannot be missed. */
export function RestartBanner() {
  const { data: me } = useMe();
  const confirm = useConfirm();
  const { data } = useQuery({
    queryKey: ["restart-needed"],
    queryFn: () => api<{ restart_needed: boolean }>("GET", "/api/restart-needed"),
    enabled: can(me, "administer"),
    refetchInterval: 30_000,
  });
  if (!data?.restart_needed) return null;
  const restart = async () => {
    if (!(await confirm({ title: "Restart ai-os?", body: "Running turns are stopped. The page reloads when it is back.", action: "Restart" })))
      return;
    try {
      await restartAiOs();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <div className="flex shrink-0 flex-wrap items-center gap-2 border-b bg-warning/20 px-4 py-2 text-sm">
      <span className="flex-1">
        <a className="underline" href={href("settings")}>
          aios.yaml
        </a>{" "}
        changed since ai-os started: channels, approvals and the rest of it apply after a restart.
      </span>
      <Button size="sm" onClick={restart}>
        <Power /> Restart now
      </Button>
    </div>
  );
}
