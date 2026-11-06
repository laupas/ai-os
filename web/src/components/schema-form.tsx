import { Plus, RotateCcw, Trash2 } from "lucide-react";
import { Fragment, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";

// A form drawn from a pydantic model's JSON schema. It edits the values a file
// *sets*: an empty field is a key left out, so its default applies, and the
// default is shown as the placeholder. Unknown shapes are left to the YAML tab.

export type Schema = Record<string, any>;
export type Values = Record<string, unknown>;

interface Resolved {
  schema: Schema;
  nullable: boolean;
}

function resolve(schema: Schema, defs: Schema): Resolved {
  if (schema.$ref) {
    const target = defs[String(schema.$ref).split("/").pop()!];
    return resolve({ ...target, ...schema, $ref: undefined }, defs);
  }
  if (schema.anyOf) {
    const rest = (schema.anyOf as Schema[]).filter((s) => s.type !== "null");
    if (rest.length === 1) {
      const inner = resolve(rest[0], defs);
      return { schema: { ...inner.schema, default: schema.default, description: schema.description ?? inner.schema.description }, nullable: true };
    }
  }
  return { schema, nullable: false };
}

const isObject = (s: Schema) => s.type === "object" && s.properties;
const isDict = (s: Schema) => s.type === "object" && !s.properties && s.additionalProperties;
const isPlain = (v: unknown): v is Values => typeof v === "object" && v !== null && !Array.isArray(v);

const tidy = (lines: string[]) => {
  const kept = lines.map((l) => l.trim()).filter(Boolean);
  return kept.length ? kept : undefined;
};

/** What is saved: empty objects dropped, so clearing every field of a section
 * removes the section, and lists of text without their blank lines. */
export function prune(values: Values): Values {
  const out: Values = {};
  for (const [k, v] of Object.entries(values)) {
    const value = Array.isArray(v) && v.every((x) => typeof x === "string") ? tidy(v as string[]) : v;
    if (value === undefined) continue;
    if (isPlain(value)) {
      const inner = prune(value);
      if (Object.keys(inner).length) out[k] = inner;
    } else out[k] = value;
  }
  return out;
}

function set(values: Values, key: string, value: unknown): Values {
  const next = { ...values };
  if (value === undefined) delete next[key];
  else next[key] = value;
  return next;
}

/** `code` in a docstring, and its line breaks undone. */
function Doc({ text }: { text?: string }) {
  if (!text) return null;
  const parts = text.replace(/\s*\n\s*/g, " ").split(/`([^`]+)`/);
  return (
    <>
      {parts.map((p, i) =>
        i % 2 ? (
          <code key={i} className="rounded bg-muted px-1 text-[0.85em]">
            {p}
          </code>
        ) : (
          <Fragment key={i}>{p}</Fragment>
        ),
      )}
    </>
  );
}

const label = (key: string) => key.replace(/_/g, " ");
const shown = (v: unknown) => (v === undefined || v === null ? "" : typeof v === "object" ? JSON.stringify(v) : String(v));

/** The whole form: plain top-level settings in one card, each section in its own. */
export function SchemaForm({ schema, values, onChange, hidden = [] }: { schema: Schema; values: Values; onChange: (v: Values) => void; hidden?: string[] }) {
  const defs = schema.$defs ?? {};
  const keys = Object.keys(schema.properties ?? {}).filter((k) => !hidden.includes(k));
  const sectionKeys = keys.filter((k) => isObject(resolve(schema.properties[k], defs).schema));
  const plainKeys = keys.filter((k) => !sectionKeys.includes(k));
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>General</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {plainKeys.map((k) => (
            <Field key={k} name={k} schema={schema.properties[k]} defs={defs} values={values} onChange={onChange} />
          ))}
        </CardContent>
      </Card>
      {sectionKeys.map((k) => {
        const { schema: s, nullable } = resolve(schema.properties[k], defs);
        const value = values[k];
        return (
          <Card key={k}>
            <CardHeader className="flex-row items-start gap-3">
              <div className="min-w-0 flex-1 space-y-1.5">
                <CardTitle className="capitalize">{label(k)}</CardTitle>
                <CardDescription>
                  <Doc text={s.description} />
                </CardDescription>
              </div>
              {nullable && isPlain(value) ? (
                <Button size="sm" variant="ghost" className="text-destructive" onClick={() => onChange(set(values, k, undefined))}>
                  <Trash2 /> Remove
                </Button>
              ) : null}
            </CardHeader>
            <CardContent>
              {nullable && !isPlain(value) ? (
                <Button size="sm" variant="outline" onClick={() => onChange(set(values, k, {}))}>
                  <Plus /> Configure
                </Button>
              ) : (
                <ObjectFields schema={s} defs={defs} values={isPlain(value) ? value : {}} onChange={(v) => onChange(set(values, k, v))} />
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

/** A code connector's settings: the fields of its schema, with those aios.yaml
 * fixes shown with their value and not editable. */
export function SettingsFields({ schema, values, onChange, fixed = {} }: { schema: Schema; values: Values; onChange: (v: Values) => void; fixed?: Values }) {
  return <ObjectFields schema={schema} defs={schema.$defs ?? {}} values={values} onChange={onChange} fixed={fixed} />;
}

function ObjectFields({
  schema,
  defs,
  values,
  onChange,
  fixed = {},
}: {
  schema: Schema;
  defs: Schema;
  values: Values;
  onChange: (v: Values) => void;
  fixed?: Values;
}) {
  return (
    <div className="space-y-4">
      {Object.keys(schema.properties ?? {}).map((k) =>
        k in fixed ? (
          <FixedField key={k} name={k} schema={schema.properties[k]} value={fixed[k]} />
        ) : (
          <Field key={k} name={k} schema={schema.properties[k]} defs={defs} values={values} onChange={onChange} required={schema.required?.includes(k)} />
        ),
      )}
    </div>
  );
}

function FixedField({ name, schema, value }: { name: string; schema: Schema; value: unknown }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">{label(name)}</span>
        <span className="rounded-md bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">set in aios.yaml</span>
      </div>
      {schema.description ? (
        <p className="text-xs text-muted-foreground">
          <Doc text={schema.description} />
        </p>
      ) : null}
      <code className="block rounded-md border bg-muted/40 px-3 py-2 text-xs">{shown(value)}</code>
    </div>
  );
}

/** One key of an object: its label, its help, its control, and a way back to the default. */
function Field({
  name,
  schema: raw,
  defs,
  values,
  onChange,
  required,
}: {
  name: string;
  schema: Schema;
  defs: Schema;
  values: Values;
  onChange: (v: Values) => void;
  required?: boolean;
}) {
  const { schema, nullable } = resolve(raw, defs);
  const value = values[name];
  const update = (v: unknown) => onChange(set(values, name, v));
  const isSet = name in values;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">
          {label(name)}
          {required ? <span className="text-destructive"> *</span> : null}
        </span>
        {isSet && !required ? (
          <button type="button" className="text-muted-foreground hover:text-foreground" onClick={() => update(undefined)} title="Back to the default" aria-label={`Reset ${name}`}>
            <RotateCcw className="size-3.5" />
          </button>
        ) : null}
      </div>
      {schema.description ? (
        <p className="text-xs text-muted-foreground">
          <Doc text={schema.description} />
        </p>
      ) : null}
      <Control schema={schema} nullable={nullable} defs={defs} value={value} onChange={update} />
    </div>
  );
}

function Control({ schema, nullable, defs, value, onChange }: { schema: Schema; nullable: boolean; defs: Schema; value: unknown; onChange: (v: unknown) => void }): ReactNode {
  const fallback = schema.default;
  if (schema.enum) {
    return (
      <NativeSelect className="w-auto min-w-48" value={shown(value)} onChange={(e) => onChange(e.target.value || undefined)}>
        <option value="">default{fallback != null ? ` (${fallback})` : ""}</option>
        {(schema.enum as string[]).map((o) => (
          <option key={o}>{o}</option>
        ))}
      </NativeSelect>
    );
  }
  if (schema.type === "boolean") {
    return <Switch checked={Boolean(value ?? fallback)} onCheckedChange={onChange} />;
  }
  if (schema.type === "integer" || schema.type === "number") {
    return (
      <Input
        type="number"
        className="w-40"
        step={schema.type === "integer" ? 1 : "any"}
        placeholder={shown(fallback)}
        value={shown(value)}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
      />
    );
  }
  if (schema.type === "string") {
    return <Input placeholder={nullable && fallback == null ? "not set" : shown(fallback)} value={shown(value)} onChange={(e) => onChange(e.target.value || undefined)} />;
  }
  if (schema.type === "array") {
    const items = resolve(schema.items ?? {}, defs).schema;
    if (isObject(items)) return <ObjectList schema={items} defs={defs} value={Array.isArray(value) ? (value as Values[]) : []} onChange={onChange} />;
    return <Lines value={Array.isArray(value) ? (value as string[]) : undefined} fallback={fallback} onChange={onChange} />;
  }
  if (isDict(schema)) {
    const of = resolve(schema.additionalProperties, defs).schema;
    if (!isObject(of) && !isDict(of)) return <DictRows schema={of} value={isPlain(value) ? value : {}} fallback={fallback} onChange={onChange} />;
  }
  if (isObject(schema)) {
    if (nullable && !isPlain(value)) {
      return (
        <Button size="sm" variant="outline" onClick={() => onChange({})}>
          <Plus /> Configure
        </Button>
      );
    }
    return (
      <div className="space-y-3 rounded-lg border p-3">
        <ObjectFields schema={schema} defs={defs} values={isPlain(value) ? value : {}} onChange={onChange} />
        {nullable ? (
          <Button size="sm" variant="ghost" className="text-destructive" onClick={() => onChange(undefined)}>
            <Trash2 /> Remove
          </Button>
        ) : null}
      </div>
    );
  }
  return <p className="text-xs text-muted-foreground">Edit this one on the aios.yaml tab.</p>;
}

/** A list of strings, one per line. Empty means the default list. */
function Lines({ value, fallback, onChange }: { value: string[] | undefined; fallback: unknown; onChange: (v: unknown) => void }) {
  const placeholder = Array.isArray(fallback) && fallback.length ? fallback.join("\n") : "one per line";
  // Tall enough for the default list too, which is the placeholder while nothing is set.
  const lines = value?.length ? value.length + 1 : placeholder.split("\n").length;
  return (
    <Textarea
      rows={Math.min(12, Math.max(3, lines))}
      className="font-mono text-xs md:text-xs"
      placeholder={placeholder}
      value={value?.join("\n") ?? ""}
      // Kept as typed, blank lines and all, and tidied when the box is left (and by `prune`).
      onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value.split("\n"))}
      onBlur={() => value && onChange(tidy(value))}
    />
  );
}

/** A dict of plain values: one row per key. */
function DictRows({ schema, value, fallback, onChange }: { schema: Schema; value: Values; fallback: unknown; onChange: (v: unknown) => void }) {
  const entries = Object.entries(value);
  const write = (next: [string, unknown][]) => onChange(next.length ? Object.fromEntries(next) : undefined);
  return (
    <div className="space-y-2">
      {entries.length === 0 && isPlain(fallback) && Object.keys(fallback).length ? (
        <p className="text-xs text-muted-foreground">Default: {Object.entries(fallback).map(([k, v]) => `${k} = ${v}`).join(", ")}</p>
      ) : null}
      {entries.map(([k, v], i) => (
        <div key={i} className="flex gap-2">
          <Input className="w-48" placeholder="key" value={k} onChange={(e) => write(entries.map((x, j) => (j === i ? [e.target.value, x[1]] : x)))} />
          {schema.enum ? (
            <NativeSelect className="flex-1" value={shown(v)} onChange={(e) => write(entries.map((x, j) => (j === i ? [x[0], e.target.value] : x)))}>
              {(schema.enum as string[]).map((o) => (
                <option key={o}>{o}</option>
              ))}
            </NativeSelect>
          ) : (
            <Input
              className="flex-1"
              type={schema.type === "number" || schema.type === "integer" ? "number" : "text"}
              placeholder="value"
              value={shown(v)}
              onChange={(e) => write(entries.map((x, j) => (j === i ? [x[0], schema.type === "string" ? e.target.value : Number(e.target.value)] : x)))}
            />
          )}
          <Button size="icon" variant="ghost" onClick={() => write(entries.filter((_, j) => j !== i))} aria-label="Remove">
            <Trash2 />
          </Button>
        </div>
      ))}
      <Button size="sm" variant="outline" onClick={() => write([...entries, ["", schema.enum ? schema.enum[0] : ""]])}>
        <Plus /> Add
      </Button>
    </div>
  );
}

/** A list of objects, each its own small form. */
function ObjectList({ schema, defs, value, onChange }: { schema: Schema; defs: Schema; value: Values[]; onChange: (v: unknown) => void }) {
  const write = (next: Values[]) => onChange(next.length ? next : undefined);
  return (
    <div className="space-y-2">
      {value.map((item, i) => (
        <div key={i} className="flex items-start gap-2 rounded-lg border p-3">
          <div className="min-w-0 flex-1">
            <ObjectFields schema={schema} defs={defs} values={item} onChange={(v) => write(value.map((x, j) => (j === i ? v : x)))} />
          </div>
          <Button size="icon" variant="ghost" onClick={() => write(value.filter((_, j) => j !== i))} aria-label="Remove">
            <Trash2 />
          </Button>
        </div>
      ))}
      <Button size="sm" variant="outline" onClick={() => write([...value, {}])}>
        <Plus /> Add
      </Button>
    </div>
  );
}
