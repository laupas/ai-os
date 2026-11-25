import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { useUnsaved } from "@/lib/router";

/** The foot of an editing page, pinned to the bottom of the screen however long the
 * form: Save stays in reach, it says when something is not saved yet, and leaving
 * the page with changes asks first. Goes last inside a `Page`. */
export function SaveBar({
  dirty,
  busy,
  label = "Save",
  onSave,
  onDiscard,
  note,
  children,
}: {
  dirty: boolean;
  busy?: boolean;
  label?: string;
  /** Without it the button submits the form the bar is in. */
  onSave?: () => void;
  onDiscard?: () => void;
  /** Shown while there is nothing to save, e.g. when a change applies. */
  note?: ReactNode;
  /** More actions, before the status: Delete, History. */
  children?: ReactNode;
}) {
  useUnsaved(dirty);
  return (
    // The negative margins reach the edges and the bottom of the Page's padding.
    <div className="sticky bottom-0 z-10 -mx-4 -mb-[calc(var(--safe-bottom)+1.5rem)] flex flex-wrap items-center gap-2 border-t bg-background/95 px-4 pt-3 pb-[calc(var(--safe-bottom)+0.75rem)] backdrop-blur md:-mx-8 md:-mb-8 md:px-8">
      {children}
      <span className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
        {dirty ? (
          <>
            <span className="size-2 rounded-full bg-warning" /> Unsaved changes
          </>
        ) : (
          note
        )}
      </span>
      {dirty && onDiscard ? (
        <Button type="button" variant="ghost" onClick={onDiscard}>
          Discard
        </Button>
      ) : null}
      <Button type={onSave ? "button" : "submit"} onClick={onSave} disabled={!dirty || busy}>
        {busy ? <Loader2 className="animate-spin" /> : null} {label}
      </Button>
    </div>
  );
}
