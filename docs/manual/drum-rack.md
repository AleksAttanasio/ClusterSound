# Drum Rack

Builds kits of similar samples for two instruments: an **8×8 controller** (Novation Launchpad Pro) or a **Roland
SPD-SX**. The menu at the top left chooses the instrument; each one has its own kit.

![8×8 Drum Rack](../assets/screenshots/drum-rack.png){ .shot }

## 8×8 controller

- **Layouts**: they split the 64 pads into groups of similar samples; the pads stay in place when the layout
  changes.
    - *Columns ×8*: 8 columns of 8 (e.g. all the hats on one column);
    - *Blocks 2×2*: 16 groups of 4;
    - *Blocks 4×4*: 4 quadrants of 16;
    - *4×4 in columns*: every quadrant is a family, every column a group of 4;
    - *Free*: one pad at a time.
- **Note mapping** (Settings › Drum Rack): *Launchpad / Live* (four 4×4 blocks of notes; by default as the
  Launchpad plays them: 52–67 top left, 84–99 top right, 36–51 bottom left, 68–83 bottom right) or
  *sequential rows* (36 + row×8 + column) for Custom Modes. **Arrange blocks…** opens a window where the four
  blocks, shown by their notes, are dragged to match your controller; *Live* puts them back as Live shows
  them (68–83 and 84–99 above 36–51 and 52–67).
- **Groups** (panel on the right): family, choke group (on by default for the hats), 🔒 *Lock group*.
  Drag pads to swap them and a sample from the browser to put it on a pad; right-click = pad menu.

## Filling the groups

The **seed** is the last sample clicked (in the browser on the left, on a pad, or from the Library with *Send →
Drum Rack*). **Fill group** puts the seed on the selected pad and similar samples on the other pads of the group.

| Mode | What it does |
|---|---|
| *Most similar* | the closest to the seed, without duplicates |
| *Random* | picks among the similar ones with a **variation** slider; *Regenerate* draws again |
| *Manual* | you tick the similar ones from a list sorted by similarity |
| *Trail* | uses the stops of the Library's *Find similar*, completed with the similar ones of the last stop |

- **Similar among**: same class as the seed, family of the group or the whole library; *One-shots only*; *Avoid
  samples already in the kit*.
- **Auto-fill**: fills the empty groups by family (`Alt`+click regenerates every unlocked one).
- **🎲 Random**: every unlocked group takes a random group of similar samples of its family; it can be limited to
  a folder or pack, to one-shots, and match the dynamics.

## Roland SPD-SX

![SPD-SX kit](../assets/screenshots/drum-rack-spdsx.png){ .shot }

- **Pads** drawn as on the instrument: 1–3 at the top, 4–9 below, plus **Pedal (Trig 1)** and **Trig 2**, turned on
  with their tick. The pedal gets a kick; without the pedal the kick goes on pad 8.
- Factory **MIDI notes**: pads 1–9 = 60–68, Trig 1 = 69, Trig 2 = 70.
- **Configurations**: *Classic kit*, *Rows*, *Columns*, *Cross*, *Percussion*, *Free*.
- **Playability**: at most 2 kicks (pedal + 1 pad), 3 snares/claps and 5 among hats and cymbals. The families that
  would exceed the limits are disabled; if the kit exceeds them a warning appears.
- **🎲 Generate kit**: a random playable configuration, with every group taken from a group of sounds that no one
  else uses (the pedal kick and a pad kick sound different).

## Exporting and using

- **→ Sequencer**: loads the samples into the Sequencer buses by class, up to 8 per bus; choose which buses,
  whether to overwrite/add/clear the others, and the alternation (default *random*, except kick, FX and bass).
- **Export for Ableton** (8×8): `Samples/<group>/<note> - <name>.wav`, `… Drum Rack.adg` (Launchpad notes and
  choke groups), `.license.txt` of the online samples and `README.txt` with the pad map.
- **Export (Live + SPD-SX)**: `… SPD-SX Drum Rack.adg` on the SPD-SX notes, the `SPD-SX/` folder with 16-bit /
  44.1 kHz WAVs (`P1 - …` … `T2 - …`) to import with SPD-SX Wave Manager, and `README.txt`.
- **Send to Live**, **Save** / **Load kit**.

How the samples are chosen: [Algorithms › Drum Rack](../algorithms/drum-rack.md).
