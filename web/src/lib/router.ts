import { useEffect, useState } from "react";

// Hash routes (#/chat/abc): the server serves one page, and old links keep working.
function read(): string[] {
  return location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
}

// Forms with changes not saved yet. While there is one, leaving the page asks first:
// a link, the back button or go() puts the address back and asks; closing the tab
// gets the browser's own question.
const unsaved = new Set<symbol>();
let askToLeave: () => Promise<boolean> = async () => window.confirm("Discard your changes?");
let leaving = false;

/** The question asked before unsaved changes are left behind; the console's own dialog (see confirm.tsx). */
export function setLeaveQuestion(ask: () => Promise<boolean>) {
  askToLeave = ask;
}

/** Marks the calling form as having unsaved changes while `dirty` holds. */
export function useUnsaved(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const key = Symbol();
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    unsaved.add(key);
    window.addEventListener("beforeunload", warn);
    return () => {
      unsaved.delete(key);
      window.removeEventListener("beforeunload", warn);
    };
  }, [dirty]);
}

export function useRoute(): string[] {
  const [route, setRoute] = useState(read);
  useEffect(() => {
    let shown = location.hash;
    let asking = false;
    const update = async () => {
      if (location.hash === shown) return;
      if (unsaved.size && !leaving) {
        const target = location.hash;
        // replaceState fires no hashchange: the page stays as it is while the question is open.
        history.replaceState(null, "", shown || location.pathname + location.search);
        if (asking) return;
        asking = true;
        const leave = await askToLeave();
        asking = false;
        if (leave) goAnyway(target);
        return;
      }
      leaving = false;
      shown = location.hash;
      setRoute(read());
    };
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}

export const href = (...parts: string[]) => "#/" + parts.map(encodeURIComponent).join("/");

export function go(...parts: string[]) {
  location.hash = href(...parts);
}

/** Navigates without asking about unsaved changes: after a save or a delete, or once the user said to discard them. */
function goAnyway(hash: string) {
  unsaved.clear();
  leaving = true;
  location.hash = hash;
}

export const goSaved = (...parts: string[]) => goAnyway(href(...parts));
