import { toast } from "sonner";
import { api } from "@/lib/api";

/** Restarts ai-os and reloads the page once it answers again. */
export async function restartAiOs() {
  await api("POST", "/api/restart");
  toast("Restarting…");
  const wait = async () => {
    try {
      await api("GET", "/api/me");
      location.reload();
    } catch {
      setTimeout(wait, 2000);
    }
  };
  setTimeout(wait, 3000);
}
