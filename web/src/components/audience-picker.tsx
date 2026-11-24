import { useState } from "react";
import { CheckRow } from "@/components/ui/checkbox";
import { Hint } from "@/components/ui/input";
import type { AudienceGroup } from "@/lib/api";

/** Which groups an agent or connector is available to: administrators only (null), everyone, or chosen groups.
 * Administrators always are; the server enforces it on every turn and tool call. `groups` are the ones the
 * caller may choose (the server says which, and checks it again on save). */
export function AudiencePicker({
  value,
  onChange,
  what,
  groups: offered,
}: {
  value: string[] | null;
  onChange: (v: string[] | null) => void;
  what: string;
  groups: AudienceGroup[];
}) {
  const everyone = value?.includes("everyone") ?? false;
  // An empty choice means administrators only too, but stays on "chosen" while picking.
  const [picking, setPicking] = useState(Boolean(value?.length) && !everyone);
  const mode = everyone ? "everyone" : picking ? "chosen" : "admins";
  const chosen = new Set(value ?? []);
  const toggle = (entry: string, on: boolean) => {
    const next = new Set(chosen);
    next.delete("everyone");
    if (on) next.add(entry);
    else next.delete(entry);
    onChange([...next]);
  };
  const [search, setSearch] = useState("");
  const wanted = search.trim().toLowerCase();
  const groups = offered.filter((g) => !wanted || `${g.name} ${g.id}`.toLowerCase().includes(wanted));
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="radio"
            checked={mode === "admins"}
            onChange={() => {
              setPicking(false);
              onChange(null);
            }}
          />{" "}
          Administrators only
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            checked={mode === "everyone"}
            onChange={() => {
              setPicking(false);
              onChange(["everyone"]);
            }}
          />{" "}
          Everyone
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            checked={mode === "chosen"}
            onChange={() => {
              setPicking(true);
              onChange([]);
            }}
          />{" "}
          Chosen groups
        </label>
      </div>
      {mode === "chosen" ? (
        <div className="space-y-2">
          {offered.length > 8 ? <input className="w-full rounded-md border bg-transparent px-2 py-1 text-sm" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search groups" /> : null}
          <div className="grid gap-x-4 sm:grid-cols-2">
            {groups.map((g) => (
              <CheckRow key={g.id} label={g.name} hint={g.description || undefined} checked={chosen.has(`group:${g.id}`)} onChange={(on) => toggle(`group:${g.id}`, on)} />
            ))}
          </div>
          {offered.length === 0 ? <p className="text-xs text-muted-foreground">No groups to choose: make them under Settings, Groups.</p> : null}
        </div>
      ) : null}
      <Hint>
        Whoever is not included does not see {what} at all, in chat or in a trigger. Administrators always do. No group chosen means administrators only.
      </Hint>
    </div>
  );
}
