import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "sonner";
import { App } from "./App";
import { ViewportDebug } from "./components/viewport-debug";
import { ConfirmProvider } from "./lib/confirm";
import "./index.css";

// Follow the system theme, live.
const dark = window.matchMedia("(prefers-color-scheme: dark)");
const applyTheme = () => document.documentElement.classList.toggle("dark", dark.matches);
applyTheme();
dark.addEventListener("change", applyTheme);

// The shell is pinned to the window's edges (`fixed inset-0`), which browsers lay out
// around their own toolbars; every height the page can read was wrong in at least
// one phone browser (`dvh` ran under a floating toolbar, `svh` and the visual
// viewport left a gap below the composer). Only the on-screen keyboard is measured,
// since iOS lays nothing out for it: `--keyboard` lifts the shell's bottom edge.
const viewport = window.visualViewport;
const fitKeyboard = () => {
  const covered = viewport ? window.innerHeight - viewport.height - viewport.offsetTop : 0;
  // Below this it is toolbar movement, not a keyboard.
  const keyboard = covered > 120 ? Math.round(covered) : 0;
  document.documentElement.style.setProperty("--keyboard", `${keyboard}px`);
  if (window.scrollY) window.scrollTo(0, 0);
};
// Chrome on iOS can scroll the window or settle its toolbars without a visual
// viewport event, leaving the top bar pushed under its address bar until the tab
// is switched. So the window's own events count too, and each fit is checked again
// once the browser has finished moving.
let settle: number | undefined;
const fitNowAndLater = () => {
  fitKeyboard();
  window.clearTimeout(settle);
  settle = window.setTimeout(fitKeyboard, 300);
};
fitKeyboard();
viewport?.addEventListener("resize", fitNowAndLater);
viewport?.addEventListener("scroll", fitNowAndLater);
window.addEventListener("resize", fitNowAndLater);
window.addEventListener("scroll", fitNowAndLater, { passive: true });

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: true, retry: 1 } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfirmProvider>
        <App />
        <ViewportDebug />
        <Toaster position="top-center" richColors closeButton />
      </ConfirmProvider>
    </QueryClientProvider>
  </StrictMode>,
);
