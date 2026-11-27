import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Link } from "lucide-react";
import { toast } from "sonner";
import { useInstalledVersions } from "@/components/installed-version";
import { Button } from "@/components/ui/button";
import { api, type StoreInstallResult, type StoreKind } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { can, useMe } from "@/lib/use-me";

const KEPT: Record<StoreKind, string> = {
  connector: "Who has it, whether it is on, its sign-in mode, its sign-ins and its variables stay as they are.",
  agent: "Who has it and whether it is on stay as they are; its prompt, model, tools, skills and connectors come from the template.",
  skill: "Agents granted it keep it.",
  trigger: "",
};

const v = (version: string) => (/^\d/.test(version) ? `v${version}` : version);

/** Brings one item installed from the Store, a copy too, to what its source offers
 * now: Update when there is a newer version, else Reinstall. One made here that a
 * source offers too gets Link to Store instead. For administrators. */
export function StoreUpdateButton({ kind, id, onDone }: { kind: StoreKind; id: string; onDone?: () => void }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { data: me } = useMe();
  const { data } = useInstalledVersions();
  const row = data?.[`${kind}:${id}`];
  const update = useMutation({
    mutationFn: () => api<StoreInstallResult>("POST", "/api/store/update", { kind, id, trust_code: Boolean(row?.code) }),
    onSuccess: async (result) => {
      toast.success(`${id} is ${result.version ? v(result.version) : "the template"} now.`);
      await Promise.all(["store", "connectors", "agents", "skills"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
      onDone?.();
    },
    onError: (e) => toast.error(e.message),
  });
  const link = useMutation({
    mutationFn: () => api("POST", "/api/store/link", { source: row?.source, kind, id }),
    onSuccess: async () => {
      toast.success(`${id} is linked to the Store.`);
      await queryClient.invalidateQueries({ queryKey: ["store"] });
    },
    onError: (e) => toast.error(e.message),
  });
  if (!row || !can(me, "administer")) return null;
  if (row.linked === false) {
    const offered = row.offered ? ` ${v(row.offered)}` : "";
    const askLink = async () => {
      const body = [
        `${id} stays exactly as it is. It is recorded as${offered} of the ${kind} ${id} from ${row.source.replace(/^https?:\/\//, "")},`,
        "so it shows where it came from and is offered that source's updates.",
        "If it was changed here, an update later replaces those changes.",
      ];
      if (await confirm({ title: `Link ${id} to the Store?`, body: body.join(" "), action: "Link" })) link.mutate();
    };
    return (
      <Button size="sm" variant="outline" onClick={() => void askLink()} disabled={link.isPending}>
        <Link /> {link.isPending ? "Linking…" : "Link to Store"}
      </Button>
    );
  }
  const verb = row.latest ? `Update to ${v(row.latest)}` : "Reinstall";
  const ask = async () => {
    const from = row.copy_of ? `the template ${row.copy_of}` : "the template";
    const body = [
      `This replaces ${id} with ${from} from ${row.source.replace(/^https?:\/\//, "")}, and with it any change made to it here.`,
      KEPT[kind],
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
