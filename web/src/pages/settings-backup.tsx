import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Download, History, Loader2, Upload } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { href } from "@/lib/router";
import { useSecurity, type SecurityStatus } from "@/lib/use-security";

interface BackupContents {
  created_at: string;
  aios_version: string;
  key_fingerprint: string;
  files: number;
  size: number;
  folders: Record<string, number>;
}

interface RestoreStatus {
  pending: BackupContents | null;
  confirmed: boolean;
  failure: string | null;
  last: { restored_at: string; backup: BackupContents; kept_in: string } | null;
}

const stamp = (iso: string) => new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });

const sizeOf = (bytes: number) => (bytes > 1_000_000 ? `${(bytes / 1_000_000).toFixed(1)} MB` : `${Math.ceil(bytes / 1000)} kB`);

/** Download the data dir as one file, sealed with the secrets key, and restore one. */
export function BackupPanel() {
  return (
    <div className="max-w-3xl space-y-4">
      <DownloadCard />
      <RestoreCard />
    </div>
  );
}

function DownloadCard() {
  const { data: security } = useSecurity();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);
  const download = async () => {
    if (!(await confirm({ title: "Download a backup?", body: "It holds everyone's conversations, memories and stored secrets, encrypted. The audit trail records the download.", action: "Download" })))
      return;
    setBusy(true);
    try {
      // Not through api(): the answer is a file, not JSON.
      const response = await fetch("/api/backup", { method: "POST", headers: { "X-Aios": "1" } });
      if (!response.ok) throw new Error((await response.text()) || response.statusText);
      const name = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "")?.[1] ?? "aios-backup.aiosbackup";
      const blob = await response.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = name;
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 60_000);
      toast.success(`Backup downloaded: ${sizeOf(blob.size)}.`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>Download a backup</CardTitle>
        <CardDescription>
          Everything ai-os keeps in its data dir, as one file: users and groups, conversations, memories, approvals, the
          configuration repository with its history, variables, connector sign-ins and the Claude CLI's sign-ins.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="space-y-1.5">
          <div className="font-medium">Left out</div>
          <ul className="list-disc space-y-0.5 pl-5 text-muted-foreground">
            <li>the logs, and the browsers signed in to the console (everyone signs in again)</li>
            <li>the Claude CLI's transcripts: past turns cannot be resumed after a restore, conversations stay</li>
            <li>decrypted copies of secrets, which ai-os writes again when needed</li>
          </ul>
        </div>
        <div className="space-y-1.5">
          <div className="font-medium">Encrypted with the secrets key</div>
          <p className="text-muted-foreground">
            The file opens only with the key in use now
            {security ? (
              <>
                , fingerprint <code className="rounded bg-muted px-1.5 py-0.5 text-foreground">{security.fingerprint}</code>
              </>
            ) : null}
            . Keep that key as long as you keep the backup, even after replacing it under{" "}
            <a className="underline" href={href("settings", "security")}>
              Security
            </a>
            . The file name ends with the same fingerprint.
          </p>
        </div>
        <Button onClick={download} disabled={busy}>
          {busy ? <Loader2 className="animate-spin" /> : <Download />} Download backup
        </Button>
      </CardContent>
    </Card>
  );
}

/** Restarts for a restore, then reloads once ai-os answers. It answers "signed out"
 * then: signed-in browsers are not in a backup. */
async function restartForRestore() {
  await api("POST", "/api/restart");
  toast("Restoring and restarting…");
  const wait = async () => {
    try {
      const response = await fetch("/api/me");
      if ([200, 401, 403].includes(response.status)) return location.reload();
    } catch {
      // not back yet
    }
    setTimeout(wait, 2000);
  };
  setTimeout(wait, 3000);
}

/** Upload a backup, see what it holds, then restore it at a restart. Nothing in the
 * data dir changes before the restart; the data a restore replaces is kept. */
