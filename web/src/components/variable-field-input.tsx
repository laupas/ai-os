import { Badge } from "@/components/ui/badge";
import { Hint, Input, Label } from "@/components/ui/input";
import type { VariableFieldRow } from "@/lib/api";

const SOURCE: Record<string, string> = {
  variable: "set",
  environment: "from the environment",
  default: "default",
};

/** One value a channel or a code connector needs: where it comes from now, and a
 * field to type a new one. A secret one is never shown; empty keeps what is set. */
export function VariableFieldInput({ field: f, value, onChange }: { field: VariableFieldRow; value: string; onChange: (v: string) => void }) {
  const placeholder =
    f.secret && f.source === "variable"
      ? "Set. Leave empty to keep it; type to replace it."
      : f.source === "environment"
        ? f.secret
          ? "Taken from the environment. Type to set it here instead."
          : (f.value ?? "")
        : f.source === "default"
          ? (f.value ?? f.placeholder)
          : f.placeholder;
  return (
    <Label>
      <span className="flex items-center gap-2">
        {f.label}
        <code className="text-xs font-normal text-muted-foreground">{f.variable}</code>
        {f.source ? (
          <Badge variant={f.source === "environment" ? "warning" : f.source === "variable" ? "success" : "secondary"}>{SOURCE[f.source]}</Badge>
        ) : f.required ? (
          <Badge variant="destructive">not set</Badge>
        ) : null}
      </span>
      <Input
        type={f.secret ? "password" : "text"}
        autoComplete="off"
        spellCheck={false}
        className="font-mono"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      {f.hint ? <Hint>{f.hint}</Hint> : null}
    </Label>
  );
}
