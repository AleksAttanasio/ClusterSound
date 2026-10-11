# -*- coding: utf-8 -*-
"""The control surface: a non-blocking UDP socket polled on every display update (~100 ms)."""
from __future__ import absolute_import

import socket
import traceback

import Live
from _Framework.ControlSurface import ControlSurface

from . import protocol

RETRY_TICKS = 2     # schedule_message ticks are ~100 ms
MAX_TRIES = 40      # a freshly written preset can take a few seconds to show up in the browser


class ClusterSoundBridge(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._sock = None
        self._pools = {}   # type key -> [(BrowserItem, folder)] collected once per session
        self._items = {}   # id -> BrowserItem offered to the device
        self._next_id = 0
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.bind(("127.0.0.1", protocol.IN_PORT))
            self._sock.setblocking(0)
            self.log_message("ClusterSoundBridge: listening on %d" % protocol.IN_PORT)
        except socket.error as e:
            self._sock = None
            self.log_message("ClusterSoundBridge: cannot bind %d: %s" % (protocol.IN_PORT, e))
            self.show_message("ClusterSoundBridge: porta %d occupata" % protocol.IN_PORT)

    def disconnect(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        ControlSurface.disconnect(self)

    def update_display(self):
        ControlSurface.update_display(self)
        if self._sock is None:
            return
        for _ in range(16):
            try:
                data, _addr = self._sock.recvfrom(65536)
            except socket.error:
                return
            msg = protocol.parse(data)
            if msg is None:
                self._log("ignored packet (%d bytes)" % len(data))
                continue
            try:
                self._handle(msg)
            except Exception as e:
                self._log("error on %r:\n%s" % (msg, traceback.format_exc()))
                self._reply(msg, False, error="%s: %s" % (type(e).__name__, e))

    # ------------------------------------------------------------------ commands
    def _log(self, text):
        self.log_message("ClusterSoundBridge: %s" % text)

    def _reply(self, msg, ok, **kw):
        if msg.get("cmd") != "ping":
            brief = dict((k, ("%d items" % len(v)) if k == "items" else v) for k, v in kw.items())
            self._log("-> %s %s %s" % (msg.get("cmd"), "ok" if ok else "ERR", brief))
        out = dict(kw, id=msg.get("id"), cmd=msg.get("cmd"), ok=ok)
        try:
            self._sock.sendto(protocol.osc_encode(out), ("127.0.0.1", protocol.OUT_PORT))
        except (socket.error, AttributeError) as e:
            self.log_message("ClusterSoundBridge: reply failed: %s" % e)

    def _handle(self, msg):
        cmd = msg.get("cmd")
        if cmd != "ping":
            self._log("<- %r" % (msg,))
        if cmd == "ping":
            self._reply(msg, True, version=1)
        elif cmd == "load":
            self._load(msg, 0)
        elif cmd == "categories":
            self._categories(msg)
        elif cmd == "list":
            self._list(msg)
        elif cmd == "load_item":
            self._load_item(msg)
        else:
            self._reply(msg, False, error="comando sconosciuto: %s" % cmd)

    def _load(self, msg, tries):
        song = self.song()
        tracks = list(song.tracks)
        idx = int(msg.get("track", -1))
        if not -len(tracks) <= idx < len(tracks):
            self._reply(msg, False, error="traccia %d inesistente" % idx)
            return
        browser = Live.Application.get_application().browser
        path = msg.get("path") or msg.get("place", "")
        item = protocol.find_item(self._roots(browser, msg.get("root")), path)
        if item is None or not item.is_loadable:
            if tries < MAX_TRIES:
                self.schedule_message(RETRY_TICKS, lambda: self._load(msg, tries + 1))
            else:
                where = "User Library" if msg.get("root") == "user_library" else "Places"
                self._reply(msg, False, error="preset non trovato in %s: %s" % (where, path))
            return
        if tries:
            self._log("found %s after %d retries" % (path, tries))
        track = tracks[idx]
        if not self._midi(track, msg):
            return
        song.view.selected_track = track
        browser.load_item(item)
        self._reply(msg, True, track=tracks.index(track))

    def _track(self, msg):
        tracks = list(self.song().tracks)
        idx = int(msg.get("track", -1))
        return tracks[idx] if -len(tracks) <= idx < len(tracks) else None

    def _midi(self, track, msg):
        """Loading an instrument on an audio track makes Live create a new MIDI track: refuse instead."""
        if track.has_midi_input:
            return True
        self._reply(msg, False, error="«%s» non è una traccia MIDI" % track.name)
        return False

    def _categories(self, msg):
        """Types of instruments in Live's library, and the one to start from for each track role."""
        cats = protocol.categories(Live.Application.get_application().browser)
        keys = [k for k, _ in cats]
        self._reply(msg, True, items=[{"key": k, "name": n} for k, n in cats], defaults=protocol.defaults(keys))

    def _list(self, msg):
        """One page of the presets of a type: {key, total, offset, items: [{id, name, folder}]}."""
        key = msg.get("key") or ""
        if key not in self._pools or msg.get("rescan"):
            self._pools[key] = protocol.category_pool(Live.Application.get_application().browser, key)
            self._log("%d presets in %s" % (len(self._pools[key]), key))
        pool = self._pools[key]
        offset = max(0, int(msg.get("offset", 0)))
        out = []
        for item, folder in pool[offset:offset + int(msg.get("limit", protocol.PAGE))]:
            self._next_id += 1
            self._items[self._next_id] = item
            out.append({"id": self._next_id, "name": protocol.display_name(item.name), "folder": folder})
        if not pool:
            self._reply(msg, False, error="nessuno strumento in questa categoria")
            return
        self._reply(msg, True, key=key, total=len(pool), offset=offset, items=out)

    def _load_item(self, msg):
        track = self._track(msg)
        item = self._items.get(int(msg.get("item", 0)))
        if track is None or item is None:
            self._reply(msg, False, error="traccia o strumento non validi")
            return
        if not self._midi(track, msg):
            return
        browser = Live.Application.get_application().browser
        song = self.song()
        song.view.selected_track = track
        if msg.get("pad") is not None:
            if not self._load_on_pad(track, int(msg["pad"]), item, browser, msg):
                return
        else:
            browser.load_item(item)
        self._reply(msg, True, name=protocol.display_name(item.name))

    def _load_on_pad(self, track, note, item, browser, msg):
        """Replace what a Drum Rack pad plays (a sample or a Simpler preset) through the browser's hotswap."""
        rack = next((d for d in track.devices if d.can_have_drum_pads), None)
        if rack is None:
            self._reply(msg, False, error="nessun Drum Rack su «%s»" % track.name)
            return False
        pad = rack.drum_pads[note]
        self.song().view.select_device(rack)
        rack.view.selected_drum_pad = pad
        try:
            browser.hotswap_target = pad
        except Exception as e:  # older APIs: loading goes to the selected pad of the selected rack
            self._log("hotswap_target on pad %d: %s" % (note, e))
        browser.load_item(item)
        try:
            browser.hotswap_target = None
        except Exception:
            pass
        return True

    @staticmethod
    def _roots(browser, root):
        """Browser items to search: the User Library's top folders and/or the Places, preferred one first."""
        library = list(browser.user_library.children)
        places = list(browser.user_folders)
        return library + places if root != "places" else places + library