function RestoreCard() {
  const { data: security } = useSecurity();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const { data: status } = useQuery({
    queryKey: ["restore"],
    queryFn: () => api<RestoreStatus>("GET", "/api/backup/restore"),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["restore"] });

  const upload = async (file: File) => {
    setBusy(true);
    try {
      // Not through api(): the body is the file itself.
      const response = await fetch("/api/backup/restore", {
        method: "POST",
        headers: { "X-Aios": "1", "Content-Type": "application/octet-stream" },
        body: file,
      });
      if (!response.ok) throw new Error((await response.text()) || response.statusText);
      toast.success("The backup is checked. Look at what it holds, then restore it.");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
      void refresh();
    }
  };
  const discard = async () => {
    try {
      await api("DELETE", "/api/backup/restore");
      void refresh();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const restore = async () => {
    if (
      !(await confirm({
        title: "Restore this backup?",
        body: "ai-os restarts and replaces its data with the backup's. The data in place now is kept beside it, so this can be undone by hand. Everyone, you too, signs in again.",
        action: "Restore and restart",
        destructive: true,
      }))
    )
      return;
    try {
      await api("POST", "/api/backup/restore/confirm");
      await restartForRestore();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Restore from a backup</CardTitle>
        <CardDescription>
          The backup is checked first: its key, the archive and every file in it. Restoring happens at a restart, before
          ai-os reads any data. The data in place is kept, in a folder named <code>.before-restore-</code> and the time, in
          the data dir.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {status?.last ? (
          <Note icon={<History className="size-4 shrink-0 text-success" />}>
            Restored on {stamp(status.last.restored_at)} from the backup of {stamp(status.last.backup.created_at)}. The data
            it replaced is in <code>{status.last.kept_in}</code> in the data dir: remove that folder once everything is as it
            should be.
          </Note>
        ) : null}
        {status?.failure ? (
          <Note icon={<AlertTriangle className="size-4 shrink-0 text-destructive" />}>
            The last restore did not run, nothing was changed: {status.failure}
          </Note>
        ) : null}
        {status?.pending ? (
          <Pending contents={status.pending} security={security} />
        ) : (
          <>
            <input
              ref={input}
              type="file"
              accept=".aiosbackup"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void upload(file);
              }}
            />
            <Button variant="outline" onClick={() => input.current?.click()} disabled={busy}>
              {busy ? <Loader2 className="animate-spin" /> : <Upload />} Choose a backup file
            </Button>
          </>
        )}
        {status?.pending ? (
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button variant="outline" onClick={discard}>
              Discard
            </Button>
            <Button variant="destructive" onClick={restore}>
              {status.confirmed ? "Restart to restore" : "Restore and restart"}
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Note({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="flex gap-2 rounded-lg border bg-muted/40 p-3">
      {icon}
      <span>{children}</span>
    </div>
  );
}

function Pending({ contents, security }: { contents: BackupContents; security?: SecurityStatus }) {
  const known = security
    ? contents.key_fingerprint === security.fingerprint
      ? "the key in use"
      : "a previous key"
    : null;
  return (
    <div className="space-y-3 rounded-lg border p-3">
      <div className="flex items-center gap-2 font-medium">
        <CheckCircle2 className="size-4 text-success" /> Checked, ready to restore
      </div>
      <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[8rem_minmax(0,1fr)]">
        <dt className="text-muted-foreground">Made</dt>
        <dd>
          {stamp(contents.created_at)}, ai-os {contents.aios_version}
        </dd>
        <dt className="text-muted-foreground">Key</dt>
        <dd>
          <code className="rounded bg-muted px-1.5 py-0.5">{contents.key_fingerprint}</code>
          {known ? <span className="ml-2 text-muted-foreground">{known}</span> : null}
        </dd>
        <dt className="text-muted-foreground">Holds</dt>
        <dd>
          {contents.files} files, {sizeOf(contents.size)} unpacked
        </dd>
      </dl>
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(contents.folders).map(([name, count]) => (
          <Badge key={name} variant="secondary" className="font-normal">
            {name} · {count}
          </Badge>
        ))}
      </div>
    </div>
  );
}
