// Reads replies aloud with the device's own voices (speechSynthesis). Text comes in
// sentence by sentence while a reply is still being written; a reply keeps the
// language of its first sentence, so the voice does not switch halfway.

export type Language = "de" | "en";

const GERMAN = /\b(der|die|das|und|ich|nicht|ist|ein|eine|du|sie|mit|für|auf|wir|habe|hast|dein|ja|nein|heute|morgen|gerne|kann)\b|[äöüß]/gi;
const ENGLISH = /\b(the|and|is|you|it|to|of|for|on|with|have|your|yes|no|today|tomorrow|can|will)\b/gi;
const STORAGE_KEY = "aios.voice.voices";

export function languageOf(text: string): Language {
  return (text.match(GERMAN)?.length ?? 0) > (text.match(ENGLISH)?.length ?? 0) ? "de" : "en";
}

/** Markdown read aloud: keep the words, drop the markup. */
export function forSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[*_`#>|~]/g, "")
    .replace(/^\s*[-+]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Prefers the voices Apple, Microsoft and Google ship as their better ones. */
function score(voice: SpeechSynthesisVoice): number {
  const name = voice.name.toLowerCase();
  let points = 0;
  if (name.includes("premium")) points += 4;
  if (name.includes("enhanced") || name.includes("natural") || name.includes("neural")) points += 3;
  if (name.includes("online") || name.includes("google")) points += 1;
  if (voice.localService) points += 1;
  return points;
}

const IDLE_CHECK_MS = 250;

export class Speaker {
  private pending = 0;
  private language: Language | null = null;
  private onIdle: (() => void) | null = null;
  private idleCheck: number | undefined;
  // Chrome may never end an utterance it no longer holds a reference to.
  private readonly queued = new Set<SpeechSynthesisUtterance>();

  static supported(): boolean {
    return typeof window !== "undefined" && "speechSynthesis" in window;
  }

  static voices(language: Language): SpeechSynthesisVoice[] {
    return speechSynthesis
      .getVoices()
      .filter((v) => v.lang.toLowerCase().startsWith(language))
      .sort((a, b) => score(b) - score(a));
  }

  static chosen(): Partial<Record<Language, string>> {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    } catch {
      return {};
    }
  }

  static choose(language: Language, voiceURI: string): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...Speaker.chosen(), [language]: voiceURI }));
    } catch {
      // private mode: the choice lasts for this page only
    }
  }

  /** iOS speaks only after a first utterance started from a tap. */
  unlock(): void {
    speechSynthesis.speak(new SpeechSynthesisUtterance(""));
  }

  beginReply(): void {
    this.language = null;
  }

  get speaking(): boolean {
    return this.pending > 0;
  }

  /** Called once when everything queued has been spoken. Besides each utterance's
   * end event, the engine itself is asked, since browsers lose those events. */
  whenIdle(callback: () => void): void {
    this.onIdle = callback;
    if (this.pending === 0) return this.idle();
    window.clearInterval(this.idleCheck);
    this.idleCheck = window.setInterval(() => {
      if (!speechSynthesis.speaking && !speechSynthesis.pending) this.idle();
    }, IDLE_CHECK_MS);
  }

  say(text: string, language?: Language): void {
    const words = forSpeech(text);
    if (!words) return;
    const lang = language ?? (this.language ??= languageOf(words));
    const utterance = new SpeechSynthesisUtterance(words);
    const voices = Speaker.voices(lang);
    utterance.voice = voices.find((v) => v.voiceURI === Speaker.chosen()[lang]) ?? voices[0] ?? null;
    utterance.lang = utterance.voice?.lang ?? (lang === "de" ? "de-DE" : "en-US");
    utterance.onend = utterance.onerror = () => {
      this.queued.delete(utterance);
      this.pending = Math.max(0, this.pending - 1);
      if (this.pending === 0) this.idle();
    };
    this.queued.add(utterance);
    this.pending += 1;
    speechSynthesis.speak(utterance);
  }

  cancel(): void {
    this.pending = 0;
    this.queued.clear();
    this.onIdle = null;
    window.clearInterval(this.idleCheck);
    speechSynthesis.cancel();
  }

  private idle(): void {
    window.clearInterval(this.idleCheck);
    this.pending = 0;
    this.queued.clear();
    const callback = this.onIdle;
    this.onIdle = null;
    callback?.();
  }
}
