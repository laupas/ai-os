import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { ErrorBox, Page, PageHeader } from "@/components/page";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const tone = (line: string) =>
  / (ERROR|CRITICAL) /.test(line) ? "text-destructive" : / WARNING /.test(line) ? "text-warning" : "";

export function LogsPage() {
  const [level, setLevel] = useState("WARNING");
  const [hours, setHours] = useState("24");
  const [follow, setFollow] = useState(false);
  const { data, error, refetch, isFetching } = useQuery({
    queryKey: ["logs", level, hours],
    queryFn: () => api<{ lines: string[] }>("GET", `/api/logs?level=${level}&hours=${hours}`),
    refetchInterval: follow ? 5000 : false,
  });
  return (
    <Page className="max-w-6xl">
      <PageHeader
        title="Logs"
        actions={
          <>
            <NativeSelect className="w-32" value={level} onChange={(e) => setLevel(e.target.value)}>
              {["DEBUG", "INFO", "WARNING", "ERROR"].map((l) => (
                <option key={l}>{l}</option>
              ))}
            </NativeSelect>
            <NativeSelect className="w-32" value={hours} onChange={(e) => setHours(e.target.value)}>
              {[1, 6, 24, 72, 168].map((h) => (
                <option key={h} value={h}>
                  last {h} h
                </option>
              ))}
            </NativeSelect>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={follow} onCheckedChange={setFollow} /> follow
            </label>
            <Button variant="outline" size="icon" onClick={() => refetch()} aria-label="Reload">
              <RefreshCw className={cn(isFetching && "animate-spin")} />
            </Button>
          </>
        }
      />
      {error ? <ErrorBox error={error} /> : null}
      <pre className="overflow-x-auto rounded-xl border bg-muted/40 p-3 font-mono text-[11px] leading-relaxed md:text-xs">
        {data?.lines.length
          ? data.lines.map((line, i) => (
              <div key={i} className={cn("whitespace-pre-wrap break-words", tone(line))}>
                {line}
              </div>
            ))
          : data
            ? "Nothing at this level."
            : "Loading…"}
      </pre>
    </Page>
  );
}
