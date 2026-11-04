import { CheckCircle2, Loader2, ShieldQuestion, Square, Wrench } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, type Message } from "@/lib/api";
import { cn, when } from "@/lib/utils";
import { Markdown } from "./markdown";

export function MessageView({ message }: { message: Message }) {
  if (message.role === "activity") return <ActivityCard steps={message.text.split("\n")} running={false} />;
  if (message.role === "user") {
    return (
      <div className="flex flex-col items-end gap-1">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-bubble px-4 py-2.5 text-bubble-foreground md:max-w-[70%]">
          <Markdown text={message.text} />
        </div>
        <span className="px-1 text-[11px] text-muted-foreground">
          {message.author ? `${message.author} · ` : ""}
          {message.channel ? `${message.channel} · ` : ""}
          {when(message.created_at)}
        </span>
      </div>
    );
  }
  if (message.role === "tool") {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
        <Wrench className="mt-0.5 size-3.5 shrink-0" />
        <span className="min-w-0 break-words">{message.text}</span>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <div className="max-w-full md:max-w-[85%]">
        <Markdown text={message.text} />
      </div>
      {message.created_at ? <span className="text-[11px] text-muted-foreground">{when(message.created_at)}</span> : null}
    </div>
  );
}

export function StreamingView({ text }: { text: string }) {
  return (
    <div className="max-w-full md:max-w-[85%]">
      <Markdown text={text} />
      <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-foreground/60 align-middle" />
    </div>
  );
}

/** The steps of one turn, like Slack's status message: live while it runs, then kept. */
export function ActivityCard({ steps, running, onStop }: { steps: string[]; running: boolean; onStop?: () => void }) {
  const [open, setOpen] = useState(running);
  const expanded = running || open;
  return (
    <div className={cn("w-fit max-w-full rounded-xl border text-sm", running ? "border-warning/60 bg-warning/5" : "bg-muted/40")}>
      <button className="flex w-full items-center gap-2 px-3 py-2 text-left" onClick={() => setOpen(!open)} disabled={running}>
        {running ? <Loader2 className="size-4 animate-spin" /> : <CheckCircle2 className="size-4 text-success" />}
        <span className="font-medium">{running ? "Working…" : "Done"}</span>
        <span className="text-xs text-muted-foreground">
          {steps.length} step{steps.length === 1 ? "" : "s"}
        </span>
      </button>
      {expanded ? (
        <ul className="space-y-1 px-3 pb-2.5 pl-9 text-muted-foreground">
          {steps.map((step, i) => (
            <li key={i} className="break-words">
              {step}
            </li>
          ))}
        </ul>
      ) : null}
      {running && onStop ? (
        <div className="px-3 pb-3">
          <Button size="sm" variant="outline" onClick={onStop}>
            <Square className="size-3" /> Stop
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function AskCard({ id, question, options, context }: { id: string; question: string; options: string[]; context?: React.ReactNode }) {
  const [answered, setAnswered] = useState<string | null>(null);
  const answer = async (option: string) => {
    try {
      await api("POST", `/api/approvals/${encodeURIComponent(id)}`, { answer: option });
      setAnswered(option);
    } catch (error) {
      toast.error((error as Error).message);
    }
  };
  return (
    <div className="rounded-xl border border-warning/60 bg-warning/5 p-3">
      <div className="mb-1 flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <ShieldQuestion className="size-4" /> ai-os asks {context}
      </div>
      <Markdown text={question} />
      <div className="mt-3 flex flex-wrap gap-2">
        {answered ? (
          <span className="text-sm text-muted-foreground">→ {answered}</span>
        ) : (
          options.map((option, i) => (
            <Button key={option} size="sm" variant={i === 0 ? "default" : "outline"} onClick={() => answer(option)}>
              {option}
            </Button>
          ))
        )}
      </div>
    </div>
  );
}
