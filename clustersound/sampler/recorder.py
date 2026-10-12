"""Record what the Mac sends to one or more output devices, each into its own file, in several formats.

Each output device is read by cs-tap (clustersound/native/cs_tap.swift), a small helper built on Core Audio
process taps (macOS 14.2+). Without the helper, "all outputs" falls back to ScreenCaptureKit.
Nothing is decrypted or bypassed: apps that protect their stream record silence.
"""
import json
import os
import platform
import shutil
import subprocess
import threading
import time

import numpy as np
import soundfile as sf
import soxr

from ..online.downloads import safe_name, unique_path
from ..paths import resource_path
from .capture import CaptureError, SystemAudioBackend
from .export import CAPTURE_NOTE

DEFAULT_DIR = os.path.expanduser("~/Music/ClusterSound Recordings")
CACHE_BIN = os.path.expanduser("~/Library/Caches/ClusterSound/bin/cs-tap")
ALL = "all"
BLOCK_FRAMES = 2048

# quality: [(value, label)], first = default. "sf": soundfile format/subtype or compression level.
FORMATS = {
    "wav": {"label": "WAV", "ext": ".wav", "sf": "WAV", "multichannel": True,
            "qualities": [("PCM_24", "24 bit"), ("PCM_16", "16 bit"), ("FLOAT", "32 bit float")]},
    "aiff": {"label": "AIFF", "ext": ".aif", "sf": "AIFF", "multichannel": True,
             "qualities": [("PCM_24", "24 bit"), ("PCM_16", "16 bit")]},
    "flac": {"label": "FLAC", "ext": ".flac", "sf": "FLAC", "multichannel": True,
             "qualities": [("PCM_24", "24 bit"), ("PCM_16", "16 bit")]},
    "caf": {"label": "CAF", "ext": ".caf", "sf": "CAF", "multichannel": True,
            "qualities": [("PCM_24", "24 bit"), ("FLOAT", "32 bit float")]},
    "mp3": {"label": "MP3", "ext": ".mp3", "sf": "MP3", "multichannel": False,
            "qualities": [("320", "320 kbps"), ("256", "256 kbps"), ("192", "192 kbps"), ("128", "128 kbps")]},
    "ogg": {"label": "OGG Vorbis", "ext": ".ogg", "sf": "OGG", "multichannel": False,
            "qualities": [("high", "Alta"), ("medium", "Media"), ("low", "Bassa")]},
    "opus": {"label": "Opus", "ext": ".opus", "sf": "OGG", "multichannel": False, "rates": [48000],
             "qualities": [("default", "Standard")]},
    "m4a": {"label": "M4A (AAC)", "ext": ".m4a", "sf": None, "multichannel": False,
            "qualities": [("256", "256 kbps"), ("192", "192 kbps"), ("128", "128 kbps")]},
}
RATES = [(0, "Del dispositivo"), (44100, "44,1 kHz"), (48000, "48 kHz"), (96000, "96 kHz")]
CHANNELS = [("stereo", "Stereo"), ("mono", "Mono"), ("all", "Tutti i canali")]
# libsndfile maps the compression level onto these CBR bitrates (measured)
MP3_LEVEL = {"320": 0.0, "256": 0.2, "192": 0.42, "128": 0.65}
OGG_LEVEL = {"high": 0.1, "medium": 0.5, "low": 0.8}


def formats() -> dict:
    out = {k: {"label": v["label"], "ext": v["ext"], "multichannel": v["multichannel"], "qualities": v["qualities"],
               "rates": v.get("rates")} for k, v in FORMATS.items()}
    if not shutil.which("afconvert"):
        out.pop("m4a")
    return out


def normalize_format(fmt: dict | None) -> dict:
    """A complete, valid {format, quality, rate, channels} from whatever the UI sent."""
    fmt = fmt or {}
    key = fmt.get("format") if fmt.get("format") in formats() else "wav"
    spec = FORMATS[key]
    qualities = [q for q, _ in spec["qualities"]]
    quality = fmt.get("quality") if fmt.get("quality") in qualities else qualities[0]
    rate = int(fmt.get("rate") or 0)
    if spec.get("rates"):
        rate = spec["rates"][0]
    elif rate not in [r for r, _ in RATES]:
        rate = 0
    channels = fmt.get("channels") if fmt.get("channels") in [c for c, _ in CHANNELS] else "stereo"
    if channels == "all" and not spec["multichannel"]:
        channels = "stereo"
    return {"format": key, "quality": quality, "rate": rate, "channels": channels}


