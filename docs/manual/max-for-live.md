# Max for Live

The **ClusterSound** device (MIDI effect, Live 10.1 Suite or later) imports patterns, sequences, drum racks and
progressions into the set, without dragging files. Installation: [Quick start › Ableton Live](../guide/ableton-live.md).

## Importing

With the app open:

- **From the device**: choose the kind (saved patterns, sequences, drum racks, progressions) and the item, then
  *Import*. *Refresh* reads the catalogue again.
    - a pattern creates the *Drums* and *Bass* tracks, each with its own rack and clip;
    - a sequence does the same with a clip as long as the sequence;
    - a drum rack creates a track with the rack;
    - a progression creates a *Chords* track (one clip per version) and a *Melody* track if there is one.
- **From the app**: *Send to Live* in the Sequencer, in the sequence bar, in the Drum Rack, in the Recorder and in
  Compose's *Export* menu. With **Receive** on the device imports straight away, even what is not saved.
- **Clip → Melody**: sends the notes of the selected MIDI clip to the app (Compose → Melody → *Import ▾ → Clip
  from Ableton*).

Rules: *New tracks* (default) creates them after the selected one; *Tempo* sets the BPM of the set; the clips start
from the selected scene and always go into an empty slot, without overwriting anything. Without the Remote Script
the clips are created anyway and the device shows the rack to drag from the browser.

## Trying Live instruments

In the right column of the device:

- **Track**: the tracks of the last import; for *Drums* also an entry per bus (*Drums › Kick*…).
- **Type**: the categories of Live's Sounds (Bass, Pad, Piano & Keys, Synth Lead…), the drum kits, the presets of
  every instrument (Operator, Wavetable, Analog…) and, for the buses, the hits of that bus.
- **Instrument**: the presets of the type, 60 at a time. Choosing one, or scrolling with **◀ ▶**, loads it and
  starts the clip in a loop; **Try ▶** loads it again, **Stop** stops.
- **★ ClusterSound sample** (or *ClusterSound kit*) puts the app's samples back.

Tracks that arrive without an instrument get the first preset of their type (*Piano & Keys* for the chords,
*Bass* for the bass, a kit for the drums), so every import plays straight away.

## Sequences and kits

Saving a sequence also saves the Sequencer kit, and the device imports it with that kit. For older sequences it
uses the user pattern of the first block, or only the MIDI (*(MIDI only)*) if the block comes from a genre preset;
failing that it uses the kit open now (*(current kit)*).

If something does not load, the reason is in the device status and in Live's `Log.txt` (`ClusterSoundBridge`
lines). Protocol and architecture: [Technical › Live integration](../technical/live-integration.md).
