# Sequencer and groove

Code: `patterns/model.py` (format and timing), `patterns/genres.py` (genres), `patterns/render.py` (audio),
`patterns/midi.py`, `patterns/arrange.py`, `patterns/ableton.py`; in JS `ui/pattern.js` and `ui/sequencer.js`.

## The model of a pattern

- **Grid**: 16 steps per bar, 96 PPQ, so **24 ticks per step** (a sixteenth note).
- **Buses**: 10 drum buses with one GM note each, plus the Bass bus.
- **Compact notation** in the genres: `X` = 127 (accent), `x` = 100, `o` = 55 (ghost), `2`/`3`/`4` = roll at velocity
  100, `.` = rest; a string shorter than the pattern is repeated. The bass uses `step:length:semitones` tokens with
  `g` = glide and `!` = accent (velocity 120).

### Swing

MPC-style swing on the odd sixteenths:

\[
\text{tick}(s) = 24\,s + \big[s \text{ odd}\big]\cdot\operatorname{round}\!\Big(\frac{\text{swing}}{100}\cdot 48 - 24\Big)
\]

At 50% no shift, at 75% the off-beat sixteenths come 12 ticks later (full shuffle). Sequences keep the swing of every
bar (`swing_bars`).

### Rolls

A ×*r* roll splits the step into *r* evenly spaced hits; the *k*-th has velocity \(v\,(1 - 0.12k)\), so it sounds like
a roll and not like a machine gun.

### Layer alternation

With 2+ layers sharing the steps of the bus, a single layer plays on every hit:

| Mode | Layer of hit *h* on step *s* |
|---|---|
| *in turn* | \(h \bmod n\) |
| *random* | \(\text{hash}(seed, s) \bmod n\) — the same choice on every loop |
| *random every loop* | \(\text{hash}(seed, s + \text{loop}\cdot N) \bmod n\) — a new choice on every repetition |

`hash` is a 32-bit integer hash (multiplication by 2654435761, xor-shift, multiplication by `0x45D9F3B`) **bit for
bit identical** in Python (`alt_hash`) and in JS (`altHash`): the Web Audio preview, the WAV and the exported MIDI
play the same layers. ⚄ changes the seed. Layers with their own steps always play.

## Genres

Every genre (`G`) has a typical BPM and range, swing, key, bass octave, an optional *half-time* and hand-written
variants (`V`: bus steps, bass line, bars). Two variants are **derived automatically** from the first one:

- **Fill**: the last 4 sixteenths of the snare (or the clap) become `xx33` (`3x33` in half-time genres): a roll on the
  last beat; a `..xx` tom run on the last beat; a crash on the downbeat if the pattern has no cymbals.
- **Breakdown**: kick, snare, toms and bass out; if nothing is left, an off-beat hat; an FX hit on the downbeat.

### Vary

*Vary* (in `pattern.js`) applies small idiomatic mutations:

1. moves an off-beat kick by ±1 sixteenth (if the target step is free), or adds one 6 steps from the end;
2. adds up to 2 snare ghosts (velocity 55) on free off-beats;
3. gives a closed hat hit a ×2 or ×3 roll;
4. with 50% probability, if there is an open hat, turns one on or off on an "and" (step 2 + 4k).

### Random kit

For every bus that plays and is not locked it asks `random_refs(classes of the bus, n)` — the same
[random group](drum-rack.md#random-group-and-random-kit) as the Drum Rack — with *n* = 1, 2 or 4 (the bass always
1), excluding the samples already chosen. With *similar dynamics* the reference is the audible layers of the buses
that are not regenerated plus those chosen along the way. Buses with several layers switch to *random* alternation,
except kick, FX and bass.

## Rendering (`render.py`)

The loop WAV is mixed in numpy, with the same logic as the Web Audio scheduler:

- Velocity **gain** \((v/127)^{1.5}\), constant-power pan, volume and pan per bus and layer.
- **Samples** loaded up to 30 s, stereo, 44.1 kHz; **pitch** is a resampling (like a sampler: the length changes
  too); the offset in ms shifts the layer.
- **Seamless loop**: tails that run past the end of the loop come back in from the start.
- **Choke**: every open hat is closed (10 ms fade) at the next closed hat, across the loop boundary too.
- High-pass/low-pass **filters** per bus: magnitude response of a 2nd-order Butterworth applied in the FFT domain
  (zero phase).
- **Limiting**: if the mix goes above 0.98 it is scaled down.

### Bass tuning

A bass sample plays in tune because its **root note** is estimated: 3 s, trim, autocorrelation of the loudest 100 ms
(after the transient), search for the fundamental 40–1000 Hz; if the harmonicity is above 0.4 (0.5 for library
samples) \(\text{root} = \operatorname{round}\big(69 + 12\log_2(f_0/440)\big)\). Every bass note is then transposed by

\[
12(\text{octave}+1) + \text{key} + \text{semitones} - \text{root} + \text{layer pitch}.
\]

## MIDI and export

- Dependency-free **SMF writer**: type 0 or 1, note-offs before note-ons on the same tick.
- **Drum Rack mapping**: consecutive notes from 36 for the buses used; an alternating bus gets one pad per layer and
  every hit goes to the pad of the layer that plays it. **GM**: one note per bus. Drum notes 1/32 long.
- **Glide**: a note with glide overlaps the next one by 1/64 (legato), so the Simpler in mono mode slides.
- **Ableton**: Drum Rack with one pad per bus (nested Instrument Rack for the layers, choke on the hats), bass in a
  mono classic Simpler with `RootKey` = estimated root, 60 ms release and 60 ms glide when needed.
- **Sequences** (`arrange.flatten`): blocks × repetitions are concatenated into a single pattern (at most 256 bars),
  with per-bar swing and section boundaries; layers with their own steps are repeated over the whole length.
