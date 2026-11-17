// Hands-free listening: the microphone stays open, a level meter decides when
// someone starts and stops talking, and each utterance comes out as one WAV file.
//
// The last moment of sound is always kept, so an utterance starts a little before
// it was recognised as speech and its first word is not cut off.
//
// Loud means clearly above the background, which is tracked all the time: it
// falls quickly when the room gets quiet and rises only slowly, so a steady fan
// becomes background within seconds while speech hardly moves it. An utterance
// ends when the level stays near the background, or well below how loud the
// speaker was, for a moment.
//
// While ai-os is speaking, the microphone hears it too: the device's own voices do
// not pass through the browser's echo cancellation. "interrupt" mode therefore
// measures against the loud part (75th percentile) of the last three seconds,
// which ai-os's voice fills and a short interruption hardly moves, waits until it
// has heard ai-os for a moment, and asks for more above it, for longer.

const RATE = 16_000; // plenty for speech, and a third of what a microphone delivers
const FRAME = 2048;
const PREROLL_MS = 700;
const MIN_SPEECH_MS = 300; // shorter bursts are clicks and coughs
const END_SILENCE_MS = 1200; // this much quiet after speech ends the utterance
const MAX_UTTERANCE_MS = 120_000; // about 4 MB, under the server's limit
const MIN_LEVEL = 0.01;
const FACTOR = 2.5; // times the background
const SPEECH_SHARE = 0.2; // below this share of the speaker's level counts as a pause
const INTERRUPT_SPEECH_MS = 400;
const INTERRUPT_FACTOR = 2;
const INTERRUPT_MIN_LEVEL = 0.03;
const INTERRUPT_GRACE_MS = 800;
const HISTORY_MS = 3000;

export interface ListenerStats {
  level: number;
  background: number;
  threshold: number;
  mode: ListenMode;
  recording: boolean;
}

export type ListenMode = "normal" | "interrupt";

export interface ListenerEvents {
  /** 0..1, for a meter. */
  onLevel(level: number): void;
  /** Speech was recognised; the utterance is being recorded. */
  onSpeech(): void;
  onUtterance(audio: Blob): void;
}

export class VoiceListener {
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private listening = false;
  private mode: ListenMode = "normal";
  private background = 0.01;
  private speech = 0; // how loud the current utterance is
  private threshold = MIN_LEVEL;
  private level = 0;
  private history: number[] = [];
  private modeSince = 0;
  private speechMs = 0;
  private lastVoice = 0;
  private preroll: Float32Array[] = [];
  private capture: Float32Array[] | null = null;
  private captureSince = 0;

  constructor(private readonly events: ListenerEvents) {}

  static supported(): boolean {
    return Boolean(navigator.mediaDevices?.getUserMedia) && typeof AudioContext !== "undefined";
  }

  /** Asks for the microphone. Call from a tap: browsers want a gesture for audio. */
  async open(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const context = new AudioContext();
    await context.resume();
    // ScriptProcessorNode is deprecated, but it runs everywhere without a worklet file.
    const processor = context.createScriptProcessor(FRAME, 1, 1);
    processor.onaudioprocess = (e) => this.frame(e.inputBuffer.getChannelData(0), context.sampleRate);
    const silent = context.createGain();
    silent.gain.value = 0; // a processor only runs while connected to the output
    context.createMediaStreamSource(this.stream).connect(processor);
    processor.connect(silent);
    silent.connect(context.destination);
    this.context = context;
    this.processor = processor;
  }

  /** Starts listening, or switches mode. Does not cut off an utterance in progress. */
  listen(mode: ListenMode = "normal"): void {
    if (!this.stream || (this.listening && this.mode === mode) || this.capture) return;
    this.listening = true;
    this.mode = mode;
    this.modeSince = performance.now();
    this.speechMs = 0;
    this.speech = 0;
    this.preroll = []; // may hold ai-os's last words
  }

  /** Ends the utterance now and hands it over, as if a pause had been heard. */
  finishNow(): void {
    if (this.capture) this.finish();
  }

  stats(): ListenerStats {
    return {
      level: this.level,
      background: this.background,
      threshold: this.threshold,
      mode: this.mode,
      recording: this.capture !== null,
    };
  }