# ------------------------------------------------------------------ writer
class Writer:
    """Streams blocks to one file: channel mapping, optional resampling, encoding (M4A through afconvert)."""

    def __init__(self, path: str, fmt: dict, in_sr: int, in_channels: int):
        self.fmt = normalize_format(fmt)
        spec = FORMATS[self.fmt["format"]]
        self.path, self.in_sr = path, int(in_sr)
        self.channels = {"mono": 1, "stereo": min(2, in_channels), "all": in_channels}[self.fmt["channels"]]
        self.sr = self.fmt["rate"] or self.in_sr
        self.frames = 0  # input frames written
        self._resampler = soxr.ResampleStream(self.in_sr, self.sr, self.channels, dtype="float32") \
            if self.sr != self.in_sr else None
        self._final = None
        q = self.fmt["quality"]
        kw: dict = {}
        if self.fmt["format"] == "m4a":
            self._final, target = path, path + ".part.caf"
            kw = {"format": "CAF", "subtype": "FLOAT"}
        else:
            target = path
            kw = {"format": spec["sf"]}
            if self.fmt["format"] == "mp3":
                kw |= {"subtype": "MPEG_LAYER_III", "compression_level": MP3_LEVEL[q], "bitrate_mode": "CONSTANT"}
            elif self.fmt["format"] == "ogg":
                kw |= {"subtype": "VORBIS", "compression_level": OGG_LEVEL[q]}
            elif self.fmt["format"] == "opus":
                kw |= {"subtype": "OPUS"}
            else:
                kw |= {"subtype": q}
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._file = sf.SoundFile(target, "w", self.sr, self.channels, **kw)
        self._target = target
        self._lock = threading.Lock()

    def _map(self, block: np.ndarray) -> np.ndarray:
        if self.channels == 1:
            return block.mean(axis=1, keepdims=True)
        if block.shape[1] >= self.channels:
            return block[:, :self.channels]
        return np.repeat(block[:, :1], self.channels, axis=1)

    def write(self, block: np.ndarray) -> None:
        y = self._map(np.asarray(block, dtype=np.float32).reshape(len(block), -1))
        if self._resampler is not None:
            y = self._resampler.resample_chunk(y)
        with self._lock:
            if self._file is None:
                return
            self._file.write(np.clip(y, -1, 1))
            self.frames += len(block)

    @property
    def seconds(self) -> float:
        return self.frames / self.in_sr if self.in_sr else 0.0

    @property
    def bytes(self) -> int:
        try:
            return os.path.getsize(self._target)
        except OSError:
            return 0

    def close(self) -> str:
        with self._lock:
            if self._file is None:
                return self.path
            if self._resampler is not None:
                tail = self._resampler.resample_chunk(np.zeros((0, self.channels), np.float32), last=True)
                if len(tail):
                    self._file.write(np.clip(tail, -1, 1))
            self._file.close()
            self._file = None
        if self._final:
            bitrate = int(self.fmt["quality"]) * 1000
            res = subprocess.run(["/usr/bin/afconvert", "-f", "m4af", "-d", "aac", "-b", str(bitrate),
                                  self._target, self._final], capture_output=True, text=True)
            if res.returncode != 0:
                raise CaptureError(f"conversione in M4A non riuscita: {res.stderr.strip() or res.returncode}")
            os.remove(self._target)
        return self.path


# ------------------------------------------------------------------ helper
def _mac_supports_taps() -> bool:
    v = tuple(int(x) for x in (platform.mac_ver()[0] or "0").split(".")[:2] + ["0"])[:2]
    return v >= (14, 2)


