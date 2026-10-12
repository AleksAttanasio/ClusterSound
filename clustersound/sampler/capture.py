"""Fallback system audio capture through ScreenCaptureKit (macOS 13+), used by the Recorder for
"all outputs" when the cs-tap helper (Core Audio process taps, macOS 14.2+) is not available.

Needs the "Screen & System Audio Recording" permission and pip install "clustersound[capture]".
Nothing is decrypted or bypassed: apps that protect their stream simply deliver silence.
"""
import threading

import numpy as np

SCK_RATE = 48000


class CaptureError(Exception):
    """A user-presentable capture problem (missing permission, unavailable backend, …)."""


# ------------------------------------------------------------------ backends
def _sck():
    try:
        import CoreMedia
        import ScreenCaptureKit
        from Foundation import NSObject
    except ImportError:
        return None
    return CoreMedia, ScreenCaptureKit, NSObject


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

    @staticmethod
    def available() -> bool:
        return _sck() is not None

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
