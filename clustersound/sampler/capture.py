"""Record what the Mac is playing (or an audio input) into a ring buffer of the last N seconds.

System audio comes from ScreenCaptureKit (macOS 13+, "Screen & System Audio Recording" permission);
nothing is decrypted or bypassed, and apps that protect their stream simply deliver silence. Audio
inputs (a loopback device such as BlackHole, an interface, a microphone) go through sounddevice.
Both are optional: pip install "clustersound[capture]".

Recordings are for personal use (private copy): the UI says so, and exports carry a .source.txt.
"""
import threading
import time

import numpy as np

from .session import SamplerSession, from_array

DEFAULT_BUFFER_SECONDS = 60
SYSTEM = "system"
SCK_RATE = 48000


class CaptureError(Exception):
    """A user-presentable capture problem (missing permission, unavailable backend, …)."""


class RingBuffer:
    def __init__(self, seconds: float, sr: int, channels: int = 2):
        self.sr, self.channels = int(sr), int(channels)
        self.size = max(1, int(seconds * sr))
        self.buf = np.zeros((self.size, self.channels), dtype=np.float32)
        self.pos = 0       # next write index
        self.filled = 0    # valid frames
        self.level = 0.0   # RMS of the last block
        self._lock = threading.Lock()

    def write(self, block: np.ndarray) -> None:
        block = np.asarray(block, dtype=np.float32)
        if block.ndim == 1:
            block = block[:, None]
        if block.shape[1] != self.channels:
            block = np.repeat(block[:, :1], self.channels, axis=1) if block.shape[1] == 1 else block[:, :self.channels]
        if block.shape[0] > self.size:
            block = block[-self.size:]
        n = block.shape[0]
        with self._lock:
            first = min(n, self.size - self.pos)
            self.buf[self.pos:self.pos + first] = block[:first]
            self.buf[:n - first] = block[first:]
            self.pos = (self.pos + n) % self.size
            self.filled = min(self.size, self.filled + n)
            self.level = float(np.sqrt(np.mean(block ** 2))) if n else 0.0

    def latest(self, seconds: float | None = None) -> np.ndarray:
        with self._lock:
            n = self.filled if seconds is None else min(self.filled, int(seconds * self.sr))
            idx = (self.pos - n + np.arange(n)) % self.size
            return self.buf[idx].copy()

    @property
    def seconds(self) -> float:
        return self.filled / self.sr


# ------------------------------------------------------------------ backends
def _sck():
    try:
        import CoreMedia
        import ScreenCaptureKit
        from Foundation import NSObject
    except ImportError:
        return None
    return CoreMedia, ScreenCaptureKit, NSObject


def _sounddevice():
    try:
        import sounddevice
    except (ImportError, OSError):
        return None
    return sounddevice


def _wait(start, timeout: float = 10.0):
    """Call an Objective-C async API taking a completion handler; returns the handler's arguments.

    Handlers run on a dispatch queue: they must return None and never raise (that aborts the process).
    """
    done, out = threading.Event(), {}

    def handler(*args):
        out["args"] = args
        done.set()

    start(handler)
    if not done.wait(timeout):
        raise CaptureError("ScreenCaptureKit non risponde")
    return out["args"]


_OUTPUT_CLASS = None
_active: "SystemAudioBackend | None" = None  # the backend receiving audio (one capture at a time)


def _output_class(NSObject):
    """The SCStreamOutput class, defined once: an Objective-C class name can be registered only once."""
    global _OUTPUT_CLASS
    if _OUTPUT_CLASS is None:
        class ClusterSoundAudioOutput(NSObject):
            def stream_didOutputSampleBuffer_ofType_(self, stream, sbuf, kind):
                try:
                    b = _active
                    if b is not None and kind == b.SCK.SCStreamOutputTypeAudio:
                        b._deliver(sbuf)
                except Exception:  # an exception here would abort the whole app
                    pass

        _OUTPUT_CLASS = ClusterSoundAudioOutput
    return _OUTPUT_CLASS


