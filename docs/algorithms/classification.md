# Classification

The model part (MLP heads, training, fusion, accuracy) is described in
[AI models › Classifier](../ai/classifier.md). Here the **strategy**: why four signals and how they complement each
other.

## The problem

A real sample library is heterogeneous: commercial packs with perfect names (`Snare 07.wav`), recordings with
anonymous names (`A101.wav`), folders that tell the class (`/Kicks/…`) or confuse it (`/Drum Loops/…`), loops,
textures. No signal is enough on its own:

| Signal | Strong when | Weak when |
|---|---|---|
| Name and folders | pack names | anonymous names, ambiguous names (`cl`, `op`, `sd`) |
| YAMNet zero-shot | categories AudioSet knows (snare, clap, guitar) | producer distinctions (closed/open hat, kick/808) |
| Acoustic rules | clear physical properties (low vs high, short vs long) | in-between cases |
| MLP heads | always, if they have seen similar examples | rare classes |

The fusion sums evidence in **log-probability**: every signal moves the distribution without being able to dominate
it, and when a signal is missing (anonymous name → null log-prior) the others decide.

## Name parser

- **Tokenization**: separators, camelCase (`ClosedHat` → `closed`, `hat`), letter/digit boundaries (`kick04` →
  `kick`, `04`), plus the joined variants (`open hat` → `openhat`).
- **Keywords per class** from `taxonomy.py`, with a lower weight for ambiguous tokens.
- **Context rules**:
    - a hat word with "open" → open hat 1.0; without → closed hat 0.8 (and open hat 0.3); "open"/"closed" without a
      hat word halve the evidence;
    - "808" next to another drum name weighs ×0.2 (it is the TR-808 drum machine, not a sub kick), next to "kick"
      ×0.6, next to "bass" the 808 wins;
    - generic words ("cymbal", "perc") lose against a specific one in the same name;
    - `fx`, `sfx`, `transition`… give 0.3 to riser, impact, downlifter and noise.
- **Depth**: the file weighs 1, the parent folder 0.65, then 0.45, 0.3, 0.2; for every class the maximum is kept.

## Acoustic rules (`features.rule_logits`)

Additive priors built with soft sigmoids \(\sigma\big((x-c)/w\big)\), so without hard thresholds:

| Rule | Effect |
|---|---|
| **Energy below 250 Hz** \(> 0.55\) | + kick, 808, bass, tom; − hat, shaker, cymbals |
| **Energy above 6 kHz** \(> 0.35\) | + hat, shaker, cymbals, tambourine; − kick, 808, bass, tom |
| **Decay to −20 dB** \(> 0.25\) s | + open hat, − closed hat |
| **T60** \(> 0.8\) s | + crash |
| **Low tonal tail** (long T60 × harmonic × low) | + 808, − kick |
| **Thump** (low × decay < 0.35 s × attack < 10 ms) | + kick, + tom, − bass |
| **Duration** < 0.12 s | + snap, rimshot, woodblock, closed hat |
| **Duration** > 2 s | + pad, noise, riser, downlifter (− if a short one-shot) |
| **Tonal** (high harmonicity × low flatness) | + melodic instruments and vocals |
| **Noisy** (high flatness) | + hat, shaker, snare, clap, noise, riser, crash |
| **Sweep** (centroid and envelope rising/falling, on long sounds) | + riser / + downlifter |
| **Slightly slow attack** and noisy | + clap (several hits within ~40 ms lengthen the attack) |

## Self-training on the library

The key idea: **the clear names of a library teach how to classify the anonymous files of the same library**.
Every classification trains a head on the files whose name has a strong keyword (≥ 0.75) and on the manual
corrections (weight 3). Since the sounds of a pack resemble each other, the head generalises to the unnamed files
much better than the zero-shot (72% against 16% in the [evaluation](../ai/classifier.md#accuracy)).

## Unsorted and corrections

Below a 22% probability the class is *Unsorted*: better an "I don't know" than a confident mistake. Every
correction:

1. saves the label in `cache.sqlite` (it survives rescans);
2. updates that sample straight away;
3. retrains the library head in the background and recomputes classes and subclusters of the whole library;
4. invalidates the snapshot (the fingerprint includes the labels).
