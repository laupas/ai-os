import { Check, Monitor, Moon, Sun } from "lucide-react";
import { Page, PageHeader } from "@/components/page";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { THEMES, useAccent, useTheme, type Theme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const MODES: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "system", label: "Like the device", icon: Monitor },
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
];

/** How the console looks: light or dark, and the colour theme. Open to everyone,
 * kept with their account (see lib/theme.ts). */
export function AppearancePage() {
  const [mode, setMode] = useTheme();
  const [accent, setAccent] = useAccent();
  return (
    <Page className="max-w-3xl">
      <PageHeader title="Appearance" description="Kept with your account: the same in every browser you sign in from." />
      <Card>
        <CardHeader>
          <CardTitle>Mode</CardTitle>
        </CardHeader>
        <CardContent>
          <div role="radiogroup" aria-label="Mode" className="grid grid-cols-3 gap-2">
            {MODES.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                role="radio"
                aria-checked={mode === value}
                onClick={() => setMode(value)}
                className={cn(
                  "flex min-h-20 flex-col items-center justify-center gap-2 rounded-xl border p-3 text-center text-sm font-medium transition-colors hover:bg-accent/50",
                  mode === value && "border-primary bg-primary/5 text-primary ring-2 ring-primary/30",
                )}
              >
                <Icon className="size-5" />
                {label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Colour</CardTitle>
          <CardDescription>The accent of buttons, switches and the page you are on. Everything else stays neutral.</CardDescription>
        </CardHeader>
        <CardContent>
          <div role="radiogroup" aria-label="Colour" className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {THEMES.map(({ id, label }) => (
              // The theme's own class: inside this button, the colours are that theme's.
              <button
                key={id}
                role="radio"
                aria-checked={accent === id}
                onClick={() => setAccent(id)}
                className={cn(
                  `theme-${id}`,
                  "rounded-xl border p-2 text-left transition-colors hover:bg-accent/40",
                  accent === id && "border-primary ring-2 ring-primary/40",
                )}
              >
                <Preview />
                <span className="flex items-center gap-2 px-1 pt-2 pb-0.5 text-sm font-medium">
                  <span className="size-3 rounded-full bg-primary" />
                  <span className="flex-1">{label}</span>
                  {accent === id ? <Check className="size-4 text-primary" /> : null}
                </span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    </Page>
  );
}

/** A tiny console: the sidebar with the current page, a message, a switch and a button. */
function Preview() {
  return (
    <span aria-hidden="true" className="flex h-20 overflow-hidden rounded-lg border bg-background">
      <span className="flex w-9 flex-col gap-1 border-r bg-muted/50 p-1.5">
        <span className="h-1.5 rounded-full bg-primary/25" />
        <span className="h-1.5 rounded-full bg-muted-foreground/20" />
        <span className="h-1.5 rounded-full bg-muted-foreground/20" />
        <span className="h-1.5 rounded-full bg-muted-foreground/20" />
      </span>
      <span className="flex flex-1 flex-col justify-between p-2">
        <span className="ml-auto h-2.5 w-14 rounded-full bg-bubble" />
        <span className="h-1.5 w-16 rounded-full bg-muted-foreground/25" />
        <span className="flex items-center justify-end gap-1.5">
          <span className="flex h-3 w-5 items-center justify-end rounded-full bg-primary px-0.5">
            <span className="size-2 rounded-full bg-primary-foreground" />
          </span>
          <span className="rounded-md bg-primary px-1.5 text-[9px] leading-4 font-medium text-primary-foreground">Save</span>
        </span>
      </span>
    </span>
  );
}
