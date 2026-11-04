import { useEffect, useState } from "react";

// Hash routes (#/chat/abc): the server serves one page, and old links keep working.
function read(): string[] {
  return location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
}

export function useRoute(): string[] {
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const update = () => setRoute(read());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}

export function go(...parts: string[]) {
  location.hash = "#/" + parts.map(encodeURIComponent).join("/");
}

export const href = (...parts: string[]) => "#/" + parts.map(encodeURIComponent).join("/");
