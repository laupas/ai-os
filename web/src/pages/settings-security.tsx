import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Copy, KeyRound, Loader2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";
import { ErrorBox, Loading } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { useSecurity, type HandedKey, type SecurityStatus } from "@/lib/use-security";

/** The secrets key: where it comes from, which one it is (by fingerprint), what it
 * opens, and how to replace it. ai-os only reads the key from AIOS_SECRETS_KEY; a key
 * shown here is never stored, it takes effect once it is in the setting. */
export function SecurityPanel() {
  const { data, isLoading, error } = useSecurity();
  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorBox error={error} />;
  return (
    <div className="max-w-3xl space-y-4">
      <KeyStatus status={data} />
      {data.origin === "data_dir" ? <MoveKey status={data} /> : null}
      <ReplaceKey status={data} />
    </div>
  );
}

function KeyStatus({ status }: { status: SecurityStatus }) {
  const moving = status.previous_fingerprints.length > 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Secrets key</CardTitle>
        <CardDescription>
          Encrypts the secrets ai-os stores: secret variables, connector sign-ins and the configuration remote's key. It is
          shown by its fingerprint only, which tells keys apart without giving anything away.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <Row label="In use">
          <code className="rounded bg-muted px-1.5 py-0.5 font-medium">{status.fingerprint}</code>{" "}
          {status.origin === "setting" ? (
            <Badge variant="secondary">from AIOS_SECRETS_KEY</Badge>
          ) : (
            <Badge variant="destructive">from the data dir</Badge>
          )}
        </Row>
        {moving ? (
          <Row label="Previous">
            {status.previous_fingerprints.map((f) => (
              <code key={f} className="mr-1 rounded bg-muted px-1.5 py-0.5">
                {f}
              </code>
            ))}
            <span className="text-muted-foreground">
              {status.on_previous ? `${status.on_previous} still on it: they move at the next start.` : "Nothing needs it any more: remove AIOS_SECRETS_KEY_PREVIOUS and restart."}
            </span>
          </Row>
        ) : null}
        <Row label="Secrets">
          {status.unreadable.length === 0 ? (
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="size-4 text-success" /> {status.total} stored, every one opened by this key.
            </span>
          ) : (
            <span className="space-y-1">
              <span className="flex items-center gap-1.5 text-destructive">
                <AlertTriangle className="size-4" /> {status.unreadable.length} of {status.total} cannot be opened by any key:
              </span>
              <span className="block text-muted-foreground">{status.unreadable.join(", ")}</span>
              <span className="block text-muted-foreground">
                Set the key they were stored with as AIOS_SECRETS_KEY_PREVIOUS and restart, or enter them again.
              </span>
            </span>
          )}
        </Row>
      </CardContent>
    </Card>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[6rem_minmax(0,1fr)] sm:gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0">{children}</span>
    </div>
  );
}

/** An older ai-os generated the key into the data dir: show it once, to put it into the setting. */
function MoveKey({ status }: { status: SecurityStatus }) {
  const [shown, setShown] = useState<HandedKey | null>(null);
  const confirm = useConfirm();
  const reveal = async () => {
    if (!(await confirm({ title: "Show the secrets key?", body: "Anyone who sees it can read the stored secrets in any copy of the data. The audit trail records that you looked.", action: "Show" })))
      return;
    try {
      setShown(await api<HandedKey>("POST", "/api/security/data-dir-key"));
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <Card className="border-warning/60">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="size-4 text-warning" /> Move the key out of the data dir
        </CardTitle>
        <CardDescription>
          An older ai-os generated this key into the data dir, so every copy of it (a backup, a snapshot) can open the
          secrets. Put the same key into AIOS_SECRETS_KEY: nothing has to be encrypted again, and ai-os removes the file at
          the next start. Without the setting, the next version of ai-os does not start.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Steps
          steps={[
            "Show the key and save it in your password manager.",
            "Set it as AIOS_SECRETS_KEY where ai-os runs (.env, the cloud's app settings).",
            `Restart ai-os. This page then shows the same fingerprint, ${status.fingerprint}, from AIOS_SECRETS_KEY.`,
          ]}
        />
        <Button className="mt-4" variant="outline" onClick={reveal}>
          <KeyRound /> Show the key
        </Button>
      </CardContent>
      <KeyDialog handed={shown} onClose={() => setShown(null)} title="The key in the data dir" />
    </Card>
  );
}

/** A new key, for a leak or as routine: handed out once, effective from the setting. */
function ReplaceKey({ status }: { status: SecurityStatus }) {
  const [handed, setHanded] = useState<HandedKey | null>(null);
  const [busy, setBusy] = useState(false);
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const generate = async () => {
    if (!(await confirm({ title: "Generate a new key?", body: "It is shown once and not kept by ai-os. Nothing changes until you set it as AIOS_SECRETS_KEY and restart.", action: "Generate" })))
      return;
    setBusy(true);
    try {
      setHanded(await api<HandedKey>("POST", "/api/security/keys"));
      void queryClient.invalidateQueries({ queryKey: ["security"] });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>Replace the key</CardTitle>
        <CardDescription>
          When the key may have leaked, or as routine. ai-os moves every stored secret onto the new key at the next start;
          until then nothing changes, and an interrupted start simply continues at the next one.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <Steps
          steps={[
            "Generate a new key below and save it in your password manager.",
            `Where ai-os runs, set AIOS_SECRETS_KEY to the new key, and AIOS_SECRETS_KEY_PREVIOUS to the current one (fingerprint ${status.fingerprint}).`,
            "Restart ai-os. This page then shows the new fingerprint, and every secret on it.",
            "Remove AIOS_SECRETS_KEY_PREVIOUS and restart once more. Keep the old key only as long as you keep backups made with it.",
          ]}
        />
        <p className="rounded-lg bg-muted p-3 text-muted-foreground">
          After a leak: a new key protects what is encrypted from now on. If someone had the old key and a copy of the data,
          the secrets themselves are exposed: renew them where they come from (API keys, tokens, passwords) and enter them
          again, and sign in to the connectors again.
        </p>
        <Button onClick={generate} disabled={busy}>
          {busy ? <Loader2 className="animate-spin" /> : <KeyRound />} Generate a new key
        </Button>
      </CardContent>
      <KeyDialog handed={handed} onClose={() => setHanded(null)} title="Your new secrets key" />
    </Card>
  );
}

function Steps({ steps }: { steps: string[] }) {
  return (
    <ol className="list-decimal space-y-1.5 pl-5 text-sm">
      {steps.map((step) => (
        <li key={step}>{step}</li>
      ))}
    </ol>
  );
}

/** Shows a key once; closed, it is gone from the page. */
function KeyDialog({ handed, onClose, title }: { handed: HandedKey | null; onClose: () => void; title: string }) {
  const copy = async () => {
    if (!handed) return;
    try {
      await navigator.clipboard.writeText(handed.key);
      toast.success("Copied. Paste it into your password manager.");
    } catch {
      toast.error("Copying is not allowed here: select the key and copy it.");
    }
  };
  return (
    <Dialog open={handed !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>Shown this once. Save it in your password manager before you close this.</DialogDescription>
        <code className="block rounded-lg border bg-muted p-3 font-mono text-sm break-all select-all">{handed?.key}</code>
        <div className="text-sm text-muted-foreground">
          Fingerprint <code className="rounded bg-muted px-1.5 py-0.5 text-foreground">{handed?.fingerprint}</code>
        </div>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" onClick={onClose}>
            I have saved it
          </Button>
          <Button onClick={copy}>
            <Copy /> Copy
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
