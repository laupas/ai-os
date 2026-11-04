import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

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
          <div className="flex justify-end gap-2">
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
