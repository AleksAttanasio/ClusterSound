// Web Audio player. The AudioContext is unlocked on the first user gesture; after that,
// playback can start from async callbacks (WKWebView would block <audio>.play() there).

export class Player {
  constructor({ onState }) {
    this.ctx = null;
    this.buffers = new Map(); // id -> AudioBuffer (small LRU)
    this.src = null;
    this.id = -1;
    this.startedAt = 0;
    this.offset = 0;
    this.playing = false;
    this.listeners = new Set(onState ? [onState] : []);
    const unlock = () => this._ensure().resume();
    window.addEventListener('pointerdown', unlock, true);
    window.addEventListener('keydown', unlock, true);
  }

  _ensure() {
    if (!this.ctx) this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    return this.ctx;
  }

  async load(id, fetchDataUrl) {
    if (this.buffers.has(id)) return this.buffers.get(id);
    const url = await fetchDataUrl(id);
    if (!url) return null;
    const b64 = url.slice(url.indexOf(',') + 1);
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const buf = await this._ensure().decodeAudioData(bytes.buffer);
    this.buffers.set(id, buf);
    if (this.buffers.size > 30) this.buffers.delete(this.buffers.keys().next().value);
    return buf;
  }

  play(id, buffer, offset = 0) {
    this.stop(false);
    const ctx = this._ensure();
    if (ctx.state !== 'running') ctx.resume();
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);
    src.onended = () => {
      if (this.src === src) { this.src = null; this.playing = false; this._emit(false, true); }
    };
    src.start(0, Math.min(offset, buffer.duration));
    this.src = src;
    this.id = id;
    this.offset = offset;
    this.startedAt = ctx.currentTime;
    this.playing = true;
    this._emit(true);
  }

  // listeners get (playing, id, ended): ended = the sound reached its end (not stopped)
  subscribe(fn) { this.listeners.add(fn); }
  _emit(playing, ended = false) { for (const fn of this.listeners) fn(playing, this.id, ended); }

  stop(notify = true) {
    if (this.src) {
      const s = this.src;
      this.src = null;
      try { s.stop(); } catch (e) { /* already stopped */ }
    }
    if (this.playing) {
      this.playing = false;
      if (notify) this._emit(false);
    }
  }

  // Seconds between a sample being scheduled (ctx.currentTime) and reaching the speakers: system buffers,
  // Bluetooth headphones… (often 50-250 ms on macOS). Playheads following ctx.currentTime run ahead of the sound.
  latency() {
    const ctx = this.ctx;
    if (!ctx) return 0;
    let lat = (ctx.baseLatency || 0) + (ctx.outputLatency || 0);
    if (!ctx.outputLatency && ctx.getOutputTimestamp) { // WebKit: no outputLatency, but the output timestamp
      const ts = ctx.getOutputTimestamp();
      if (ts.contextTime > 0 && ts.performanceTime > 0)
        lat = ctx.currentTime - (ts.contextTime + (performance.now() - ts.performanceTime) / 1000);
    }
    return Math.min(1, Math.max(0, lat));
  }

  // AudioContext time of what is heard now
  heardTime() { return this.ctx ? this.ctx.currentTime - this.latency() : 0; }

  // position in the buffer of what is heard now
  get currentTime() {
    return this.playing ? this.offset + Math.max(0, this.heardTime() - this.startedAt) : 0;
  }
}