def tap_binary(build: bool = True) -> str | None:
    """Path of cs-tap: bundled with the app, cached, or (from source, with swiftc) compiled on first use."""
    if not _mac_supports_taps():
        return None
    bundled = str(resource_path("bin/cs-tap"))
    if os.access(bundled, os.X_OK):
        return bundled
    src = str(resource_path("native/cs_tap.swift"))
    fresh = os.access(CACHE_BIN, os.X_OK) and (not os.path.exists(src) or
                                                os.path.getmtime(CACHE_BIN) >= os.path.getmtime(src))
    if fresh:
        return CACHE_BIN
    if not (build and os.path.exists(src) and shutil.which("swiftc")):
        return CACHE_BIN if os.access(CACHE_BIN, os.X_OK) else None
    os.makedirs(os.path.dirname(CACHE_BIN), exist_ok=True)
    res = subprocess.run(["swiftc", "-O", "-swift-version", "5", "-o", CACHE_BIN + ".tmp", src],
                         capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        return None
    os.replace(CACHE_BIN + ".tmp", CACHE_BIN)
    return CACHE_BIN


def output_devices() -> list[dict]:
    """Output devices that can be recorded; the first entry is the mix of all outputs."""
    binary = tap_binary()
    mix = {"id": ALL, "name": "Tutte le uscite (mix)", "channels": 2, "sample_rate": None, "default": False}
    if binary is None:
        return [mix | {"backend": "sck"}] if SystemAudioBackend.available() else []
    try:
        res = subprocess.run([binary, "list"], capture_output=True, text=True, timeout=10)
        devices = json.loads(res.stdout or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        devices = []
    devices.sort(key=lambda d: (not d.get("default"), d.get("name", "").lower()))
    return [mix] + [{"id": d["uid"], "name": d["name"], "channels": d["channels"],
                     "sample_rate": d["sample_rate"], "default": d["default"]} for d in devices]


class TapBackend:
    """One output device read through cs-tap: interleaved float32 blocks to on_block."""

    def __init__(self, device: str, on_block, binary: str | None = None, timeout: float = 10.0):
        self.binary = binary or tap_binary()
        if not self.binary:
            raise CaptureError("registrazione per dispositivo non disponibile (serve macOS 14.2 o successivo)")
        self.device, self.on_block, self.timeout = device, on_block, timeout
        self.sr, self.channels = 0, 0
        self.proc: subprocess.Popen | None = None
        self.error: str | None = None
        self._thread: threading.Thread | None = None

    def _stderr_error(self) -> str:
        try:
            text = self.proc.stderr.read().decode("utf-8", "replace").strip() if self.proc else ""
        except (OSError, ValueError):
            text = ""
        for line in reversed(text.splitlines()):
            try:
                return json.loads(line)["error"]
            except (ValueError, KeyError, TypeError):
                continue
        return text or "il registratore si è chiuso inatteso"

    def start(self) -> None:
        self.proc = subprocess.Popen([self.binary, "record", "--device", self.device, "--exclude-pid", str(os.getpid())],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        box: dict = {}
        reader = threading.Thread(target=lambda: box.setdefault("line", self.proc.stdout.readline()), daemon=True)
        reader.start()
        reader.join(self.timeout)
        line = box.get("line")
        if not line:
            if reader.is_alive():
                self.proc.kill()
                raise CaptureError("il registratore non risponde (controlla il permesso di registrazione audio)")
            self.proc.wait(2)
            raise CaptureError(self._stderr_error())
        head = json.loads(line)
        self.sr, self.channels = int(round(head["sample_rate"])), int(head["channels"])
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self) -> None:
        frame = 4 * self.channels
        pending = b""
        out = self.proc.stdout
        while True:
            chunk = out.read1(BLOCK_FRAMES * frame)
            if not chunk:
                break
            data = pending + chunk
            usable = len(data) - len(data) % frame
            pending = data[usable:]
            if usable:
                try:
                    self.on_block(np.frombuffer(data[:usable], dtype=np.float32).reshape(-1, self.channels))
                except Exception as e:  # a failing writer stops this device only
                    self.error = str(e)
                    break
        if self.proc and self.proc.poll() not in (None, 0) and not self.error:
            self.error = self._stderr_error()

    def stop(self) -> None:
        p = self.proc
        if p is None:
            return
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(3)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(2)
        if self._thread:
            self._thread.join(3)
        self.proc = None


# ------------------------------------------------------------------ recorder
class Track:
    def __init__(self, device: dict, path: str, fmt: dict):
        self.device, self.path, self.fmt = device, path, fmt
        self.backend = None
        self.writer: Writer | None = None
        self.level = 0.0
        self.error: str | None = None

    def on_block(self, block: np.ndarray) -> None:
        if self.writer is None:
            self.writer = Writer(self.path, self.fmt, self.backend.sr, block.shape[1])
        self.writer.write(block)
        self.level = float(np.sqrt(np.mean(block ** 2))) if block.size else 0.0

    def status(self) -> dict:
        w = self.writer
        err = self.error or getattr(self.backend, "error", None)
        return {"device": self.device["id"], "name": self.device["name"], "path": self.path,
                "seconds": round(w.seconds, 2) if w else 0.0, "bytes": w.bytes if w else 0,
                "level": round(self.level, 4), "error": err}


def source_text(name: str, started: str, seconds: float, fmt: dict) -> str:
    return (f"Registrazione dell'uscita audio: {name}\nInizio: {started}\nDurata: {seconds:.1f} s\n"
            f"Formato: {FORMATS[fmt['format']]['label']} · {fmt['quality']}\n\n{CAPTURE_NOTE}\n")


def _default_backend(device: dict, on_block):
    if device.get("backend") == "sck":
        return SystemAudioBackend(on_block)
    return TapBackend(device["id"], on_block)


class Recorder:
    """Several output devices at once, one file per device, started together."""

    def __init__(self, backend_factory=_default_backend):
        self.backend_factory = backend_factory
        self.tracks: list[Track] = []
        self.started_at: float | None = None
        self.started_label = ""
        self.recordings: list[dict] = []  # finished in this session, newest first
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self.started_at is not None

    def start(self, devices: list[dict], fmt: dict, folder: str = DEFAULT_DIR) -> dict:
        with self._lock:
            if self.running:
                raise CaptureError("una registrazione è già in corso")
            if not devices:
                raise CaptureError("scegli almeno un dispositivo di uscita")
            fmt = normalize_format(fmt)
            stamp = time.strftime("%Y-%m-%d %H.%M.%S")
            self.started_label = stamp.replace(".", ":")
            tracks = []
            for d in devices:
                path = unique_path(os.path.join(folder, f"{stamp} - {safe_name(d['name'])}{FORMATS[fmt['format']]['ext']}"))
                t = Track(d, path, fmt)
                try:
                    t.backend = self.backend_factory(d, t.on_block)
                    t.backend.start()
                except Exception as e:
                    t.error = str(e) if isinstance(e, CaptureError) else f"avvio non riuscito ({e})"
                    t.backend = None
                tracks.append(t)
            if all(t.backend is None for t in tracks):
                raise CaptureError("; ".join(f"{t.device['name']}: {t.error}" for t in tracks))
            self.tracks, self.started_at = tracks, time.time()
        return self.status()

    def status(self) -> dict:
        return {"running": self.running, "elapsed": round(time.time() - self.started_at, 1) if self.running else 0.0,
                "tracks": [t.status() for t in self.tracks], "recordings": self.recordings}

    def stop(self) -> dict:
        with self._lock:
            if not self.running:
                return self.status()
            for t in self.tracks:
                if t.backend:
                    t.backend.stop()
            for t in self.tracks:
                if not t.writer:
                    continue
                st = t.status()
                try:
                    path = t.writer.close()
                except CaptureError as e:
                    t.error = str(e)
                    continue
                with open(path + ".source.txt", "w", encoding="utf-8") as f:
                    f.write(source_text(t.device["name"], self.started_label, t.writer.seconds, t.fmt))
                self.recordings.insert(0, {"path": path, "name": os.path.basename(path), "device": t.device["name"],
                                           "seconds": st["seconds"], "format": FORMATS[t.fmt["format"]]["label"],
                                           "bytes": os.path.getsize(path), "error": st["error"]})
            self.started_at = None
        return self.status()
