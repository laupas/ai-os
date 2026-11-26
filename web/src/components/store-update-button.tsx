import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { toast } from "sonner";
import { useInstalledVersions } from "@/components/installed-version";
import { Button } from "@/components/ui/button";
import { api, type StoreInstallResult, type StoreKind } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { can, useMe } from "@/lib/use-me";

const v = (version: string) => (/^\d/.test(version) ? `v${version}` : version);

/** Brings one item installed from the Store, a copy too, to what its source offers
 * now: Update when there is a newer version, else Reinstall. For administrators. */
export function StoreUpdateButton({ kind, id }: { kind: StoreKind; id: string }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { data: me } = useMe();
  const { data } = useInstalledVersions();
  const row = data?.[`${kind}:${id}`];
  const update = useMutation({
    mutationFn: () => api<StoreInstallResult>("POST", "/api/store/update", { kind, id, trust_code: Boolean(row?.code) }),
    onSuccess: (result) => {
      toast.success(`${id} is ${result.version ? v(result.version) : "the template"} now.`);
      for (const key of ["store", "connectors", "agents", "skills"]) void queryClient.invalidateQueries({ queryKey: [key] });
    },
    onError: (e) => toast.error(e.message),
  });
  if (!row || !can(me, "administer")) return null;
  const verb = row.latest ? `Update to ${v(row.latest)}` : "Reinstall";
  const ask = async () => {
    const from = row.copy_of ? `the template ${row.copy_of}` : "the template";
    const body = [
      `This replaces ${id} with ${from} from ${row.source.replace(/^https?:\/\//, "")}, and with it any change made to its description or config here.`,
      "Who has it, whether it is on, its sign-in mode, its sign-ins and its variables stay as they are.",
      row.code ? "It is a code connector: its code is copied again from the source and runs on this server." : "",
    ];
    if (await confirm({ title: `${verb.replace(/ to .*/, "")} ${id}?`, body: body.filter(Boolean).join(" "), action: verb, destructive: !row.latest }))
      update.mutate();
  };
  return (
    <Button size="sm" variant={row.latest ? "default" : "outline"} onClick={() => void ask()} disabled={update.isPending}>
      <Download /> {update.isPending ? "Updating…" : verb}
    </Button>
  );
}
