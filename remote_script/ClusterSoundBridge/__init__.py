# -*- coding: utf-8 -*-
"""ClusterSoundBridge: MIDI Remote Script for Ableton Live 10 (Python 2.7) that loads .adg presets for the
ClusterSound Max for Live device, which the Live API available to Max cannot do.

Install: copy this folder to ~/Music/Ableton/User Library/Remote Scripts/, restart Live and pick
"ClusterSoundBridge" as a Control Surface in Preferences > Link/MIDI (Input and Output: None).
"""
from __future__ import absolute_import


def create_instance(c_instance):
    from .bridge import ClusterSoundBridge
    return ClusterSoundBridge(c_instance)
