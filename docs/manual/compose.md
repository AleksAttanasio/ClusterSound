# Compose

Builds **chord progressions** with the MIDI clips of a chord pack. The app ships a **built-in pack**, generated
for all 12 keys (triads, extended chords, borrowed and modal chords, progressions), used by default. If you own a
pack organised like the **Unison MIDI Chord Pack**, choose its folder in Settings › Compose (*Use built-in* goes
back). The pack is never modified: the files are read and indexed in memory.

![Compose: Harmony view](../assets/screenshots/compose-harmony.png){ .shot }

## Chord browser

- The chords of the chosen key, grouped by **degree** (I, ii, bVII…) and coloured by **function**: green tonic,
  blue subdominant, orange dominant, purple colour/modal borrowing.
- *Triads*, *Extended*, *Borrowed & modal*, *Progressions* filters and search by name or degree.
- Click: listen · double-click, **+** or drag onto the timeline: add. The pack's progressions come in as one block
  per chord. Keys or categories missing from the pack are transposed from the nearest one.

## Key

The key is chosen at the top of the chord browser (tonic, *Major*/*Minor*), with the lock next to it.

- **🔒 Locked**: shows only the chords of that key; changing it transposes the whole progression.
- **🔓 Unlocked**: the key only changes the chords browsed, from any key, each transposable ±12 semitones.
  Locking again makes the key shown the key of the progression.
- In both cases the key of the progression is the reference for degrees and suggestions.

## Timeline

Grid (1 bar … 1/16) in the toolbar; length in **Bars** at the right of the version tabs, separate for every
version. Drag a block to move it, its right edge to change its length:
the following chords slide instead of overlapping. *⇔ Spread evenly* gives all of them the same length. Every
block shows the notes that really play (after strum, arpeggios and rhythm). Versions **A, B, C…** in the tabs
above the timeline.

## Next chord

Suggestions for the selected chord (or the last one), with a score and the reasons: harmonic function, cadences
(V → I, ii → V, deceptive, plagal, bVI → bVII…), bass motion, common notes, voice leading and how often the move
appears in the pack's progressions. If there is already a chord after the block, it also counts how well the
suggestion leads into it. Under every proposal the colour variants of the same degree. Full formula in
[Algorithms › Harmony](../algorithms/harmony.md#next-chord).

## Playing style

Per chord or as the default of the sequence (*Mode*):

- *Block*, *Strum* (↑, ↓ or alternate, 5–80 ms), *Arpeggio* (up, down, up-down, random; 1/4…1/16 and triplets;
  1–2 octaves);
- *Rhythm* (quarter notes, eighth notes, offbeat, charleston, tresillo, syncopated house, half notes, pulse 1/16)
  played as block or strum;
- note length, swing, dynamics curve, **humanize** (timing, velocity, feel, drift… 🎲 redraws it) and
  **Alternation** of styles on every hit or bar.

Preview and export use the same events, computed in Python.

## Variations

- **Of a chord** (*✦ Vary harmony…* or `V`): voicing (inversions, drop-2, open/close, doubled bass, minimal voice
  leading from the previous chord), colour (same degree, different extensions), substitutions in context, playing
  styles. ▶ plays the proposal from the bar before.
- **Of the progression** (*✦* on the version tab): reharmonisation (first and last chord stay), harmonic rhythm
  (anticipations, long-short, split chords), voice leading, richer / sparser, playing style and ending
  (IV → V, bVI → bVII, IV → iv, ii → V…), with a *How much to vary* slider. *Keep* saves it as a new version,
  *Append* adds it at the end.

## Exporting

The toolbar has two rows: *Harmony*/*Melody*, name, *Open…*, *Save* and **Send to ▾** above; stop, play/pause, loop, undo/redo, BPM,
grid, melody on/mute and *Pattern* below. **Send to ▾** offers:

- **Sequencer**: the roots of the chords become the bass line of the Sequencer pattern (one note per chord), which
  takes key, BPM and bars of the progression (1, 2 or 4: longer progressions send the first 4 bars). It asks
  before replacing a bass line already there.
- **Export for Ableton**: one `.mid` (type 0, 480 PPQ, with the tempo) for the current version or one per version;
  *chords only* exports the block voicings without style. With a melody: *Chords + melody* (type 1), *Chords only*
  or *Melody only*.
- **Ableton Live**: *Chords* track with one clip per version, plus one track per melody layer.
- **Pattern**: plays the progression together with the Sequencer pattern.
- *Save* / *Open…* keep the progressions with all their versions; `⌘Z` / `⇧⌘Z` undo and redo.

Shortcuts: `Space` play/pause, `←` `→` previous/next chord, `Del` delete, `⌘D` duplicate, `V` variations.
