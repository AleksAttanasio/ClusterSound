"""Recorder backend for Windows: WASAPI loopback of an output device, through the `soundcard` library.

Loopback records what Windows sends to one output (this app's own sound included: WASAPI cannot exclude a
process). There is no mix of every output as on the Mac: the "mix" entry is the default output.
Nothing is decrypted or bypassed: apps that protect their stream record silence.
"""
import ctypes
import sys
import threading
import warnings

from ..i18n import tr
from .capture import CaptureError

RATE = 48000  # shared-mode WASAPI converts to any rate; the Recorder resamples to the chosen one
BLOCK_FRAMES = 1024  # ~20 ms: stop() is noticed quickly


def _soundcard():
    try:
        import soundcard
    except Exception:  # ImportError, or the library failing to load its system DLLs
        return None
    return soundcard


def _com_init() -> None:
    """soundcard initializes COM only in the thread that imported it; every other thread needs its own."""
    if sys.platform == "win32":
        ctypes.windll.ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED; S_FALSE if already done


def output_devices(mix_id: str) -> list[dict]:
    """The default output (as the "mix" entry) followed by every output, in output_devices() format."""
    sc = _soundcard()
    if sc is None:
        return []
    _com_init()
    try:
        speakers = sc.all_speakers()
        default = sc.default_speaker()
    except Exception:
        return []
    default_id = getattr(default, "id", None)
    devices = [{"id": s.id, "name": s.name, "channels": int(s.channels), "sample_rate": None,
                "default": s.id == default_id, "backend": "wasapi"} for s in speakers]
    devices.sort(key=lambda d: (not d["default"], d["name"].lower()))
    if not devices:
        return []
    mix = {"id": mix_id, "name": tr("Default output"), "channels": 2, "sample_rate": None, "default": False,
           "backend": "wasapi", "note": tr("Everything that plays on the Windows default output")}
    return [mix] + devices


class LoopbackBackend:
    """One output device recorded through WASAPI loopback: float32 blocks (frames, channels) to on_block."""

    def __init__(self, device: str | None, on_block, timeout: float = 10.0):
        self.sc = _soundcard()
        if self.sc is None:
            raise CaptureError(tr("recording not available: install the «soundcard» package"))
        self.device, self.on_block, self.timeout = device, on_block, timeout  # device None: the default output
        self.sr, self.channels = RATE, 0
        self.error: str | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None

    def _microphone(self):
        sc = self.sc
        speaker = sc.default_speaker() if self.device is None else sc.get_speaker(self.device)
        return speaker, sc.get_microphone(speaker.id, include_loopback=True)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(self.timeout):
            self._stop.set()
            raise CaptureError(tr("the device is not responding"))
        if self.error:
            raise CaptureError(self.error)

    def _run(self) -> None:
        try:
            _com_init()
            speaker, mic = self._microphone()
            self.channels = max(1, int(speaker.channels))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # "data discontinuity": a dropped buffer, not worth a popup
                with mic.recorder(samplerate=self.sr, channels=self.channels, blocksize=BLOCK_FRAMES) as rec:
                    self._ready.set()
                    while not self._stop.is_set():
                        block = rec.record(numframes=BLOCK_FRAMES)
                        if len(block):
                            self.on_block(block.astype("float32", copy=False).reshape(len(block), -1))
        except Exception as e:  # opening errors reach start(); later ones stop this device only
            self.error = str(e) or type(e).__name__
        finally:
            self._ready.set()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(3)
            self._thread = None