class SystemAudioBackend:
    """ScreenCaptureKit audio of the whole system (this app's own process excluded)."""
    sr = SCK_RATE
    channels = 2

    def __init__(self, on_block):
        mods = _sck()
        if mods is None:
            raise CaptureError("cattura dell'audio di sistema non disponibile: installa l'extra «capture»")
        self.CM, self.SCK, NSObject = mods
        self.on_block = on_block
        self.stream = None
        self._output = _output_class(NSObject).alloc().init()

    def _deliver(self, sbuf) -> None:
        CM = self.CM
        n = CM.CMSampleBufferGetNumSamples(sbuf)
        bb = CM.CMSampleBufferGetDataBuffer(sbuf)
        if not n or bb is None:
            return
        asbd = CM.CMAudioFormatDescriptionGetStreamBasicDescription(CM.CMSampleBufferGetFormatDescription(sbuf))
        flags, channels = asbd[2], asbd[6]
        size = CM.CMBlockBufferGetDataLength(bb)
        err, data = CM.CMBlockBufferCopyDataBytes(bb, 0, size, None)
        if err:
            return
        a = np.frombuffer(bytes(data), dtype=np.float32)
        if flags & 32:  # kAudioFormatFlagIsNonInterleaved: one plane per channel
            a = a[: n * channels].reshape(channels, n).T
        else:
            a = a[: n * channels].reshape(n, channels)
        self.on_block(a)

    def start(self) -> None:
        SCK, CM = self.SCK, self.CM
        content, err = _wait(SCK.SCShareableContent.getShareableContentWithCompletionHandler_)
        if content is None or not content.displays():
            raise CaptureError("permesso mancante: abilita ClusterSound in Impostazioni di Sistema → Privacy e "
                               "sicurezza → Registrazione schermo e audio di sistema, poi riavvia l'app"
                               + (f" ({err.localizedDescription()})" if err else ""))
        flt = SCK.SCContentFilter.alloc().initWithDisplay_excludingWindows_(content.displays()[0], [])
        cfg = SCK.SCStreamConfiguration.alloc().init()
        cfg.setCapturesAudio_(True)
        cfg.setExcludesCurrentProcessAudio_(True)
        cfg.setSampleRate_(self.sr)
        cfg.setChannelCount_(self.channels)
        cfg.setWidth_(2)  # video is mandatory: keep it as small and slow as possible
        cfg.setHeight_(2)
        cfg.setMinimumFrameInterval_(CM.CMTimeMake(1, 1))
        stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(flt, cfg, None)
        ok, err = stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self._output, SCK.SCStreamOutputTypeAudio, None, None)
        if not ok:
            raise CaptureError(f"impossibile avviare la cattura ({err})")
        global _active
        _active = self
        (err,) = _wait(stream.startCaptureWithCompletionHandler_)
        if err is not None:
            _active = None
            raise CaptureError(f"cattura rifiutata: {err.localizedDescription()}")
        self.stream = stream

    def stop(self) -> None:
        global _active
        if self.stream is not None:
            try:
                _wait(self.stream.stopCaptureWithCompletionHandler_, timeout=3)
            except CaptureError:
                pass
            self.stream = None
        if _active is self:
            _active = None


class InputBackend:
    """An audio input device (loopback driver, interface, microphone) via sounddevice."""

    def __init__(self, on_block, device: int):
        sd = _sounddevice()
        if sd is None:
            raise CaptureError("registrazione da ingresso audio non disponibile: installa l'extra «capture»")
        self.sd, self.device, self.on_block = sd, int(device), on_block
        info = sd.query_devices(self.device)
        self.channels = max(1, min(2, int(info["max_input_channels"])))
        self.sr = int(info["default_samplerate"])
        self.name = info["name"]
        self.stream = None

    def start(self) -> None:
        def cb(indata, frames, t, status):
            try:
                self.on_block(indata.copy())
            except Exception:
                pass
        try:
            self.stream = self.sd.InputStream(device=self.device, channels=self.channels, samplerate=self.sr,
                                              dtype="float32", callback=cb)
            self.stream.start()
        except Exception as e:
            self.stream = None
            raise CaptureError(f"impossibile aprire «{self.name}»: {e}") from e

    def stop(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None


def sources() -> list[dict]:
    """Capture sources this Mac offers right now."""
    out = []
    if _sck() is not None:
        out.append({"id": SYSTEM, "name": "Audio di sistema (tutto ciò che il Mac riproduce)"})
    sd = _sounddevice()
    if sd is not None:
        try:
            devices = sd.query_devices()
        except Exception:
            devices = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                out.append({"id": str(i), "name": d["name"]})
    return out


class SystemCapture:
    """One capture at a time, always keeping the last `seconds` of audio."""

    def __init__(self, seconds: float = DEFAULT_BUFFER_SECONDS):
        self.seconds = float(seconds)
        self.backend = None
        self.ring: RingBuffer | None = None
        self.source = None
        self.started_at = None
        self.error = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self.backend is not None

    def start(self, source: str = SYSTEM, seconds: float | None = None) -> dict:
        with self._lock:
            self._stop()
            if seconds:
                self.seconds = float(seconds)
            self.error = None
            ring_box: dict = {}
            on_block = lambda block: ring_box["ring"].write(block)  # noqa: E731
            try:
                backend = SystemAudioBackend(on_block) if source == SYSTEM else InputBackend(on_block, int(source))
                ring_box["ring"] = self.ring = RingBuffer(self.seconds, backend.sr, backend.channels)
                backend.start()
            except Exception as e:  # e.g. macOS 12: ScreenCaptureKit has no audio capture
                self.error = str(e) if isinstance(e, CaptureError) else f"cattura non disponibile ({e})"
                raise CaptureError(self.error) from e
            self.backend, self.source, self.started_at = backend, source, time.time()
        return self.status()

    def _stop(self) -> None:
        if self.backend is not None:
            self.backend.stop()
            self.backend = None

    def stop(self) -> dict:
        with self._lock:
            self._stop()
        return self.status()

    def status(self) -> dict:
        r = self.ring
        return {"running": self.running, "source": self.source, "buffer_seconds": self.seconds,
                "seconds": round(r.seconds, 2) if r else 0.0,
                "level": round(r.level, 4) if r and self.running else 0.0, "error": self.error}

    def grab(self, seconds: float | None = None) -> SamplerSession:
        """The last `seconds` (default: the whole buffer) as a sampler session."""
        r = self.ring
        if r is None or r.filled == 0:
            raise CaptureError("niente da prendere: avvia la cattura e fai suonare qualcosa")
        audio = r.latest(seconds)
        name = getattr(self.backend, "name", None) or ("audio di sistema" if self.source == SYSTEM else "ingresso audio")
        stamp = time.strftime("%Y-%m-%d %H.%M.%S")
        return from_array(audio, r.sr, origin="capture", title=f"Cattura {stamp}",
                          meta={"captured_at": stamp.replace(".", ":"), "device": name})
