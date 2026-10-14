# Melody

In Compose, **Harmony | Melody** switches view. Every version (A, B, C…) has its own melody, which plays together
with the chords in both views (♫ in the bar mutes it).

![Compose: Melody view](../assets/screenshots/compose-melody.png){ .shot }

## Layers

The melody is made of one or more **layers** over the same chords — *Melody*, *Bass*, *Arpeggio*, *Riff*, *Pad*,
*Keys* — each with its own sound and colour.

- *＋ Layer ▾* adds an empty one; click on the name makes it active (the others show in transparency); double-click
  renames it; **M** mutes it; ✕ deletes it.
- Two sliders: volume of the active layer and of all the layers.

## Piano roll

The rows of the scale are lighter and under every chord its notes are highlighted.

- Click on an empty space: new note (drag to lengthen it); drag a note to move it, its right edge to lengthen it,
  `Alt`+drag for the velocity; double-click deletes it.
- `↑` `↓` transpose (`⇧` by an octave), `←` `→` move, `⌘D` duplicates, `⌘A` selects all; *−8va* / *+8va*.

## Import

- **MIDI file**: the highest note of every chord, quantised.
- **Ableton clip**: in the device press *Clip → Melody* with a MIDI clip selected.
- **MIDI keyboard**: 4 count-in clicks, then you play over the progression (needs the `midi` extra).

If the version has no chords, the key is detected from the melody.

## Generate from the chords

Choose *Type*, *Density*, contour or style and range (it sets itself to the register of the type), then
**Generate**:

| Type | What it generates |
|---|---|
| *Melody* | contour (arch, rising, falling, wave); chord notes on the strong beats, scale notes in between; 2–4 bar phrases with an answer |
| *Bass* | style (roots, octaves, fifths, walking); root on the first beat and an approach note to the next chord |
| *Arpeggio* | direction (rising, falling, up and down, random) over the chord notes, in quarters, eighths or sixteenths |
| *Riff* | a one-bar cell that follows the chords, varied every 4 bars |
| *Pad* / *Keys* | chords with smooth voicings, held or rhythmic |

*Only over the selected chords* regenerates only those bars. ▶ listens with the other layers, **Use** replaces the
active layer (if of the same type), **＋ Layer** adds the line as a new layer.

## Chords from the melody

**Harmonise** (from the active layer): one chord per bar, two, or as many as needed, chosen among those of the pack
that contain the notes of the melody and chained with the same criteria as the suggestions. The key can be the one
of the version or detected from the melody; optionally borrowed chords too. *New version* adds a version with
chords and melody, *Replace* changes the chords of the current version.

Generation and harmonisation algorithms: [Algorithms › Melody](../algorithms/melody.md).
