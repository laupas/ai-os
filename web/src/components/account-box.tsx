import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, LogOut } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Hint, Input, Label } from "@/components/ui/input";
import { api, type Me, type PasswordState } from "@/lib/api";
import { useLogin } from "@/lib/use-login";

/** Who is signed in; with the console's own login, also signing out and (password) changing one's password. */
export function AccountBox({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const { data: login } = useLogin();
  const [changing, setChanging] = useState(false);
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
      {login?.mode ? (
        <div className="flex flex-wrap gap-1">
          {login.mode === "password" ? (
            <Button size="sm" variant="ghost" onClick={() => setChanging(true)}>
              <KeyRound /> Password
            </Button>
          ) : null}
          <Button size="sm" variant="ghost" onClick={() => void signOut()}>
            <LogOut /> Sign out
          </Button>
        </div>
      ) : null}
      <Dialog open={changing} onOpenChange={setChanging}>
        <DialogContent>{changing ? <OwnPasswordForm onDone={() => setChanging(false)} /> : null}</DialogContent>
      </Dialog>
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
