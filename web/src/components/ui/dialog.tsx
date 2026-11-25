import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;

/** A sheet from the bottom on a phone, in reach of the thumb; centred from 640px.
 * On a phone it sits above the on-screen keyboard (`--keyboard`, see main.tsx). */
export function DialogContent({ className, children, ...props }: React.ComponentProps<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
      <DialogPrimitive.Content
        className={cn(
          "fixed inset-x-0 bottom-[var(--keyboard,0px)] z-50 mx-auto grid max-h-[85dvh] max-w-md gap-4 overflow-y-auto rounded-t-2xl border-t bg-background p-5 pb-[calc(env(safe-area-inset-bottom)+1.25rem)] shadow-lg outline-none",
          "sm:top-1/2 sm:right-auto sm:bottom-auto sm:left-1/2 sm:mx-0 sm:w-[calc(100%-2rem)] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-xl sm:border sm:pb-5",
          className,
        )}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export const DialogTitle = ({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Title>) => (
  <DialogPrimitive.Title className={cn("text-lg font-semibold", className)} {...props} />
);
export const DialogDescription = ({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Description>) => (
  <DialogPrimitive.Description className={cn("text-sm text-muted-foreground", className)} {...props} />
);
