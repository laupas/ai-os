import { KeyRound } from "lucide-react";
import { href } from "@/lib/router";
import { securityProblem, useSecurity } from "@/lib/use-security";

/** For administrators, while the secrets key needs them: where every page shows it. */
export function SecurityBanner() {
  const { data } = useSecurity();
  const problem = securityProblem(data);
  if (!problem) return null;
  return (
    <div className="flex shrink-0 items-center gap-2 border-b bg-warning/20 px-4 py-2 text-sm">
      <KeyRound className="size-4 shrink-0" />
      <span className="flex-1">{problem}</span>
      <a className="shrink-0 font-medium underline" href={href("settings", "security")}>
        Security
      </a>
    </div>
  );
}
