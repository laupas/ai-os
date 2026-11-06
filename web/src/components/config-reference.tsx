import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Schema = Record<string, any>;

interface Key {
  path: string[];
  type: string;
  default: unknown;
  description?: string;
}

function resolve(schema: Schema, defs: Schema): Schema {
  if (schema.$ref) return resolve({ ...defs[String(schema.$ref).split("/").pop()!], ...schema, $ref: undefined }, defs);
  if (schema.anyOf) {
    const rest = (schema.anyOf as Schema[]).filter((s) => s.type !== "null");
    if (rest.length === 1) return { ...resolve(rest[0], defs), default: schema.default, description: schema.description ?? rest[0].description };
  }
  return schema;
}

function typeOf(s: Schema): string {
  if (s.enum) return (s.enum as string[]).join(" | ");
  if (s.type === "array") return `list of ${s.items?.type ?? "items"}`;
  if (s.type === "object") return "map";
  return String(s.type ?? "value");
}

/** Every key of aios.yaml, from the model ai-os reads it with: a leaf per setting,
 * sections walked into. Ones it only reads once, or reads for older files, are left
 * out by name. */
function keysOf(schema: Schema, defs: Schema, path: string[] = []): Key[] {
  const keys: Key[] = [];
  for (const [name, raw] of Object.entries<Schema>(schema.properties ?? {})) {
    if (HIDDEN.includes([...path, name].join("."))) continue;
    const s = resolve(raw, defs);
    if (s.type === "object" && s.properties) keys.push(...keysOf(s, defs, [...path, name]));
    else keys.push({ path: [...path, name], type: typeOf(s), default: s.default, description: s.description });
  }
  return keys;
}

// mcp_servers is read on the first start only; the access_* and dev_email keys are
// older forms of web.auth, still read, not to be taken up anew.
const HIDDEN = ["mcp_servers", "web.access_team_domain", "web.access_aud", "web.dev_email"];

const shown = (v: unknown) => (v === undefined ? "" : JSON.stringify(v));
const doc = (text?: string) => text?.replace(/\s*\n\s*/g, " ");

/** The keys aios.yaml can have, next to its editor: what each is, its default, and
 * a button that writes it in with that default for you to change. */
export function ConfigReference({ schema, onInsert }: { schema: Schema; onInsert: (path: string[], value: unknown) => void }) {
  const [filter, setFilter] = useState("");
  const needle = filter.trim().toLowerCase();
  const keys = keysOf(schema, schema.$defs ?? {}).filter(
    (k) => !needle || k.path.join(".").toLowerCase().includes(needle) || k.description?.toLowerCase().includes(needle),
  );
  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input className="pl-9" placeholder="Find a key" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </div>
      <div className="divide-y rounded-xl border">
        {keys.map((k) => (
          <div key={k.path.join(".")} className="space-y-1 p-3">
            <div className="flex items-start gap-2">
              <code className="min-w-0 flex-1 text-xs font-medium break-all">{k.path.join(".")}</code>
              <Button size="sm" variant="ghost" className="h-6 px-2 text-xs" onClick={() => onInsert(k.path, k.default ?? null)} title="Write it into aios.yaml with its default">
                <Plus className="size-3" /> insert
              </Button>
            </div>
            <div className="text-xs text-muted-foreground">
              {k.type}
              {k.default !== undefined ? (
                <>
                  {" · default "}
                  <code className="break-all">{shown(k.default)}</code>
                </>
              ) : null}
            </div>
            {k.description ? <p className="text-xs text-muted-foreground">{doc(k.description)}</p> : null}
          </div>
        ))}
      </div>
    </div>
  );
}
