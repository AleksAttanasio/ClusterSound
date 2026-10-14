# Harmony and chords

Code: `chords/library.py`, `theory.py`, `harmony.py`, `variations.py`, `perform.py`. Chords are not generated from
abstract rules: they are the **MIDI clips of the chord pack**, indexed and then sorted, transposed and varied. This
way every chord has a voicing played by a musician.

## Indexing the pack

- **Key** from the `NN - X Major - Y Minor` folders; the mode from the presence of "minor" in the subfolders; the
  **category** (triads, extended, borrowed, progressions…) from keywords of the folders.
- **Segmentation**: notes with onsets within 1/32 form a chord (resampled to 480 PPQ); every chord lasts until the
  next one and the end of the file is rounded to the bar. A file with several segments is a **progression**; the
  degrees in brackets in the name (`(I-V-vi-IV)`) are read if they are all valid.
- **Root**: from the name of the chord, otherwise from the degree, otherwise estimated (below).
- **Missing keys**: served by the nearest key of the pack with the same category, transposing by −6…+5 semitones (on
  a tie, downwards). The results are marked *transposed*.
- **Statistics**: for every progression the **bigrams** of degrees are counted (consecutive pairs, repetitions
  excluded; the last → first return counts 0.5 because progressions loop).

## Theory (`theory.py`)

**Quality** from the intervals above the root: with a major third → augmented (augmented 5th without a perfect one),
dominant (minor 7th without a major one) or major; with a minor third → diminished (diminished 5th without a perfect
one) or minor; otherwise sus.

**Estimated root**: for every pitch class *r*

\[
\text{score}(r) = 2[\text{3rd}] + 1.5[\text{5th}] + 1[\text{dim. 5th with min. 3rd}] + 0.5[\text{7th}] + 0.75[r = \text{bass}]
\]

**Harmonic function**: a chord is *diatonic* if the root and the triad core (root, 3rd, 5th) are in the scale (in
minor the leading tone is allowed too). Diatonic chords have a **T**onic, **S**ubdominant or **D**ominant function
by degree; all the others are **C** (colour / modal borrowing). These are the four colours of the browser.

## Next chord

For every candidate *b* after the chord *a*, `transition(a, b)` adds up:

| Term | Value |
|---|---|
| **Function flow** | T/S/D/C table: e.g. T→S 1.0 · S→D 1.0 · D→T 1.0 · T→D 0.75 · D→S 0.3 |
| **Cadence** (the first that matches) | V→I +0.6 · ii→V +0.45 · plagal +0.35 · deceptive +0.35 · bVI→bVII +0.35 · mixolydian bVII→I +0.35 · Neapolitan +0.3 · leading tone→tonic +0.3 … |
| **Bass motion** | fourth up (fifth down) +0.35 · fifth up +0.15 · stepwise +0.15 · tritone −0.3 · same root −0.3 (different colour) or −0.7 |
| **Common notes** | +0.08 per note, up to 3 |
| **Voice leading** | \(\max(0,\;0.3 - 0.03\,d)\), with *d* = mean distance in semitones |
| **Frequency in the pack** | \(+0.6 \cdot \text{bigram}(a,b) / \max\) |

The **voice leading distance** between two voicings is the mean of two means: every note of *b* to the nearest note
of *a*, and vice versa.

Then `suggest`:

- a −0.8 penalty for the same chord of the library and −0.15 for an A-B-A ping-pong;
- if there is already a chord *n* after it, \(0.6 \cdot \text{transition}(b, n)\) is added: the suggestion also has to
  *lead* well;
- without a previous chord, starting score: T 1.0 (+0.4 if it is the I) · S 0.55 · D 0.35 · C 0.2;
- the candidates are grouped by (root, minor, diminished): the best voicing wins, the others become the **colour
  variants** under the proposal;
- the scores are rescaled between 0.35 and 1 for the bar; the **reasons** shown are the labels of the terms that
  fired.

With an unlocked key the candidates include the nearby keys: dominant, subdominant, relative and parallel.

## Variations

All deterministic given the seed (`random.Random(seed)`).

**Fitting a voicing** (`_fit`): tries inversions −2…+2 × octaves −1…+1 (notes between 24 and 100) and picks the one
that minimises \(d(\text{previous}) + 0.15\,|\text{centre} - \text{reference centre}|/3\).

**Of a chord**:

- *voicing*: 1st and 2nd inversion, inverted downwards, drop-2, open (2nd voice an octave up), close, doubled bass;
  at the top the one with minimal voice leading from the previous chord;
- *colour*: same root and same mode from the pack, preferring a different number of notes;
- *substitution*: the first 2 of `suggest` in context (chord before and after) plus 2 random ones among the others.

**Of the progression** (`vary_progression`), with *How much to vary* \(a \in [0.05, 1]\):

| Kind | Strategy |
|---|---|
| *reharmonisation* | replaces \(\operatorname{round}(a \cdot \text{inner})\) chords (first and last stay); every choice takes rank \(\lfloor u^2 \cdot 5\rfloor\) among the 5 best suggestions, with *u* uniform: it favours the best without always being the same |
| *harmonic rhythm* | eighth-note anticipation, long-short (1.5 + 0.5), split of a chord ≥ 1 bar with the best suggestion in the second half |
| *voice leading* | chain of `_fit` for minimal motion |
| *richer / sparser* | same root with more or fewer notes (sparser prefers triads) |
| *ending* | typical cadence of the mode on the last 2 chords (IV→V, bVI→bVII, IV→iv, ii→V…) |

The proposals are deduplicated by signature; up to 4× the number requested are generated.

## Playing (`perform.py`)

From chords to notes, at 480 PPQ; **the same function** produces preview, MIDI and clips for Live.

- **Hits**: the rhythm grid repeats over the absolute timeline; a length of 0 means "until the next hit". A chord
  that starts off the grid gets a hit at its start.
- **Swing**: odd sixteenths delayed by \((\text{swing}/50 - 1)\cdot 120\) ticks.
- **Strum**: *guitar* direction (down on the beats, up in between), alternate, always up/down; total spread limited to
  half the length; linear, accelerating \(1-(1-x)^2\) or decelerating \(x^2\) curve; velocity tilt and softer
  upstrokes; upstrokes can be limited to the top notes.
- **Arpeggio**: up, down, up-down, random over 1–3 octaves; off-beat notes at 0.86 of the velocity.
- **Dynamics**: crescendo \(0.72 + 0.42f\), diminuendo \(1.14 - 0.42f\), bass accent ×1.12; accents on the beats.
- Deterministic **humanize** (humanize seed XOR CRC32 of the chord): timing shifts a whole hit together, with a
  *drift* that mixes white noise and cosine-interpolated "value" noise (period 2 beats); plus per-note spread,
  length ±% and velocity ±. Finally overlaps on the same note are shortened and notes under 12 ticks are dropped.
