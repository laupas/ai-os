import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, LogOut, Monitor, Moon, Palette, Sun } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Hint, Input, Label } from "@/components/ui/input";
import { SessionsList } from "@/components/sessions-list";
import { api, type Me, type PasswordState } from "@/lib/api";
import { useTheme, type Theme } from "@/lib/theme";
import { href } from "@/lib/router";
import { useLogin } from "@/lib/use-login";
import { cn } from "@/lib/utils";

/** Who is signed in; with the console's own login, also signing out and (password) changing one's password. */
export function AccountBox({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const { data: login } = useLogin();
  const [changing, setChanging] = useState(false);
  const [browsers, setBrowsers] = useState(false);
  const signOut = async () => {
    await api("POST", "/api/logout");
    await queryClient.resetQueries();
  };
  return (
    <div className="space-y-2">
      <div>
        <div className="font-medium text-foreground">{me.name}</div>
        <div className="truncate">{me.email}</div>
      </div>
      <div className="flex items-center gap-1">
        <div className="flex-1">
          <ThemeSwitch />
        </div>
        <Button size="icon-sm" variant="ghost" asChild>
          <a href={href("appearance")} aria-label="Appearance" title="Appearance: mode and colour theme">
            <Palette />
          </a>
        </Button>
      </div>
      {login?.mode ? (
        <div className="flex flex-wrap gap-1">
          {login.mode === "password" ? (
            <Button size="sm" variant="ghost" onClick={() => setChanging(true)}>
              <KeyRound /> Password
            </Button>
          ) : null}
          <Button size="sm" variant="ghost" onClick={() => setBrowsers(true)}>
            <Monitor /> Browsers
          </Button>
          <Button size="sm" variant="ghost" onClick={() => void signOut()}>
            <LogOut /> Sign out
          </Button>
        </div>
      ) : null}
      <Dialog open={browsers} onOpenChange={setBrowsers}>
        <DialogContent>
          <DialogTitle>Where you are signed in</DialogTitle>
          <DialogDescription>Sign out a browser you no longer use, or all but this one.</DialogDescription>
          {browsers ? <SessionsList /> : null}
        </DialogContent>
      </Dialog>
      <Dialog open={changing} onOpenChange={setChanging}>
        <DialogContent>{changing ? <OwnPasswordForm onDone={() => setChanging(false)} /> : null}</DialogContent>
      </Dialog>
    </div>
  );
}

const THEMES: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "system", label: "Like the device", icon: Monitor },
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
];

/** Light, dark or like the device, for this browser. */
function ThemeSwitch() {
  const [theme, setTheme] = useTheme();
  return (
    <div role="radiogroup" aria-label="Appearance" className="flex gap-0.5 rounded-lg bg-muted p-0.5">
      {THEMES.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          role="radio"
          aria-checked={theme === value}
          aria-label={label}
          title={label}
          onClick={() => setTheme(value)}
          className={cn(
            "flex h-7 flex-1 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground pointer-coarse:h-10",
            theme === value && "bg-background text-foreground shadow-xs",
          )}
        >
          <Icon className="size-3.5" />
        </button>
      ))}
    </div>
  );
}

function OwnPasswordForm({ onDone }: { onDone: () => void }) {
  const { data } = useQuery({ queryKey: ["passwords"], queryFn: () => api<PasswordState>("GET", "/api/passwords") });
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await api("PUT", "/api/me/password", { password, current: current || null });
      toast.success("Password changed. Other browsers are signed out.");
      onDone();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <DialogTitle>Change your password</DialogTitle>
      <DialogDescription>For signing in to this console. At least 8 characters.</DialogDescription>
      {data?.mine ? (
        <Label>
          Current password
          <Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </Label>
      ) : null}
      <Label>
        New password
        <Input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
      </Label>
      <Label>
        Again
        <Input type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
        {again && again !== password ? <Hint className="text-destructive">Not the same.</Hint> : null}
      </Label>
      <Button type="submit" disabled={busy || password.length < 8 || password !== again}>
        {busy ? <Loader2 className="animate-spin" /> : null} Change
      </Button>
    </form>
  );
}
