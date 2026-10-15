# Choosing the Drum Rack samples

The Drum Rack has to fill groups of pads with samples that are **similar to each other but not identical**,
respecting family, filters and, for the SPD-SX, the playability of the kit. Code: `racks/select.py`,
`racks/dynamics_match.py`, `racks/spdsx.py`, masks and auto-fill in `api.py`.

## Space and candidates

- **Similarity**: cosine between normalised YAMNet embeddings.
- **Candidate mask** (`_rack_mask`): same class as the seed (default), the classes of the group's family, or the
  whole library; *one-shots only* (default yes); *avoid samples already in the kit*; for random kits also the
  folder/pack filter (substring of the path).
- **Pool**: the **400** candidates most similar to the seed are considered.
- **Duplicates**: a candidate is discarded if its cosine with one already chosen (seed included) is ≥ **0.995** —
  copies and renamed files do not take two pads.

## Fill modes

**Most similar** (`neighbours`): goes down the ranking and takes the first *k* non-duplicates.

**Random** (`pick`, `random` mode): builds a pool of the
\(\text{count} + \operatorname{round}(v \cdot 5 \cdot \text{count})\) most similar, where \(v \in [0,1]\) is the
*variation* slider (at \(v = 1\) the pool is 6 times the number of pads). Then it draws without replacement with
weights

\[
w_i = \exp\!\Big(\frac{s_i - s_{\max}}{T}\Big), \qquad T = 0.05
\]

The low temperature clearly favours the most similar but leaves room for the others; the slider widens the pool. The
result is sorted by similarity and reproducible from the random seed (*Regenerate* changes it).

**Manual**: the 60 most similar neighbours in a list to tick.

**Trail** (`trail`): the stops of *Find similar* chosen by hand, in order and without repetitions, cut to the size of
the group; if they are too few, they are completed with the neighbours of the last stop (the filters only apply to
the completion).

## Random group and random kit

`random_group` is the building block of *🎲 Random*, of the Sequencer's random kit and of *Generate kit*:

1. among the allowed candidates the **groups** `class:subcluster` are listed;
2. one is chosen **uniformly** (not in proportion to its size: small groups come out too);
3. a random seed inside the group;
4. the other `count − 1` with a random `pick` around the seed.

`rack_randomize` applies it to every unlocked group (or only to the empty ones):

- the samples already used are excluded;
- with **distinct groups** (always for the SPD-SX) the subclusters already used by other groups are excluded first,
  so two rows of hats, or the pedal kick and a pad kick, sound different; if too few candidates are left that way,
  the constraint is dropped;
- with **similar dynamics** the reference is the set of samples already put in the kit (see below).

**Auto-fill** (`rack_autofill`) is the deterministic version: for every empty group it picks as seed the best unused
one-shot of the family — sorting by class of the family, one-shots first, non-loop names first, decreasing
confidence — preferring among the first 300 a subcluster not yet used in the same family; then it completes with a
random `pick` at variation 0.3.

## Similar dynamics (`dynamics_match.py`)

A kit sounds cohesive if its hits have compatible envelopes. Every sample has a 5-value envelope vector:

| Feature | Scale | Weight |
|---|---|---|
| attack | log₁₀ | 0.7 |
| decay to −20 dB | log₁₀ | 1.2 |
| T60 | log₁₀ | 1.2 |
| tail share | linear | 1.0 |
| envelope slope (dB/s, clipped to [−200, 50]) | linear | 0.6 |

The values are **standardised within every class** (with statistics of the whole library for classes with fewer than
5 samples): this way a kick that is *short for a kick* comes out close to a hat that is *short for a hat*. The
reference is the mean of the samples already chosen; the distance is the RMS over the 5 dimensions and the score
\(\exp(-d^2/2)\). The margin keeps the closest fraction of the candidates (at least 8), which then goes to the random
choice.

## 8×8 layout

- Pads numbered `row·8 + column`, row 0 at the bottom.
- *Launchpad* notes: \(b_{Q[q]} + 4\,(r \bmod 4) + (c \bmod 4)\), with quadrant \(q = 2[r \ge 4] + [c \ge 4]\) and
  \(Q\) the kit's arrangement of the blocks C = 36, D = 52, A = 68, B = 84 (default `DBCA`: top-left 36–51,
  top-right 68–83, bottom-left 52–67, bottom-right 84–99, as the Launchpad plays them). *Rows* notes: \(36 + p\).
- Layouts: 8 columns of 8, 16 blocks 2×2, 4 quadrants 4×4, 16 columns of 4 (one family per quadrant), free; every
  layout has default families (18 families in all). Choke is on by default for the hat families.

## Roland SPD-SX

**Pads and triggers**: 9 pads (notes 60–68) plus Trig 1 (pedal, 69) and Trig 2 (70). Without the pedal pad 8 becomes a
group of its own with the kick; every connected trigger is a group (T1 kick, T2 cymbal).

**Playability limits**: at most **2 kicks**, **3 snares/claps**, **5 hats/cymbals**. The role of a group comes from
its family; for generic families ("any", "fx") the class of the sample on every pad is counted. A family is offered
for a group only if, changing it, no role exceeds \(\max(\text{limit}, \text{current count})\).

**Generate kit** (`random_config` + `rack_randomize`):

1. up to 50 attempts: a random configuration (*Free* excluded), in which every group swaps its family for a variant
   of the **same role** (snare ↔ clap, hat ↔ hat + cymbal, perc ↔ shaker ↔ tom…); T1 stays a kick;
2. the first one that respects every limit is accepted;
3. it is filled with distinct groups (above). If a group is locked, or keeping the configuration was asked, only the
   filling changes.

## Export

- `.adg`: gzipped XML from neutral Live 10 templates; one `DrumBranch` per pad with note
  (`ReceivingNote = 128 − note`), choke group and a Simpler in one-shot mode with a path **relative** to the preset.
- SPD-SX: also 16-bit / 44.1 kHz WAVs (resampled with soxr) for Wave Manager, named `P1`…`P9`, `T1 Pedal`, `T2`, plus
  `README.txt` with the pad map.
