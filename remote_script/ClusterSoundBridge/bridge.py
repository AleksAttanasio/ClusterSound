# -*- coding: utf-8 -*-
"""The control surface: a non-blocking UDP socket polled on every display update (~100 ms)."""
from __future__ import absolute_import

import socket

import Live
from _Framework.ControlSurface import ControlSurface

from . import protocol

RETRY_TICKS = 3     # schedule_message ticks are ~100 ms
MAX_TRIES = 15      # a freshly written preset can take a moment to show up in the browser


class ClusterSoundBridge(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._sock = None
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
            if msg is not None:
                self._handle(msg)

    # ------------------------------------------------------------------ commands
    def _reply(self, msg, ok, **kw):
        out = dict(kw, id=msg.get("id"), cmd=msg.get("cmd"), ok=ok)
        try:
            self._sock.sendto(protocol.osc_encode(out), ("127.0.0.1", protocol.OUT_PORT))
        except (socket.error, AttributeError) as e:
            self.log_message("ClusterSoundBridge: reply failed: %s" % e)

    def _handle(self, msg):
        cmd = msg.get("cmd")
        if cmd == "ping":
            self._reply(msg, True, version=1)
        elif cmd == "load":
            self._load(msg, 0)
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
        item = protocol.find_item(browser.user_folders, msg.get("place", ""))
        if item is None or not item.is_loadable:
            if tries < MAX_TRIES:
                self.schedule_message(RETRY_TICKS, lambda: self._load(msg, tries + 1))
            else:
                self._reply(msg, False, error="preset non trovato nei Places: %s" % msg.get("place"))
            return
        track = tracks[idx]
        song.view.selected_track = track
        browser.load_item(item)
        self._reply(msg, True, track=tracks.index(track))
