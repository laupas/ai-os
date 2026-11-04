import { ArrowUp, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

const coarse = () => window.matchMedia("(pointer: coarse)").matches;

/** Grows with its text. Enter sends on a keyboard; on a touch screen Enter is a new line
 * and the button sends, since a phone keyboard has no Shift+Enter. */
export function Composer({
  onSend,
  onStop,
  busy,
  autoFocus,
  placeholder = "Message ai-os…",
  toolbar,
}: {
  onSend: (text: string) => void;
  onStop?: () => void;
  busy?: boolean;
  autoFocus?: boolean;
  placeholder?: string;
  /** Shown inside the box above the text, e.g. who the message goes to. */
  toolbar?: React.ReactNode;
}) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);
  useEffect(() => {
    if (autoFocus && !coarse()) ref.current?.focus();
  }, [autoFocus]);
  const send = () => {
    const value = text.trim();
    if (!value) return;
    setText("");
    onSend(value);
  };
  return (
    <div className="shrink-0 border-t bg-background/95 px-3 pt-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] backdrop-blur md:px-6">
      <div className="mx-auto max-w-3xl rounded-2xl border bg-card p-2 shadow-sm focus-within:ring-[3px] focus-within:ring-ring/30">
        {toolbar ? <div className="flex items-center gap-2 px-1 pb-1">{toolbar}</div> : null}
        <div className="flex items-end gap-2">
        <textarea
          ref={ref}
          rows={1}
          value={text}
          placeholder={placeholder}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !coarse()) {
              event.preventDefault();
              send();
            }
          }}
          className="max-h-[200px] min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 outline-none placeholder:text-muted-foreground"
        />
        {busy && onStop ? (
          <Button size="icon" variant="outline" className="rounded-full" onClick={onStop} aria-label="Stop">
            <Square className="size-3.5" />
          </Button>
        ) : null}
        <Button size="icon" className="rounded-full" onClick={send} disabled={!text.trim()} aria-label="Send">
          <ArrowUp />
        </Button>
        </div>
      </div>
    </div>
  );
}
