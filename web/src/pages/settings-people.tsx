import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Pencil, Plus, Shield, Trash2, User as UserIcon, Users, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ListView } from "@/components/list-view";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CheckRow } from "@/components/ui/checkbox";
import { Hint, Input, Label, NativeSelect, Textarea } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { api, type ChannelAccount, type GroupDoc, type PasswordState, type RoleDoc, type Settings, type User } from "@/lib/api";
import { useConfirm } from "@/lib/confirm";
import { useMe } from "@/lib/use-me";

const CHANNELS = ["slack", "teams", "web", "signal", "mail"];
const ADDRESS_HINT: Record<string, string> = {
  slack: "Slack member id, e.g. U0123ABCDEF",
  teams: "Microsoft Entra object id (Entra admin center → Users → the user), e.g. 1b2c3d4e-…",
  web: "the address they sign in to the console with (login proxy, or name for the console's own login)",
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
  const groupName = (id: string) => data.groups.find((g) => g.id === id)?.name ?? id;
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
      <ListView
        items={data.users}
        keyOf={(u) => u.id}
        text={(u) => `${u.name} ${u.aliases.join(" ")} ${u.accounts.map((a) => a.address).join(" ")}`}
        facets={[
          { label: "roles", value: (u) => (u.role_ids.length ? u.role_ids.map(roleName) : "no role") },
          { label: "groups", value: (u) => ((u.group_ids ?? []).length ? (u.group_ids ?? []).map(groupName) : "no group") },
          { label: "channels", value: (u) => u.accounts.map((a) => a.channel) },
        ]}
        empty="No users yet."
      >
        {(u) => (
        <Card className="p-4">
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
                {(u.group_ids ?? []).map((g) => (
                  <Badge key={g} variant="secondary">
                    <Users /> {groupName(g)}
                  </Badge>
                ))}
                {u.role_ids.length === 0 && !(u.group_ids ?? []).length ? <span className="text-xs text-muted-foreground">no role: cannot chat</span> : null}
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
        )}
      </ListView>
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent side="right" className="gap-0 p-0 sm:max-w-xl">
          {editing !== null ? <UserForm user={editing === "new" ? null : editing} roles={data.roles} groups={data.groups} onDone={() => setEditing(null)} /> : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function UserForm({ user: u, roles, groups, onDone }: { user: User | null; roles: RoleDoc[]; groups: GroupDoc[]; onDone: () => void }) {
  const refresh = useRefresh();
  const confirm = useConfirm();
  const { data: me } = useMe();
  const [name, setName] = useState(u?.name ?? "");
  const [aliases, setAliases] = useState((u?.aliases ?? []).join(", "));
  const [accounts, setAccounts] = useState<ChannelAccount[]>(u?.accounts ?? [{ channel: "web", address: "" }]);
  const [roleIds, setRoleIds] = useState(new Set(u?.role_ids ?? ["member"]));
  const [groupIds, setGroupIds] = useState(new Set(u?.group_ids ?? []));
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
        group_ids: [...groupIds],
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
        {groups.length ? (
          <div>
            <div className="mb-1 text-sm font-medium">Groups</div>
            {groups.map((g) => (
              <CheckRow
                key={g.id}
                label={g.name}
                hint={g.role_ids.length ? `gives ${g.role_ids.map((r) => roles.find((x) => x.id === r)?.name ?? r).join(", ")}` : "gives no role"}
                checked={groupIds.has(g.id)}
                onChange={(on) => {
                  const next = new Set(groupIds);
                  if (on) next.add(g.id);
                  else next.delete(g.id);
                  setGroupIds(next);
                }}
              />
            ))}
            <Hint>They have each group's roles on top of their own.</Hint>
          </div>
        ) : null}
        <Label>
          Notes
          <Textarea rows={3} className="font-sans" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Who they are, for the agents: relationship, language, …" />
        </Label>
        {u ? <PasswordSection user={u} isMe={isMe} /> : null}
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

/** The user's password for the console's own login (`web.auth.mode: password`). Never shown, only set or removed. */
function PasswordSection({ user, isMe }: { user: User; isMe: boolean }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { data } = useQuery({ queryKey: ["passwords"], queryFn: () => api<PasswordState>("GET", "/api/passwords") });
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const has = isMe ? data?.mine : data?.users?.includes(user.id);
  const path = `/api/passwords/${encodeURIComponent(user.id)}`;
  const run = async (action: () => Promise<unknown>, done: string) => {
    setBusy(true);
    try {
      await action();
      toast.success(done);
      setPassword("");
      void queryClient.invalidateQueries({ queryKey: ["passwords"] });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!(await confirm({ title: `Remove ${user.name}'s password?`, body: "With the password login, they can no longer sign in to the console.", action: "Remove", destructive: true })))
      return;
    await run(() => api("DELETE", path), "Password removed.");
  };
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium">
        <KeyRound className="size-4" /> Console password
        <Badge variant={has ? "secondary" : "outline"}>{has ? "set" : "none"}</Badge>
      </div>
      {isMe && has ? (
        <Hint>Change your own under your name at the bottom of the menu: that asks for the current one.</Hint>
      ) : (
        <div className="flex gap-2">
          <Input type="password" autoComplete="new-password" className="min-w-0 flex-1" placeholder={has ? "new password" : "at least 8 characters"} value={password} onChange={(e) => setPassword(e.target.value)} />
          <Button
            type="button"
            variant="outline"
            disabled={busy || password.length < 8}
            onClick={() => void run(() => api("PUT", isMe ? "/api/me/password" : path, { password }), "Password set. Their other browsers are signed out.")}
          >
            Set
          </Button>
          {has && !isMe ? (
            <Button type="button" variant="ghost" className="text-destructive" disabled={busy} onClick={() => void remove()}>
              Remove
            </Button>
          ) : null}
        </div>
      )}
      <Hint>For signing in when the console uses its own name-and-password login (Settings → Login). Needs a web account above.</Hint>
    </div>
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
      <ListView
        items={data.roles}
        keyOf={(r) => r.id}
        text={(r) => `${r.name} ${r.id}`}
        facets={[{ label: "rights", value: (r) => r.permissions }]}
        empty="No roles yet."
      >
        {(r) => {
        const holders = [
          ...data.users.filter((u) => u.role_ids.includes(r.id)).map((u) => u.name),
          ...data.groups.filter((g) => g.role_ids.includes(r.id)).map((g) => `group ${g.name}`),
        ];
        return (
          <Card className="p-4">
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
        }}
      </ListView>
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
  const holders = r
    ? [...data.users.filter((u) => u.role_ids.includes(r.id)), ...data.groups.filter((g) => g.role_ids.includes(r.id)).map((g) => ({ name: `group ${g.name}` }))]
    : [];
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

export function GroupsPanel({ data }: { data: Settings }) {
  const [editing, setEditing] = useState<GroupDoc | "new" | null>(null);
  const roleName = (id: string) => data.roles.find((r) => r.id === id)?.name ?? id;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start gap-3">
        <p className="min-w-0 flex-1 text-sm text-muted-foreground">
          People who share roles: every member has the group's roles on top of their own. In the configuration repository, like roles; who is in a group is
          kept with each user.
        </p>
        <Button onClick={() => setEditing("new")}>
          <Plus /> New group
        </Button>
      </div>
      <ListView
        items={data.groups}
        keyOf={(g) => g.id}
        text={(g) => `${g.name} ${g.id} ${g.description}`}
        facets={[{ label: "roles", value: (g) => (g.role_ids.length ? g.role_ids.map(roleName) : "no role") }]}
        empty="No groups yet."
      >
        {(g) => {
          const members = data.users.filter((u) => (u.group_ids ?? []).includes(g.id)).map((u) => u.name);
          return (
            <Card className="p-4">
              <div className="flex items-start gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <Users className="size-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{g.name}</span>
                    <code className="text-xs text-muted-foreground">{g.id}</code>
                    {g.role_ids.map((r) => (
                      <Badge key={r} variant="outline">
                        {roleName(r)}
                      </Badge>
                    ))}
                  </div>
                  {g.description ? <p className="text-xs text-muted-foreground">{g.description}</p> : null}
                  <p className="mt-1 text-xs text-muted-foreground">{members.length ? `Members: ${members.join(", ")}` : "No members"}</p>
                </div>
                <Button size="sm" variant="outline" onClick={() => setEditing(g)}>
                  <Pencil /> Edit
                </Button>
              </div>
            </Card>
          );
        }}
      </ListView>
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent side="right" className="gap-0 p-0 sm:max-w-xl">
          {editing !== null ? <GroupForm group={editing === "new" ? null : editing} data={data} onDone={() => setEditing(null)} /> : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function GroupForm({ group: g, data, onDone }: { group: GroupDoc | null; data: Settings; onDone: () => void }) {
  const refresh = useRefresh();
  const confirm = useConfirm();
  const [name, setName] = useState(g?.name ?? "");
  const [description, setDescription] = useState(g?.description ?? "");
  const [roleIds, setRoleIds] = useState(new Set(g?.role_ids ?? []));
  const before = new Set(g ? data.users.filter((u) => (u.group_ids ?? []).includes(g.id)).map((u) => u.id) : []);
  const [members, setMembers] = useState(new Set(before));
  const [busy, setBusy] = useState(false);
  const toggle = (set: Set<string>, id: string, on: boolean) => {
    const next = new Set(set);
    if (on) next.add(id);
    else next.delete(id);
    return next;
  };
  const save = async () => {
    setBusy(true);
    try {
      const body = { id: g?.id ?? "new", name: name.trim(), description: description.trim(), role_ids: [...roleIds] };
      let id = g?.id;
      if (g) await send("PUT", `/api/settings/groups/${encodeURIComponent(g.id)}`, body);
      else id = (await send("POST", "/api/settings/groups", body) as GroupDoc).id;
      // Membership is kept on each user: save those whose membership changed.
      for (const u of data.users) {
        const was = before.has(u.id);
        const is = members.has(u.id);
        if (was === is || !id) continue;
        const groupIds = is ? [...(u.group_ids ?? []), id] : (u.group_ids ?? []).filter((x) => x !== id);
        await send("PUT", `/api/settings/users/${encodeURIComponent(u.id)}`, { ...u, group_ids: groupIds });
      }
      toast.success("Saved.");
      refresh();
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
      refresh();
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!g) return;
    if (!(await confirm({ title: `Delete the group ${g.name}?`, action: "Delete", destructive: true }))) return;
    try {
      await api("DELETE", `/api/settings/groups/${encodeURIComponent(g.id)}`);
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
        <SheetTitle>{g ? g.name : "New group"}</SheetTitle>
        <SheetDescription>{g ? `id ${g.id} · applies at once` : "Applies at once."}</SheetDescription>
      </SheetHeader>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <Label>
          Name
          <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Family" />
          {g ? null : <Hint>The id is made from the name and cannot change later.</Hint>}
        </Label>
        <Label>
          Description
          <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Who is in it, and why" />
        </Label>
        <div>
          <div className="mb-1 text-sm font-medium">Roles</div>
          {data.roles.map((r) => (
            <CheckRow key={r.id} label={r.name} hint={r.permissions.join(", ") || "no rights"} checked={roleIds.has(r.id)} onChange={(on) => setRoleIds(toggle(roleIds, r.id, on))} />
          ))}
          <Hint>Every member has these on top of their own roles.</Hint>
        </div>
        <div>
          <div className="mb-1 text-sm font-medium">Members</div>
          {data.users.map((u) => (
            <CheckRow key={u.id} label={u.name} checked={members.has(u.id)} onChange={(on) => setMembers(toggle(members, u.id, on))} />
          ))}
        </div>
      </div>
      <div className="flex gap-2 border-t p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        <Button type="submit" disabled={busy || !name.trim()} className="flex-1 sm:flex-none">
          {g ? "Save" : "Create"}
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <span className="flex-1" />
        {g ? (
          <Button type="button" variant="ghost" className="text-destructive" onClick={remove} disabled={before.size > 0} title={before.size ? "Take the members out first" : undefined}>
            <Trash2 /> Delete
          </Button>
        ) : null}
      </div>
    </form>
  );
}
