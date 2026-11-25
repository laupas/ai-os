import { useSyncExternalStore } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";

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

// Both choices are kept with the user's account (/api/me/appearance), so they follow
// them to every browser. localStorage holds a copy for the first paint and the sign-in
// page, before the account is known. "system" follows the device, live.
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

function adopt(nextMode: Theme, nextAccent: Accent) {
  mode = nextMode;
  accent = nextAccent;
  store(MODE_KEY, mode === "system" ? null : mode);
  store(ACCENT_KEY, accent === THEMES[0].id ? null : accent);
  changed();
}

async function save() {
  try {
    await api("PUT", "/api/me/appearance", { mode, theme: accent });
  } catch (e) {
    toast.error(`Not saved to your account: ${(e as Error).message}`);
  }
}

export function setTheme(next: Theme) {
  adopt(next, accent);
  void save();
}

export function setAccent(next: Accent) {
  adopt(mode, next);
  void save();
}

/** Once signed in: the account's choice wins over this browser's copy. An account
 * with none yet takes over what this browser had, so nobody loses a choice made
 * before it was kept with the account. */
export async function loadAccountAppearance() {
  let saved: { mode: string; theme: string } | null;
  try {
    saved = await api<{ mode: string; theme: string } | null>("GET", "/api/me/appearance");
  } catch {
    return; // keep this browser's copy
  }
  if (saved) {
    const savedMode: Theme = saved.mode === "light" || saved.mode === "dark" ? saved.mode : "system";
    adopt(savedMode, THEMES.find((t) => t.id === saved.theme)?.id ?? THEMES[0].id);
  } else if (mode !== "system" || accent !== THEMES[0].id) {
    await save();
  }
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
