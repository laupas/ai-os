// Which of a question's options a spoken answer means. A transcript is rarely the
// option verbatim: "Ja, Carol." for "Carol", "Karol" for a name it has not seen,
// "die zweite" for the second. When it is not clear, the answer is null and the
// question is asked again: guessing would answer for the user.

const ORDINALS: string[][] = [
  ["erste", "ersten", "eins", "first", "one"],
  ["zweite", "zweiten", "zwei", "second", "two"],
  ["dritte", "dritten", "drei", "third", "three"],
  ["vierte", "vierten", "vier", "fourth", "four"],
  ["fünfte", "fünften", "fünf", "fifth", "five"],
];
const YES = new Set(["ja", "yes", "genau", "richtig", "korrekt", "jawohl", "gerne", "ok", "okay"]);
const NO = new Set(["nein", "no", "nope", "falsch"]);

function words(text: string): string[] {
  return text
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .split(/[^a-z0-9ß]+/)
    .filter(Boolean);
}

/** 1 for equal, towards 0 the more edits it takes. */
function similarity(a: string, b: string): number {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
  }
  return 1 - d[a.length][b.length] / Math.max(a.length, b.length, 1);
}

/** How well the spoken words cover the option's words, 0..1. */
function coverage(spoken: string[], option: string[]): number {
  if (option.length === 0) return 0;
  const best = option.map((w) => Math.max(0, ...spoken.map((s) => similarity(s, w))));
  return best.reduce((a, b) => a + b, 0) / option.length;
}

/** `question` lets a plain yes pick the one option it names: "Meinst du Carol?" "Ja." */
export function matchOption(transcript: string, options: string[], question = ""): string | null {
  const spoken = words(transcript);
  if (spoken.length === 0) return null;

  const ordinal = ORDINALS.findIndex((forms) => spoken.some((w) => forms.includes(w)));
  if (ordinal >= 0 && ordinal < options.length && !options.some((o) => words(o).some((w) => ORDINALS[ordinal].includes(w)))) {
    return options[ordinal];
  }

  const scored = options
    .map((option) => ({ option, score: coverage(spoken, words(option)) }))
    .sort((a, b) => b.score - a.score);
  const [best, second] = scored;
  if (best && best.score >= 0.75 && (!second || best.score - second.score >= 0.15)) return best.option;

  // A bare yes or no, for options that are yes and no in other words.
  const optionWords = options.map(words);
  const sayYes = spoken.some((w) => YES.has(w));
  const sayNo = spoken.some((w) => NO.has(w));
  if (sayYes !== sayNo) {
    const set = sayYes ? YES : NO;
    const hits = options.filter((_, i) => optionWords[i].some((w) => set.has(w)));
    if (hits.length === 1) return hits[0];
    const asked = words(question.split(/[.!?]\s+/).filter((s) => s.trim()).at(-1) ?? ""); // the question itself
    const named = options.filter((_, i) => optionWords[i].length > 0 && optionWords[i].every((w) => asked.includes(w)));
    if (sayYes && named.length === 1) return named[0];
  }
  return null;
}
