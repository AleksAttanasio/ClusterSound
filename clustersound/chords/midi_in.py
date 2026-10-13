"""MIDI keyboard input for recording a melody in Compose.

The web view (WKWebView) has no Web MIDI, so notes are read here with python-rtmidi, an optional dependency
(`pip install clustersound[midi]`). Times are seconds from start(); the UI converts them to ticks knowing
when its transport started.
"""
import threading
import time

from ..i18n import tr

try:
    import rtmidi
except ImportError:  # optional
    rtmidi = None

HINT = "To record from the keyboard install python-rtmidi: pip install python-rtmidi"


class Recorder:
    def __init__(self):
        self._in = None
        self._lock = threading.Lock()
        self._t0 = 0.0
        self._open: dict[int, tuple[float, int]] = {}
        self._notes: list[tuple[float, float, int, int]] = []

    @staticmethod
    def available() -> bool:
        return rtmidi is not None

    def ports(self) -> list[str]:
        if rtmidi is None:
            return []
        m = rtmidi.MidiIn()
        try:
            return m.get_ports()
        finally:
            m.close_port()
            del m

    @property
    def recording(self) -> bool:
        return self._in is not None

    def start(self, port: int = 0) -> None:
        if rtmidi is None:
            raise RuntimeError(HINT)
        self.stop()
        m = rtmidi.MidiIn()
        names = m.get_ports()
        if not names:
            raise RuntimeError(tr("No MIDI keyboard connected"))
        m.open_port(max(0, min(len(names) - 1, int(port))))
        with self._lock:
            self._open, self._notes = {}, []
            self._t0 = time.monotonic()
        m.set_callback(self._on_message)
        self._in = m

    def _on_message(self, event, _data=None):
        msg, _ = event
        self.feed(msg, time.monotonic() - self._t0)

    def feed(self, msg: list[int], t: float) -> None:
        """One raw MIDI message at t seconds from start (also used by the tests)."""
        if len(msg) < 3:
            return
        kind, pitch, vel = msg[0] & 0xF0, msg[1], msg[2]
        with self._lock:
            if kind == 0x90 and vel > 0:
                if pitch in self._open:  # retrigger without note-off
                    s, v = self._open.pop(pitch)
                    self._notes.append((s, t, pitch, v))
                self._open[pitch] = (t, vel)
            elif kind == 0x80 or (kind == 0x90 and vel == 0):
                if pitch in self._open:
                    s, v = self._open.pop(pitch)
                    self._notes.append((s, t, pitch, v))

    def stop(self) -> list[tuple[float, float, int, int]]:
        """Close the port; (start s, end s, pitch, vel) of every note, held notes end now."""
        m, self._in = self._in, None
        if m is not None:
            m.cancel_callback()
            m.close_port()
            del m
        with self._lock:
            now = time.monotonic() - self._t0
            notes = self._notes + [(s, now, p, v) for p, (s, v) in self._open.items()]
            self._open, self._notes = {}, []
        return sorted(notes)


def to_ticks(notes, offset: float, bpm: float, ppq: int, length_ticks: int | None = None):
    """Seconds from the recorder start -> ticks from the transport start (offset: seconds between the two).
    With length_ticks (a looped take) later passes fold back onto the loop."""
    tps = bpm / 60 * ppq
    out = []
    for s, e, p, v in notes:
        a, b = round((s - offset) * tps), round((e - offset) * tps)
        if b <= 0:
            continue
        a = max(0, a)
        if length_ticks:
            k = a // length_ticks
            a, b = a - k * length_ticks, min(b - k * length_ticks, length_ticks)
        out.append((a, max(a + 1, b), p, v))
    return out
