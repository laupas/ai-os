import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** The scrolling body of every page except chat, which manages its own height. */
export function Page({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className="h-full overflow-y-auto">
      <div className={cn("mx-auto w-full max-w-5xl space-y-4 p-4 pb-[calc(env(safe-area-inset-bottom)+1.5rem)] md:p-8", className)}>
        {children}
      </div>
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start gap-3">
      <div className="min-w-0 flex-1">
        <h1 className="text-xl font-semibold tracking-tight md:text-2xl">{title}</h1>
        {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">{children}</div>;
}

export function Loading() {
  return (
    <div className="space-y-3 p-4 md:p-8">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-20 animate-pulse rounded-xl bg-muted" />
      ))}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div className="m-4 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive md:m-8">
      {error instanceof Error ? error.message : String(error)}
    </div>
  );
}
