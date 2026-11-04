import { useEffect, useState } from "react";

/** `?debug` in the address: what the browser tells the page about its own size, to
 * fit the console around a phone browser's toolbars from facts rather than guesses. */
export function ViewportDebug() {
  const [, tick] = useState(0);
  useEffect(() => {
    const update = () => tick((n) => n + 1);
    window.visualViewport?.addEventListener("resize", update);
    window.visualViewport?.addEventListener("scroll", update);
    window.addEventListener("resize", update);
    const timer = setInterval(update, 1000);
    return () => {
      window.visualViewport?.removeEventListener("resize", update);
      window.visualViewport?.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
      clearInterval(timer);
    };
  }, []);
  if (!new URLSearchParams(window.location.search).has("debug")) return null;
  const probe = document.createElement("div");
  probe.style.cssText =
    "position:fixed;top:env(safe-area-inset-top);bottom:env(safe-area-inset-bottom);left:0;width:1px;visibility:hidden";
  document.body.appendChild(probe);
  const safe = probe.getBoundingClientRect();
  probe.remove();
  const vv = window.visualViewport;
  const header = document.querySelector("header")?.getBoundingClientRect();
  const rows: [string, string | number | undefined][] = [
    ["inner", `${window.innerWidth}×${window.innerHeight}`],
    ["outer", `${window.outerWidth}×${window.outerHeight}`],
    ["screen", `${screen.width}×${screen.height}`],
    ["client", `${document.documentElement.clientWidth}×${document.documentElement.clientHeight}`],
    ["vv", vv ? `${Math.round(vv.width)}×${Math.round(vv.height)} top ${Math.round(vv.offsetTop)} page ${Math.round(vv.pageTop)}` : "none"],
    ["scrollY", window.scrollY],
    ["safe", `top ${Math.round(safe.top)} bottom ${Math.round(window.innerHeight - safe.bottom)}`],
    ["--keyboard", getComputedStyle(document.documentElement).getPropertyValue("--keyboard")],
    ["header", header ? `top ${Math.round(header.top)} h ${Math.round(header.height)}` : "none"],
    ["ua", navigator.userAgent.replace(/^Mozilla\/5\.0 /, "").slice(0, 90)],
  ];
  return (
    <div className="pointer-events-none fixed top-1/3 left-2 z-[100] rounded-md bg-black/80 p-2 font-mono text-[11px] leading-tight text-white">
      {rows.map(([k, v]) => (
        <div key={k}>
          {k}: {v}
        </div>
      ))}
    </div>
  );
}
