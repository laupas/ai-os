import type { Memory, MemoryKind } from "@/lib/api";

export const KINDS: MemoryKind[] = ["preference", "person", "project", "note"];

/** The memories about one subject of one kind; a note without a subject stands alone. */
export interface MemoryGroup {
  key: string;
  kind: MemoryKind;
  subject: string | null;
  memories: Memory[];
}

export const changedAt = (m: Memory) => m.updated_at ?? m.created_at;

const norm = (s: string | null) => (s ?? "").trim().toLowerCase();

/** Groups in kind order, then by subject; inside one, the latest change first. */
export function groupMemories(memories: Memory[]): MemoryGroup[] {
  const groups = new Map<string, MemoryGroup>();
  for (const m of memories) {
    const key = m.subject?.trim() ? `${m.kind}:${norm(m.subject)}` : `${m.kind}#${m.id}`;
    const group = groups.get(key) ?? { key, kind: m.kind, subject: m.subject, memories: [] };
    group.memories.push(m);
    groups.set(key, group);
  }
  for (const g of groups.values()) g.memories.sort((a, b) => changedAt(b).localeCompare(changedAt(a)));
  return [...groups.values()].sort(
    (a, b) => KINDS.indexOf(a.kind) - KINDS.indexOf(b.kind) || norm(a.subject).localeCompare(norm(b.subject)) || changedAt(b.memories[0]).localeCompare(changedAt(a.memories[0])),
  );
}

const words = (text: string) => new Set(text.toLowerCase().match(/[\p{L}\p{N}]{3,}/gu) ?? []);

function similarity(a: Set<string>, b: Set<string>): number {
  if (!a.size || !b.size) return 0;
  let shared = 0;
  for (const w of a) if (b.has(w)) shared++;
  return shared / Math.min(a.size, b.size);
}

/** For each memory that looks like another one of the same owner (most of the
 * shorter one's words are in the other), the ids it looks like. Same-subject
 * entries are not listed: their group already shows them side by side. */
export function lookAlikes(memories: Memory[], threshold = 0.7): Map<string, string[]> {
  const sets = memories.map((m) => words(`${m.subject ?? ""} ${m.text}`));
  const found = new Map<string, string[]>();
  for (let i = 0; i < memories.length; i++) {
    for (let j = i + 1; j < memories.length; j++) {
      const [a, b] = [memories[i], memories[j]];
      if (a.user_id !== b.user_id || (a.kind === b.kind && norm(a.subject) === norm(b.subject))) continue;
      if (similarity(sets[i], sets[j]) < threshold) continue;
      found.set(a.id, [...(found.get(a.id) ?? []), b.id]);
      found.set(b.id, [...(found.get(b.id) ?? []), a.id]);
    }
  }
  return found;
}
