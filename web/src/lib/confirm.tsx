import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { setLeaveQuestion } from "@/lib/router";

interface Ask {
  title: string;
  body?: string;
  action?: string;
  destructive?: boolean;
}

const ConfirmContext = createContext<(ask: Ask) => Promise<boolean>>(async () => false);

/** `const confirm = useConfirm(); if (await confirm({...}))` — a dialog instead of window.confirm. */
export const useConfirm = () => useContext(ConfirmContext);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [ask, setAsk] = useState<Ask | null>(null);
  const resolver = useRef<(value: boolean) => void>(() => {});
  const confirm = useCallback((next: Ask) => {
    setAsk(next);
    return new Promise<boolean>((resolve) => (resolver.current = resolve));
  }, []);
  // Leaving a page with unsaved changes asks here too, not with the browser's own box.
  useEffect(
    () =>
      setLeaveQuestion(() =>
        confirm({ title: "Discard your changes?", body: "They are not saved yet.", action: "Discard", destructive: true }),
      ),
    [confirm],
  );
  const settle = (value: boolean) => {
    resolver.current(value);
    setAsk(null);
  };
  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Dialog open={ask !== null} onOpenChange={(open) => !open && settle(false)}>
        <DialogContent>
          <DialogTitle>{ask?.title}</DialogTitle>
          {ask?.body ? <DialogDescription>{ask.body}</DialogDescription> : null}
          {/* On a phone the dialog is a sheet at the bottom: full-width buttons, the action nearest the thumb. */}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="outline" onClick={() => settle(false)}>
              Cancel
            </Button>
            <Button variant={ask?.destructive ? "destructive" : "default"} onClick={() => settle(true)}>
              {ask?.action ?? "OK"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </ConfirmContext.Provider>
  );
}
