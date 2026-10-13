# Sequencer

A sequencer to **try samples on typical grooves** and take them into Ableton.

![Sequencer](../assets/screenshots/sequencer.png){ .shot }

## Genres and patterns

**47 genres, 191 patterns**, with bass music up front:

- *Bass music UK*: UK garage 2-step, speed garage, bassline, UK funky, grime, dubstep, riddim, tearout, halftime,
  breaks, future garage;
- *Drum & bass / jungle*: liquid, rollers, jump-up, neurofunk, dancefloor, jungle (amen), minimal, drumfunk,
  footwork;
- *Hip hop / trap*: boom bap, lo-fi, trap, UK and NY drill, phonk, memphis, jersey club, baltimore club;
- *House / techno*: house, deep, tech house, techno, minimal, electro, trance, hardstyle, disco;
- *Global*: afrobeats, amapiano, reggaeton/dembow, dancehall, moombahton, pop, funk, rock, breakbeat.

Every genre has its variants plus automatically generated *Fill* and *Breakdown*, with the BPM, swing and key of
the genre. **Vary** creates a variation of the groove; **Save variant** adds it to yours (★).

## Buses, steps and layers

- **Buses**: Kick, Snare, Clap, Rim, Closed Hat, Open Hat, Ride/Crash, Perc, Tom, FX and Bass, each with steps,
  volume, pan, filter, mute/solo and meter. 🔒 locks the bus against the random kit.
- **Steps**: click turns on/off, `Shift`+click accent, `Alt`+click ghost note, right-click roll ×2/×3/×4. Closed
  and open hi-hat choke each other.
- **Layers**: every bus can have several samples together (e.g. 3 snares), each with volume, pitch, offset in ms,
  mute/solo and optionally its own steps.
- **Layer alternation** (with 2+ layers): *together* (all on every hit), *in turn* (one after the other), *random*
  (a random one per hit, the same on every loop; ⚄ draws again), *random every loop* (a new draw on every
  repetition). The export records exactly what you hear.
- **Bass**: piano roll with glide (`Alt`+click on a note). The root note of the sample is detected automatically,
  so the bass plays in tune.

## Loading samples

- **Send** from the Library (right-click on a point or a row, or *Send ▾* in the drawer) and from the Store (→):
  as a new layer or in place of the selected one.
- **🎲 Random kit**: for every bus that plays it picks a group of similar samples (class + subcluster) and takes
  1, 2 or 4 of them (alternated at random). It can be limited to a folder or pack, keep only one-shots and match
  the dynamics. The groove stays the same.
- **▦ Load from the Drum Rack**: brings the Drum Rack samples into the buses of their class.
- Online samples stay in the **temporary cache** (300 MB, configurable) and become files only on export.

## Sequence (arrangement)

In the *Sequence* panel you build a running order of patterns, of different genres too:

- drag a variant chip (or double-click it), or *+ Current pattern*;
- cards are reordered by dragging and have ×N repetitions, duplicate, rename, delete; they are as wide as their
  bars and show a thumbnail of the groove;
- click on a card: the grid edits that block; *Play sequence* with *Follow* shows the block that is playing;
- kit and BPM are shared, the swing stays the one of each block;
- *Save…* / *Open…* manage the saved sequences (with the kit).

## Exporting

- **MIDI**: Drum Rack mapping (consecutive pads from C1) or General MIDI.
- **WAV** of the loop or of the sequence.
- **Export for Ableton**: a folder with `Samples/<Bus>/…wav` (plus `.license.txt` for online samples),
  `… Drum Rack.adg` (one pad per bus, nested Instrument Rack when the bus has several layers), `… Bass.adg`
  (mono Simpler with root note and glide), `Drums.mid`, `Bass.mid`, `Loop.wav` and `README.txt`.
- **Send to Live**: the same, imported directly by the device. Tested with Live 10.1.

How swing, rolls, alternation, Fill and rendering work: [Algorithms › Sequencer](../algorithms/sequencer.md).