  /** Stops listening and drops whatever was recorded. */
  pause(): void {
    this.listening = false;
    this.capture = null;
  }

  close(): void {
    this.pause();
    this.processor?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.context?.close();
    this.processor = null;
    this.stream = null;
    this.context = null;
  }

  private frame(input: Float32Array, rate: number): void {
    const rms = Math.sqrt(input.reduce((sum, s) => sum + s * s, 0) / input.length);
    this.level = rms;
    this.events.onLevel(Math.min(1, rms * 8));
    // Down fast, up slowly (about 6 s): a steady sound becomes background, speech not.
    this.background = rms < this.background ? this.background * 0.7 + rms * 0.3 : this.background * 0.993 + rms * 0.007;
    this.history.push(rms);
    if (this.history.length > HISTORY_MS / ((input.length / rate) * 1000)) this.history.shift();
    if (!this.listening) return;

    const samples = downsample(input, rate);
    if (this.capture) {
      this.capture.push(samples);
    } else {
      this.preroll.push(samples);
      while (this.preroll.length > 1 && (this.preroll.length - 1) * samples.length > (RATE * PREROLL_MS) / 1000) {
        this.preroll.shift();
      }
    }

    const now = performance.now();
    const ms = (input.length / rate) * 1000;
    const interrupt = this.mode === "interrupt";
    this.threshold = interrupt
      ? Math.max(INTERRUPT_MIN_LEVEL, percentile(this.history, 0.75) * INTERRUPT_FACTOR)
      : Math.max(MIN_LEVEL, this.background * FACTOR, this.speech * SPEECH_SHARE);
    const loud = rms > this.threshold && !(interrupt && now - this.modeSince < INTERRUPT_GRACE_MS);
    if (loud) {
      this.speechMs += ms;
      this.lastVoice = now;
      this.speech = Math.max(rms, this.speech * 0.98); // follows the speaker's loudness
      if (!this.capture && this.speechMs >= (interrupt ? INTERRUPT_SPEECH_MS : MIN_SPEECH_MS)) this.begin(now);
    }

    if (!this.capture) {
      // A burst too short for speech; in interrupt mode it has to be unbroken.
      if (this.speechMs > 0 && now - this.lastVoice > (interrupt ? 300 : END_SILENCE_MS)) this.speechMs = 0;
    } else if (now - this.lastVoice > END_SILENCE_MS || now - this.captureSince > MAX_UTTERANCE_MS) {
      this.finish();
    }
  }

  private begin(now: number): void {
    this.capture = this.preroll;
    this.preroll = [];
    this.captureSince = now;
    this.mode = "normal";
    this.events.onSpeech();
  }

  private finish(): void {
    const capture = this.capture ?? [];
    this.capture = null;
    this.speech = 0;
    this.listening = false;
    this.events.onUtterance(wav(capture));
  }
}

function percentile(values: number[], share: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * share))];
}

/** Averages the microphone's samples down to RATE. */
function downsample(input: Float32Array, rate: number): Float32Array {
  const ratio = rate / RATE;
  if (ratio <= 1) return input.slice();
  const out = new Float32Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    out[i] = sum / Math.max(1, end - start);
  }
  return out;
}

/** 16-bit mono PCM in a WAV container, which every transcription service reads. */
function wav(chunks: Float32Array[]): Blob {
  const length = chunks.reduce((n, c) => n + c.length, 0);
  const view = new DataView(new ArrayBuffer(44 + length * 2));
  const text = (offset: number, s: string) => [...s].forEach((ch, i) => view.setUint8(offset + i, ch.charCodeAt(0)));
  text(0, "RIFF");
  view.setUint32(4, 36 + length * 2, true);
  text(8, "WAVEfmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, RATE, true);
  view.setUint32(28, RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, length * 2, true);
  let offset = 44;
  for (const chunk of chunks) {
    for (const s of chunk) {
      view.setInt16(offset, Math.max(-1, Math.min(1, s)) * 0x7fff, true);
      offset += 2;
    }
  }
  return new Blob([view], { type: "audio/wav" });
}
