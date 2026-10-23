import type { Api, Product, CallResult, Segment } from "./api";

interface Events {
  status: (message: string) => void;
  active: (active: boolean) => void;
  transcript: (segment: Segment) => void;
  result: (result: CallResult) => void;
}
interface AudioEvent {
  audio: string;
  seq: number;
  epoch: number;
}

// Provider generation can outrun real-time playback. Bound memory by the
// maximum demo duration rather than treating a normal introduction as failure.
const MAX_QUEUED_AUDIO_SECONDS = 120;

/** The existing PCM relay, isolated from the UI. Audio only lives in memory. */
export class CallClient {
  private ws: WebSocket | null = null;
  private ctx: AudioContext | null = null;
  private mic: MediaStream | null = null;
  private capture: AudioWorkletNode | null = null;
  private sources = new Set<AudioBufferSourceNode>();
  private nextTime = 0;
  private epoch = 0;
  private suppressed = false;
  private streaming = false;
  private halfDuplex = false;
  private listening = true;
  private listeningTimer: ReturnType<typeof setTimeout> | undefined;
  private disposed = false;
  private finalized = false;
  private playbackFailure: string | null = null;
  private id: string | null = null;

  constructor(
    private api: Api,
    private events: Events,
  ) {}
  private send(event: object) {
    if (this.ws?.readyState === WebSocket.OPEN)
      this.ws.send(JSON.stringify(event));
  }
  private stopPlayback() {
    for (const source of this.sources) {
      source.onended = null;
      try {
        source.stop();
      } catch {
        /* Already ended. */
      }
    }
    this.sources.clear();
    this.nextTime = this.ctx?.currentTime ?? 0;
  }
  private stopCapture() {
    clearTimeout(this.listeningTimer);
    this.listening = false;
    this.streaming = false;
    this.capture?.disconnect();
    this.capture = null;
    this.mic?.getTracks().forEach((track) => track.stop());
    this.mic = null;
    this.events.active(false);
  }
  private cleanup() {
    this.stopCapture();
    this.stopPlayback();
    if (this.ctx) void this.ctx.close();
    this.ctx = null;
  }
  private play(event: AudioEvent) {
    if (!this.ctx || this.suppressed || event.epoch < this.epoch) return;
    this.epoch = event.epoch;
    const bytes = Uint8Array.from(atob(event.audio), (char) =>
      char.charCodeAt(0),
    );
    if (bytes.length % 2) throw new Error("قالب صدای دریافتی نامعتبر است");
    const view = new DataView(bytes.buffer);
    const buffer = this.ctx.createBuffer(1, bytes.length / 2, 24000);
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++)
      samples[i] = view.getInt16(i * 2, true) / 32768;
    if (Math.max(0, this.nextTime - this.ctx.currentTime) + buffer.duration > MAX_QUEUED_AUDIO_SECONDS)
      throw new Error("صف پخش بیش از حد مجاز است");
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.ctx.destination);
    this.sources.add(source);
    const start = Math.max(this.ctx.currentTime + 0.025, this.nextTime);
    this.nextTime = start + buffer.duration;
    source.onended = () => {
      this.sources.delete(source);
      source.disconnect();
      this.send({ type: "played", seq: event.seq, epoch: event.epoch });
    };
    source.start(start);
  }
  private async waitResult() {
    for (let attempt = 0; attempt < 50 && !this.disposed; attempt++) {
      const response = await fetch(`/api/calls/${this.id}/result`);
      if (response.ok) return response.json() as Promise<CallResult>;
      if (response.status !== 409) break;
      this.events.status("در حال نهایی‌سازی متن و نتیجه…");
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    throw new Error("نتیجهٔ نهایی در دسترس نیست.");
  }
  private async handle(event: Record<string, unknown>) {
    if (this.disposed) return;
    if (event.type === "ready") {
      if (!this.ctx || !this.mic) return;
      this.halfDuplex = event.turn_taking === "half_duplex";
      this.listening = !this.halfDuplex;
      for (const track of this.mic.getAudioTracks()) track.enabled = this.listening;
      this.events.status(this.halfDuplex ? "نوبت دستیار است؛ پس از پایان پاسخ صحبت کنید." : "دمو فعال است؛ شما نقش فروشنده را دارید.");
      const input = this.ctx.createMediaStreamSource(this.mic);
      this.capture = new AudioWorkletNode(this.ctx, "pcm-capture");
      this.capture.port.onmessage = ({
        data,
      }: MessageEvent<{ pcm: ArrayBuffer; rms: number }>) => {
        if (!this.streaming || !this.listening) return;
        if (!this.halfDuplex && !this.suppressed && this.sources.size && data.rms > 0.06) {
          this.stopPlayback();
          this.suppressed = true;
          this.send({ type: "barge_in" });
        }
        if ((this.ws?.bufferedAmount ?? 0) > 1_000_000) {
          this.send({ type: "playback_error" });
          this.cleanup();
          return;
        }
        let text = "";
        for (const byte of new Uint8Array(data.pcm))
          text += String.fromCharCode(byte);
        this.send({ type: "audio", audio: btoa(text) });
      };
      input.connect(this.capture);
      this.capture.connect(this.ctx.destination);
    } else if (event.type === "listening" && this.halfDuplex) {
      clearTimeout(this.listeningTimer);
      this.listening = false;
      for (const track of this.mic?.getAudioTracks() || []) track.enabled = false;
      if (event.enabled === true) {
        // Let the last speaker frame leave the device before enabling capture.
        this.listeningTimer = setTimeout(() => {
          if (this.disposed || !this.streaming || !this.mic) return;
          this.listening = true;
          for (const track of this.mic.getAudioTracks()) track.enabled = true;
          this.events.status("نوبت شماست؛ حالا صحبت کنید.");
        }, 200);
      } else this.events.status("نوبت دستیار است؛ پس از پایان پاسخ صحبت کنید.");
    } else if (event.type === "finalizing") {
      this.stopCapture();
      this.events.status("در حال نهایی‌سازی متن و نتیجه…");
    } else if (event.type === "audio")
      this.play(event as unknown as AudioEvent);
    else if (event.type === "interrupt") {
      this.stopPlayback();
      this.epoch = Number(event.epoch);
      this.suppressed = false;
      this.events.status("پخش دستیار قطع شد؛ صحبت شما دریافت می‌شود.");
    } else if (event.type === "transcript") {
      this.events.transcript({
        item_id: String(event.item_id),
        speaker: "seller",
        text: event.text as string | null,
        interrupted: false,
      });
    } else if (event.type === "finalized") {
      this.finalized = true;
      this.cleanup();
      this.events.result(event.result as CallResult);
      if (this.playbackFailure) this.events.status(this.playbackFailure);
      this.ws?.close();
    }
  }
  async start(product: Product) {
    try {
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error("میکروفون فقط روی localhost یا HTTPS در دسترس است.");
      this.ctx = new AudioContext({ sampleRate: 24000 });
      await this.ctx.resume();
      await this.ctx.audioWorklet.addModule("/static/capture.js");
      this.mic = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      if (this.disposed) {
        this.cleanup();
        return;
      }
      const created = await this.api<{ session_id: string; ws_path: string }>(
        "/api/calls",
        {
          request_id: crypto.randomUUID(),
          offer_id: product.product_id ? product.id : null,
          store: { id: product.store!.id, name: product.store!.name },
          product: {
            id: product.product_id || product.id,
            name: product.name,
            attributes: product.attributes,
          },
          questions: ["availability", "price"],
          language: "fa-IR",
        },
      );
      this.id = created.session_id;
      if (this.disposed) {
        await this.end();
        this.cleanup();
        return;
      }
      this.streaming = true;
      this.events.active(true);
      this.events.status("در حال اتصال؛ هنوز مکالمه شروع نشده است…");
      this.ws = new WebSocket(
        `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}${created.ws_path}`,
      );
      this.ws.onmessage = ({ data }) => {
        void this.handle(JSON.parse(data)).catch((error: Error) => {
          this.playbackFailure = error.message;
          this.events.status(error.message);
          this.send({ type: "playback_error" });
          this.cleanup();
        });
      };
      this.ws.onerror = () => {
        this.events.status("خطای اتصال؛ برقراری تماس تأیید نشد.");
        this.cleanup();
      };
      this.ws.onclose = () => {
        this.cleanup();
        if (!this.finalized && !this.disposed)
          void this.waitResult()
            .then((result) => {
              if (!this.disposed) {
                this.finalized = true;
                this.events.result(result);
                if (this.playbackFailure) this.events.status(this.playbackFailure);
              }
            })
            .catch((error: Error) => {
              if (!this.disposed) this.events.status(error.message);
            });
      };
    } catch (error) {
      if (this.id)
        try {
          await this.api(`/api/calls/${this.id}/end`, {});
        } catch {
          /* Preserve original error. */
        }
      this.cleanup();
      throw error;
    }
  }
  async end() {
    this.stopCapture();
    this.send({ type: "end" });
    if (this.id) await this.api(`/api/calls/${this.id}/end`, {});
    if (!this.disposed) this.events.status("در حال نهایی‌سازی متن و نتیجه…");
  }
  dispose() {
    this.disposed = true;
    this.send({ type: "end" });
    if (this.id && !this.finalized)
      void this.api(`/api/calls/${this.id}/end`, {}).catch(() => {});
    this.cleanup();
    this.ws?.close();
  }
}
