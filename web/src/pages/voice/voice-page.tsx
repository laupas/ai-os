import { useQuery } from "@tanstack/react-query";
import { Loader2, Mic, MicOff, Plus, Settings2, Volume2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, ApiError, type ConversationEvent } from "@/lib/api";
import { href } from "@/lib/router";
import { cn } from "@/lib/utils";
import { Markdown } from "@/pages/chat/markdown";
import { AskCard } from "@/pages/chat/message-views";
import { matchOption } from "@/pages/voice/option-matcher";
import { languageOf, Speaker, type Language } from "@/pages/voice/speaker";
import { VoiceListener, type ListenerStats } from "@/pages/voice/voice-listener";

type Phase = "off" | "listening" | "hearing" | "transcribing" | "thinking" | "speaking" | "answering";

interface Entry {
  role: "user" | "assistant";
  text: string;
}

interface Ask {
  id: string;
  question: string;
  options: string[];
  voiceAnswerable: boolean;
  answered?: string;
}

/** What a transcription service makes of silence or a cough. */
const NOISE = /^(untertitel.*|vielen dank\.?|vielen dank fürs zuschauen\.?|thank you\.?|thanks for watching\.?|you\.?|\W*)$/i;
/** Said to cut ai-os off, not to tell it anything. */
const STOP = /^\W*(stopp?|halt|ruhe|okay|ok|danke|schon gut|stop it|that's enough)\W*$/i;
/** "Stopp, what about tomorrow?": the command is what follows. */
const LEADING_STOP = /^\W*(stopp?|halt)\b[\s,.!?:;-]*/i;
/** A sentence is complete once whitespace follows its end. */
const SENTENCE_END = /[.!?…:](?=\s)|\n/g;

const LABELS: Record<Phase, string> = {
  off: "Tap to start talking",
  listening: "Listening",
  hearing: "Hearing you, tap to send",
  transcribing: "Transcribing",
  thinking: "Thinking, talk or tap to stop",
  speaking: "Speaking, talk or tap to interrupt",
  answering: "Answer by voice, or tap an option",
};

function either(options: string[], language: Language): string {
  const or = language === "de" ? " oder " : " or ";
  return options.length < 2 ? options.join("") : `${options.slice(0, -1).join(", ")}${or}${options.at(-1)}`;
}

/** The question as it is read out: options it does not name are added, and a
 * permission says that it needs a tap. */
function spokenQuestion(ask: Ask): string {
  const de = languageOf(ask.question) === "de";
  if (!ask.voiceAnswerable) {
    return de
      ? `Ich brauche deine Freigabe. ${ask.question} Bitte tippe auf deine Antwort.`
      : `I need your approval. ${ask.question} Please tap your answer.`;
  }
  const named = ask.options.every((o) => ask.question.toLowerCase().includes(o.toLowerCase()));
  if (named) return ask.question;
  const lang = de ? "de" : "en";
  return `${ask.question} ${de ? "Zur Wahl" : "Options"}: ${either(ask.options, lang)}.`;
}

async function transcribe(audio: Blob): Promise<string> {
  const response = await fetch("/api/voice/transcriptions", {
    method: "POST",
    headers: { "X-Aios": "1", "Content-Type": audio.type },
    body: audio,
  });
  if (!response.ok) throw new ApiError((await response.text()) || response.statusText, response.status);
  return ((await response.json()) as { text: string }).text.trim();
}

/** Talking with ai-os hands-free: listen, transcribe, answer, read the answer aloud,
 * listen again. Speaking up while it talks or works cuts it off: "stopp" alone
 * just stops it, anything else stops it and becomes the next message. An agent's
 * question is read out and may be answered by voice; permission for a tool is read
 * out but waits for a tap. */
export function VoicePage() {
  const { data: status, error: statusError } = useQuery({
    queryKey: ["voice"],
    queryFn: () => api<{ available: boolean }>("GET", "/api/voice"),
  });
  const [phase, setPhaseState] = useState<Phase>("off");
  const [level, setLevel] = useState(0);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [streamed, setStreamed] = useState("");
  const [step, setStep] = useState<string | null>(null);
  const [asks, setAsks] = useState<Ask[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showVoices, setShowVoices] = useState(false);

  const listener = useRef<VoiceListener | null>(null);
  const speaker = useRef(new Speaker());
  const phaseRef = useRef<Phase>("off");
  const idRef = useRef<string | null>(null);
  // The reply being written: what has arrived since the last restart, how much of
  // it is already queued for speaking, and whether the user cut it off.
  const reply = useRef({ segment: "", spoken: 0, muted: false });
  // Whether a turn is still running, and how many "Stopped." replies of turns
  // cut off by a new message are still to come (and to be ignored).
  const turnRunning = useRef(false);
  const stoppedReplies = useRef(0);
  // The question the turn is waiting for, if any.
  const pendingAsk = useRef<Ask | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const setPhase = useCallback((next: Phase) => {
    phaseRef.current = next;
    setPhaseState(next);
  }, []);

  const inTurn = () => phaseRef.current === "thinking" || phaseRef.current === "speaking";

  const listen = useCallback(() => {
    setPhase("listening");
    listener.current?.listen();
  }, [setPhase]);

  const speak = useCallback(
    (text: string) => {
      if (!inTurn() || reply.current.muted || !text.trim()) return;
      speaker.current.say(text);
      setPhase("speaking");
      listener.current?.listen("interrupt");
    },
    [setPhase],
  );

  /** Says something now, whatever the reply's state, and then listens in `next`. */
  const sayThen = useCallback(
    (text: string, next: Phase) => {
      speaker.current.say(text, languageOf(text));
      setPhase("speaking");
      listener.current?.listen("interrupt");
      speaker.current.whenIdle(() => {
        setPhase(next);
        listener.current?.listen();
      });
    },
    [setPhase],
  );

  /** The question is answered, by voice or by tap; the turn carries on. */
  const answered = useCallback(
    (ask: Ask, option: string) => {
      setAsks((all) => all.map((a) => (a.id === ask.id ? { ...a, answered: option } : a)));
      if (pendingAsk.current?.id !== ask.id) return;
      pendingAsk.current = null;
      reply.current.muted = false;
      speaker.current.cancel();
      setPhase("thinking");
      listener.current?.listen();
    },
    [setPhase],
  );

  const answerByVoice = useCallback(
    async (ask: Ask, text: string) => {
      const de = languageOf(ask.question) === "de";
      if (!ask.voiceAnswerable) {
        return sayThen(de ? "Das musst du bitte antippen." : "Please tap your answer for this one.", "thinking");
      }
      const option = matchOption(text, ask.options, ask.question);
      if (option === null) {
        const lang = de ? "de" : "en";
        const again = de ? "Das habe ich nicht verstanden. Zur Wahl" : "I did not get that. Options";
        return sayThen(`${again}: ${either(ask.options, lang)}.`, "answering");
      }
      try {
        await api("POST", `/api/approvals/${encodeURIComponent(ask.id)}`, { answer: option, voice: true });
        answered(ask, option);
      } catch (e) {
        setError((e as Error).message);
        pendingAsk.current = null;
        setPhase("thinking");
        listener.current?.listen();
      }
    },
    [answered, sayThen, setPhase],
  );

  const speakFinishedSentences = useCallback(() => {
    const r = reply.current;
    const last = [...r.segment.slice(r.spoken).matchAll(SENTENCE_END)].at(-1);
    if (last?.index === undefined) return;
    const end = r.spoken + last.index + last[0].length;
    speak(r.segment.slice(r.spoken, end));
    r.spoken = end;
  }, [speak]);

  /** Stops the running turn quietly, before what was said next takes over. */
  const stopTurn = useCallback(async () => {
    if (!turnRunning.current || idRef.current === null) return;
    turnRunning.current = false;
    try {
      const { stopped } = await api<{ stopped: boolean }>("POST", `/api/conversations/${encodeURIComponent(idRef.current)}/stop`);
      if (stopped) stoppedReplies.current += 1;
    } catch {
      // the turn ends on its own; its reply is then just not spoken
    }
  }, []);

  const send = useCallback(
    async (text: string) => {
      turnRunning.current = true;
      setEntries((e) => [...e, { role: "user", text }]);
      reply.current = { segment: "", spoken: 0, muted: false };
      speaker.current.beginReply();
      setPhase("thinking");
      try {
        if (idRef.current === null) {
          const { id } = await api<{ id: string }>("POST", "/api/conversations", { text, voice: true });
          idRef.current = id;
          setConversationId(id);
        } else {
          await api("POST", `/api/conversations/${encodeURIComponent(idRef.current)}/messages`, { text, voice: true });
        }
        listener.current?.listen(); // "stopp" or the next message while it works
      } catch (e) {
        setError((e as Error).message);
        listen();
      }
    },
    [listen, setPhase],
  );

  const heard = useCallback(
    async (audio: Blob) => {
      setPhase("transcribing");
      try {
        const text = await transcribe(audio);
        const ask = pendingAsk.current;
        if (NOISE.test(text)) {
          if (ask) {
            setPhase(ask.voiceAnswerable ? "answering" : "thinking");
            return listener.current?.listen();
          }
          if (!turnRunning.current || reply.current.muted) return listen();
          setPhase("thinking"); // nothing said; the answer is still to come
          return listener.current?.listen();
        }
        if (ask && !STOP.test(text)) return await answerByVoice(ask, text);
        pendingAsk.current = null;
        await stopTurn();
        if (STOP.test(text)) return listen();
        await send(text.replace(LEADING_STOP, "") || text);
      } catch (e) {
        setError((e as Error).message);
        listen();
      }
    },
    [answerByVoice, listen, send, setPhase, stopTurn],
  );

  // The conversation's events: the reply as it is written, steps, approvals, the end.
  useEffect(() => {
    if (!conversationId) return;
    const source = new EventSource(`/api/conversations/${encodeURIComponent(conversationId)}/events`);
    source.onmessage = (raw) => {
      const event = JSON.parse(raw.data) as ConversationEvent;
      const r = reply.current;
      if (event.kind === "delta") {
        r.segment = event.restart ? event.text : r.segment + event.text;
        if (event.restart) r.spoken = 0;
        setStreamed(r.segment);
        speakFinishedSentences();
      } else if (event.kind === "progress") {
        setStep(event.text);
      } else if (event.kind === "approval" && event.approval_id) {
        const ask: Ask = {
          id: event.approval_id,
          question: event.text,
          options: event.options,
          voiceAnswerable: event.voice_answerable,
        };
        setAsks((a) => (a.some((x) => x.id === ask.id) ? a : [...a, ask]));
        if (phaseRef.current !== "off") {
          pendingAsk.current = ask;
          sayThen(spokenQuestion(ask), ask.voiceAnswerable ? "answering" : "thinking");
        }
      } else if (event.kind === "message" && event.message?.role === "assistant") {
        if (stoppedReplies.current > 0) {
          stoppedReplies.current -= 1;
          return;
        }
        turnRunning.current = false;
        const text = event.message.text;
        const said = r.segment.slice(0, r.spoken);
        speak(text.startsWith(said) ? text.slice(r.spoken) : r.spoken === 0 ? text : "");
        setEntries((e) => [...e, { role: "assistant", text }]);
        setStreamed("");
        setStep(null);
        if (inTurn()) speaker.current.whenIdle(() => inTurn() && listen());
      }
    };
    return () => source.close();
  }, [conversationId, listen, sayThen, speak, speakFinishedSentences]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [entries, streamed, asks]);

  useEffect(
    () => () => {
      listener.current?.close();
      speaker.current.cancel();
    },
    [],
  );

  const start = async () => {
    setError(null);
    speaker.current.unlock();
    const l = new VoiceListener({
      onLevel: setLevel,
      onSpeech: () => {
        if (phaseRef.current === "speaking") {
          reply.current.muted = true;
          speaker.current.cancel();
        }
        setPhase("hearing");
      },
      onUtterance: (audio) => void heard(audio),
    });
    try {
      await l.open();
      listener.current = l;
      listen();
    } catch (e) {
      l.close();
      setError(`No microphone: ${(e as Error).message}`);
    }
  };

  /** Cuts the reply off and listens. The turn carries on until what is said next
   * turns out to be more than noise. */
  const interrupt = () => {
    reply.current.muted = true;
    speaker.current.cancel();
    listen();
  };

  const end = () => {
    pendingAsk.current = null;
    listener.current?.close();
    listener.current = null;
    speaker.current.cancel();
    setLevel(0);
    setPhase("off");
  };

  const tap = async () => {
    if (phase === "off") return start();
    if (phase === "speaking") return interrupt();
    if (phase === "hearing") return listener.current?.finishNow();
    if (phase === "thinking" && idRef.current) {
      await api("POST", `/api/conversations/${encodeURIComponent(idRef.current)}/stop`).catch(() => undefined);
    }
  };

  const restart = () => {
    idRef.current = null;
    setConversationId(null);
    setEntries([]);
    setAsks([]);
    setStreamed("");
    setStep(null);
    reply.current = { segment: "", spoken: 0, muted: true };
    pendingAsk.current = null;
    turnRunning.current = false;
    stoppedReplies.current = 0;
    speaker.current.cancel();
    if (phase !== "off") listen();
  };

  const supported = VoiceListener.supported() && Speaker.supported();
  const unavailable = !supported
    ? "This browser cannot record audio or speak."
    : status && !status.available
      ? "Transcription is not set up on the server (OPENAI_API_KEY)."
      : statusError
        ? (statusError as Error).message
        : null;
  const busy = phase === "transcribing" || phase === "thinking";
  const Icon = phase === "off" ? MicOff : busy ? Loader2 : phase === "speaking" ? Volume2 : Mic;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b px-4 py-2">
        <h1 className="flex-1 text-lg font-semibold">Voice</h1>
        {conversationId ? (
          <a className="text-xs text-muted-foreground underline" href={href("chat", conversationId)}>
            Open in chat
          </a>
        ) : null}
        <Button size="sm" variant="ghost" onClick={() => setShowVoices((s) => !s)} title="Voices">
          <Settings2 className="size-4" />
        </Button>
        <Button size="sm" variant="outline" onClick={restart} disabled={entries.length === 0}>
          <Plus className="size-4" /> New
        </Button>
      </div>

      {showVoices ? <VoiceChoice speaker={speaker.current} listener={listener.current} /> : null}

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <div className="mx-auto max-w-2xl space-y-3">
          {entries.length === 0 && !streamed ? (
            <p className="pt-10 text-center text-sm text-muted-foreground">
              Start, then just talk. ai-os answers out loud and listens again when it is done.
            </p>
          ) : null}
          {entries.map((e, i) =>
            e.role === "user" ? (
              <div key={i} className="ml-auto w-fit max-w-[85%] rounded-2xl bg-primary px-3 py-2 text-[15px] text-primary-foreground">
                {e.text}
              </div>
            ) : (
              <div key={i} className="max-w-[95%]">
                <Markdown text={e.text} />
              </div>
            ),
          )}
          {streamed ? (
            <div className="max-w-[95%] opacity-70">
              <Markdown text={streamed} />
            </div>
          ) : null}
          {step && phase === "thinking" ? <p className="text-xs text-muted-foreground">{step}</p> : null}
          {asks.map((a) => (
            <AskCard
              key={a.id}
              id={a.id}
              question={a.question}
              options={a.options}
              answered={a.answered}
              onAnswered={(option) => answered(a, option)}
            />
          ))}
          <div ref={bottom} />
        </div>
      </div>

      <div className="flex flex-col items-center gap-2 border-t px-4 pt-4 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
        {error ? <p className="text-center text-xs text-destructive">{error}</p> : null}
        {unavailable ? (
          <p className="text-center text-sm text-muted-foreground">{unavailable}</p>
        ) : (
          <>
            <button
              type="button"
              onClick={() => void tap()}
              className="relative flex size-24 items-center justify-center rounded-full"
              aria-label={LABELS[phase]}
            >
              <span
                className="absolute inset-0 rounded-full bg-primary/20 transition-transform duration-75"
                style={{ transform: `scale(${1 + (phase === "listening" || phase === "hearing" || phase === "speaking" ? level * 0.6 : 0)})` }}
              />
              <span
                className={cn(
                  "relative flex size-20 items-center justify-center rounded-full",
                  phase === "off" ? "bg-muted text-muted-foreground" : "bg-primary text-primary-foreground",
                )}
              >
                <Icon className={cn("size-8", busy && "animate-spin")} />
              </span>
            </button>
            <p className="text-sm text-muted-foreground">{phase === "thinking" && step ? step : LABELS[phase]}</p>
            {phase !== "off" ? (
              <Button size="sm" variant="ghost" onClick={end}>
                End
              </Button>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

/** Which of the device's voices reads German and English replies. */
function VoiceChoice({ speaker, listener }: { speaker: Speaker; listener: VoiceListener | null }) {
  const [, refresh] = useState(0);
  const [stats, setStats] = useState<ListenerStats | null>(null);
  useEffect(() => {
    const timer = window.setInterval(() => setStats(listener?.stats() ?? null), 200);
    return () => window.clearInterval(timer);
  }, [listener]);
  const [chosen, setChosen] = useState(Speaker.chosen());
  useEffect(() => {
    const update = () => refresh((n) => n + 1);
    speechSynthesis.addEventListener("voiceschanged", update);
    return () => speechSynthesis.removeEventListener("voiceschanged", update);
  }, []);
  const samples: Record<Language, string> = { de: "Hallo, ich bin ai-os.", en: "Hello, I am ai-os." };
  return (
    <div className="space-y-2 border-b bg-muted/30 px-4 py-3 text-sm">
      {(["de", "en"] as const).map((lang) => {
        const voices = Speaker.voices(lang);
        return (
          <div key={lang} className="flex items-center gap-2">
            <span className="w-16 text-muted-foreground">{lang === "de" ? "German" : "English"}</span>
            <select
              className="min-w-0 flex-1 rounded-md border bg-background px-2 py-1"
              value={chosen[lang] ?? voices[0]?.voiceURI ?? ""}
              onChange={(e) => {
                Speaker.choose(lang, e.target.value);
                setChosen(Speaker.chosen());
              }}
            >
              {voices.map((v) => (
                <option key={v.voiceURI} value={v.voiceURI}>
                  {v.name} ({v.lang})
                </option>
              ))}
            </select>
            <Button size="sm" variant="outline" onClick={() => speaker.say(samples[lang], lang)}>
              Test
            </Button>
          </div>
        );
      })}
      {stats ? (
        <p className="font-mono text-xs text-muted-foreground">
          level {stats.level.toFixed(3)} · background {stats.background.toFixed(3)} · threshold {stats.threshold.toFixed(3)} ·{" "}
          {stats.mode}
          {stats.recording ? " · recording" : ""}
        </p>
      ) : null}
      <p className="text-xs text-muted-foreground">
        Better voices: on Apple devices, download a Premium or Enhanced voice under Settings, Accessibility, Spoken Content.
      </p>
    </div>
  );
}
