import { useSyncExternalStore } from "react";

export type Theme = "system" | "light" | "dark";

/** The colour themes, each a class in index.css (`theme-<id>`). The first is the default. */
export const THEMES = [
  { id: "indigo", label: "Indigo" },
  { id: "blue", label: "Blue" },
  { id: "teal", label: "Teal" },
  { id: "green", label: "Green" },
  { id: "orange", label: "Orange" },
  { id: "rose", label: "Rose" },
  { id: "graphite", label: "Graphite" },
] as const;
export type Accent = (typeof THEMES)[number]["id"];

// Both choices are this browser's own, kept in localStorage; "system" follows the
// device, live. A browser that refuses storage keeps the defaults.
const MODE_KEY = "aios-theme";
const ACCENT_KEY = "aios-accent";
const systemDark = window.matchMedia("(prefers-color-scheme: dark)");
const listeners = new Set<() => void>();

function stored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function store(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Not kept past this page; it still applies now.
  }
}

const readMode = (): Theme => {
  const value = stored(MODE_KEY);
  return value === "light" || value === "dark" ? value : "system";
};
const readAccent = (): Accent => THEMES.find((t) => t.id === stored(ACCENT_KEY))?.id ?? THEMES[0].id;

let mode = readMode();
let accent = readAccent();

export function applyTheme() {
  const root = document.documentElement;
  root.classList.toggle("dark", mode === "dark" || (mode === "system" && systemDark.matches));
  THEMES.forEach((t) => root.classList.toggle(`theme-${t.id}`, t.id === accent));
}

function changed() {
  applyTheme();
  listeners.forEach((notify) => notify());
}

export function setTheme(next: Theme) {
  mode = next;
  store(MODE_KEY, next === "system" ? null : next);
  changed();
}

export function setAccent(next: Accent) {
  accent = next;
  store(ACCENT_KEY, next === THEMES[0].id ? null : next);
  changed();
}

systemDark.addEventListener("change", applyTheme);

const subscribe = (notify: () => void) => {
  listeners.add(notify);
  return () => {
    listeners.delete(notify);
  };
};

export function useTheme(): [Theme, (theme: Theme) => void] {
  return [useSyncExternalStore(subscribe, () => mode), setTheme];
}

export function useAccent(): [Accent, (accent: Accent) => void] {
  return [useSyncExternalStore(subscribe, () => accent), setAccent];
}
