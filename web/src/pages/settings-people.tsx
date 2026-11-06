import { useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Shield, Trash2, User as UserIcon, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CheckRow } from "@/components/ui/checkbox";
import { Hint, Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { api, type ChannelAccount, type RoleDoc, type Settings, type User } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { useMe } from "@/lib/use-me";

const CHANNELS = ["slack", "web", "signal", "mail"];
const ADDRESS_HINT: Record<string, string> = {
  slack: "Slack member id, e.g. U0123ABCDEF",
  web: "the address used to sign in to Cloudflare Access",
  signal: "phone number with country code, e.g. +15551234567",
  mail: "mail address",
};

// The settings API takes each document as JSON text.
const send = (method: string, path: string, data: unknown) => api(method, path, { text: JSON.stringify(data) });

function useRefresh() {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: ["settings"] });
}

export function UsersPanel({ data }: { data: Settings }) {
  const [editing, setEditing] = useState<User | "new" | null>(null);
  const roleName = (id: string) => data.roles.find((r) => r.id === id)?.name ?? id;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start gap-3">
        <p className="min-w-0 flex-1 text-sm text-muted-foreground">
          Who ai-os talks to and sends to. Changes apply at once. Kept in the data dir, not in the configuration repository.
        </p>
        <Button onClick={() => setEditing("new")}>
          <Plus /> New user
        </Button>
      </div>
      {data.users.map((u) => (
        <Card key={u.id} className="p-4">
          <div className="flex items-start gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
              <UserIcon className="size-4" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{u.name}</span>
                {u.role_ids.map((r) => (
                  <Badge key={r} variant="outline">
                    {roleName(r)}
                  </Badge>
                ))}
                {u.role_ids.length === 0 ? <span className="text-xs text-muted-foreground">no role: cannot chat</span> : null}
              </div>
              {u.aliases.length ? <p className="text-xs text-muted-foreground">also {u.aliases.join(", ")}</p> : null}
              <div className="mt-1 flex flex-wrap gap-1.5">
                {u.accounts.map((a, i) => (
                  <code key={i} className="rounded bg-muted px-1.5 py-0.5 text-xs">
                    {a.channel}: {a.address}
                  </code>
                ))}
              </div>
            </div>
            <Button size="sm" variant="outline" onClick={() => setEditing(u)}>
              <Pencil /> Edit
            </Button>
          </div>
        </Card>
      ))}
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent side="right" className="gap-0 p-0 sm:max-w-xl">
          {editing !== null ? <UserForm user={editing === "new" ? null : editing} roles={data.roles} onDone={() => setEditing(null)} /> : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function UserForm({ user: u, roles, onDone }: { user: User | null; roles: RoleDoc[]; onDone: () => void }) {
  const refresh = useRefresh();
  const confirm = useConfirm();
  const { data: me } = useMe();
  const [name, setName] = useState(u?.name ?? "");
  const [aliases, setAliases] = useState((u?.aliases ?? []).join(", "));
  const [accounts, setAccounts] = useState<ChannelAccount[]>(u?.accounts ?? [{ channel: "web", address: "" }]);
  const [roleIds, setRoleIds] = useState(new Set(u?.role_ids ?? ["member"]));
  const [notes, setNotes] = useState(u?.notes ?? "");
  const [busy, setBusy] = useState(false);
  const isMe = u !== null && me?.name === u.name;
  const setAccount = (i: number, patch: Partial<ChannelAccount>) =>
    setAccounts(accounts.map((a, j) => (j === i ? { ...a, ...patch } : a)));
  const save = async () => {
    setBusy(true);
    try {
      const body = {
        id: u?.id ?? "new",
        name: name.trim(),
        aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean),
        accounts: accounts.map((a) => ({ channel: a.channel.trim(), address: a.address.trim() })).filter((a) => a.channel && a.address),
        role_ids: [...roleIds],
        notes: notes.trim() || null,
      };
      if (u) await send("PUT", `/api/settings/users/${encodeURIComponent(u.id)}`, body);
      else await send("POST", "/api/settings/users", body);
      toast.success("Saved.");
      refresh();
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!u) return;
    if (!(await confirm({ title: `Delete ${u.name}?`, body: "Their conversations stay; they can no longer chat or be messaged.", action: "Delete", destructive: true })))
      return;
    try {
      await api("DELETE", `/api/settings/users/${encodeURIComponent(u.id)}`);
      refresh();
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <form
      className="flex h-full flex-col"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <SheetHeader className="border-b">
        <SheetTitle>{u ? u.name : "New user"}</SheetTitle>
        <SheetDescription>Applies at once.</SheetDescription>
      </SheetHeader>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <Label>
          Name
          <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Anna Muster" />
        </Label>
        <Label>
          Also known as
          <Input value={aliases} onChange={(e) => setAliases(e.target.value)} placeholder="Anna, Mama" />
          <Hint>Comma separated: names people use for them in a message ("tell Mama…").</Hint>
        </Label>
        <div className="space-y-2">
          <div className="text-sm font-medium">Accounts</div>
          {accounts.map((a, i) => (
            <div key={i} className="flex items-start gap-2">
              <NativeSelect className="w-28 shrink-0" value={CHANNELS.includes(a.channel) ? a.channel : "other"} onChange={(e) => setAccount(i, { channel: e.target.value === "other" ? "" : e.target.value })}>
                {CHANNELS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
                <option value="other">other…</option>
              </NativeSelect>
              {!CHANNELS.includes(a.channel) ? (
                <Input className="w-24 shrink-0" value={a.channel} onChange={(e) => setAccount(i, { channel: e.target.value })} placeholder="channel" />
              ) : null}
              <Input className="min-w-0 flex-1 font-mono text-xs" value={a.address} onChange={(e) => setAccount(i, { address: e.target.value })} placeholder={ADDRESS_HINT[a.channel] ?? "address"} />
              <Button type="button" size="icon-sm" variant="ghost" onClick={() => setAccounts(accounts.filter((_, j) => j !== i))} aria-label="Remove account">
                <X />
              </Button>
            </div>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={() => setAccounts([...accounts, { channel: "signal", address: "" }])}>
            <Plus /> Add account
          </Button>
          <Hint>How ai-os recognises them when they write, and how it reaches them.</Hint>
        </div>
        <div>
          <div className="mb-1 text-sm font-medium">Roles</div>
          {roles.map((r) => (
            <CheckRow
              key={r.id}
              label={r.name}
              hint={r.permissions.join(", ") || "no rights"}
              checked={roleIds.has(r.id)}
              onChange={(on) => {
                const next = new Set(roleIds);
                if (on) next.add(r.id);
                else next.delete(r.id);
                setRoleIds(next);
              }}
            />
          ))}
        </div>
        <Label>
          Notes
          <Textarea rows={3} className="font-sans" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Who they are, for the agents: relationship, language, …" />
        </Label>
      </div>
      <div className="flex gap-2 border-t p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <Button type="submit" disabled={busy || !name.trim()} className="flex-1 sm:flex-none">
          {u ? "Save" : "Create"}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <span className="flex-1" />
        {u && !isMe ? (
          <Button type="button" variant="ghost" className="text-destructive" onClick={remove}>
            <Trash2 /> Delete
          </Button>
        ) : null}
      </div>
    </form>
  );
}

export function RolesPanel({ data }: { data: Settings }) {
  const [editing, setEditing] = useState<RoleDoc | "new" | null>(null);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start gap-3">
        <p className="min-w-0 flex-1 text-sm text-muted-foreground">
          Sets of rights given to users. In the configuration repository, so they travel with a branch and to a new machine.
        </p>
        <Button onClick={() => setEditing("new")}>
          <Plus /> New role
        </Button>
      </div>
      {data.roles.map((r) => {
        const holders = data.users.filter((u) => u.role_ids.includes(r.id)).map((u) => u.name);
        return (
          <Card key={r.id} className="p-4">
            <div className="flex items-start gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                <Shield className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{r.name}</span>
                  <code className="text-xs text-muted-foreground">{r.id}</code>
                </div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {r.permissions.length ? (
                    r.permissions.map((p) => (
                      <Badge key={p} variant="secondary">
                        {p}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-xs text-muted-foreground">no rights</span>
                  )}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{holders.length ? `Given to ${holders.join(", ")}` : "Given to nobody"}</p>
              </div>
              <Button size="sm" variant="outline" onClick={() => setEditing(r)}>
                <Pencil /> Edit
              </Button>
            </div>
          </Card>
        );
      })}
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent side="right" className="gap-0 p-0 sm:max-w-xl">
          {editing !== null ? <RoleForm role={editing === "new" ? null : editing} data={data} onDone={() => setEditing(null)} /> : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function RoleForm({ role: r, data, onDone }: { role: RoleDoc | null; data: Settings; onDone: () => void }) {
  const refresh = useRefresh();
  const confirm = useConfirm();
  const [name, setName] = useState(r?.name ?? "");
  const [permissions, setPermissions] = useState(new Set<string>(r?.permissions ?? ["chat"]));
  const [busy, setBusy] = useState(false);
  const holders = r ? data.users.filter((u) => u.role_ids.includes(r.id)) : [];
  const save = async () => {
    setBusy(true);
    try {
      const body = { id: r?.id ?? "new", name: name.trim(), permissions: [...permissions] };
      if (r) await send("PUT", `/api/settings/roles/${encodeURIComponent(r.id)}`, body);
      else await send("POST", "/api/settings/roles", body);
      toast.success("Saved.");
      refresh();
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!r) return;
    if (!(await confirm({ title: `Delete the role ${r.name}?`, action: "Delete", destructive: true }))) return;
    try {
      await api("DELETE", `/api/settings/roles/${encodeURIComponent(r.id)}`);
      refresh();
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <form
      className="flex h-full flex-col"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <SheetHeader className="border-b">
        <SheetTitle>{r ? r.name : "New role"}</SheetTitle>
        <SheetDescription>{r ? `id ${r.id} · applies at once` : "Applies at once."}</SheetDescription>
      </SheetHeader>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <Label>
          Name
          <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Family" />
          {r ? null : <Hint>The id is made from the name and cannot change later.</Hint>}
        </Label>
        <div>
          <div className="mb-1 text-sm font-medium">Rights</div>
          {data.permissions.map((p) => (
            <CheckRow
              key={p}
              label={<code>{p}</code>}
              hint={data.permission_descriptions?.[p]}
              checked={permissions.has(p)}
              onChange={(on) => {
                const next = new Set(permissions);
                if (on) next.add(p);
                else next.delete(p);
                setPermissions(next);
              }}
            />
          ))}
          <Hint>At least one user must keep a role with administer, or nobody could open these settings again.</Hint>
        </div>
      </div>
      <div className="flex gap-2 border-t p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <Button type="submit" disabled={busy || !name.trim()} className="flex-1 sm:flex-none">
          {r ? "Save" : "Create"}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <span className="flex-1" />
        {r ? (
          <Button type="button" variant="ghost" className="text-destructive" onClick={remove} disabled={holders.length > 0} title={holders.length ? `Given to ${holders.map((u) => u.name).join(", ")}` : undefined}>
            <Trash2 /> Delete
          </Button>
        ) : null}
      </div>
    </form>
  );
}
