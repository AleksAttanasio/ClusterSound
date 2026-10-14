# Melody

Code: `chords/melody.py`. Every generator gets the **chord map** (which chord plays on every sixteenth) and the key,
is deterministic given the seed and produces several proposals (up to 3× those requested, deduplicated).

## Melody (lead)

The strategy combines a **global contour** with a **local note-by-note choice**, organised in **phrases**.

**Phrases and rhythm.**

- Phrases of 2 bars (high density), 4 (low) or random. The rhythm of every bar is chosen from a repertoire per
  density.
- Odd phrases are **answers**: with probability 0.75 they take up the rhythm of the question, bar by bar; the last bar
  of the answer is mutated (an onset added or removed).
- **Breath**: the last bar of a phrase keeps only the onsets up to the third beat, so the phrase ends on a long note,
  and that note is the **root of the chord**.

**Candidate pitches.** On the strong beats the chord notes; on the weak ones the scale plus the chord notes.

**Contour.** The centre of attraction within the phrase (position \(x \in [0,1]\)) is

\[
\text{target}(x) = \text{centre} + 0.7\cdot\text{half-range}\cdot f(x)
\]

with *arch* \(f = 1.2\sin(\pi x) - 0.4\), *rising* \(f = -0.6 + 1.2x\), *falling* \(f = 0.6 - 1.2x\), *wave*
\(f = 0.6\sin\big(\pi(2x + \varphi)\big)\).

**Note choice** (`_pick`): among the candidates the highest score wins:

| Term | Value |
|---|---|
| distance from the contour | \(-0.25\,|p - \text{target}|\) |
| interval from the previous note (*a* semitones) | \(-0.35\,a\) up to 4; beyond \(-1.4 - 0.6\,(a-4)\); beyond the fifth another −3 |
| repeated note | −0.9 on the strong beats, −1.6 on the weak ones |
| unrecovered leap | −1.5 if after a leap > 4 semitones it does not step back in the opposite direction |
| variety | \(+0.9\,u\), *u* uniform |

These are the classic rules of counterpoint (stepwise motion, recovered leaps, few repetitions) in the form of a
score. **Velocity**: 104 on the downbeat, 92 on the beats, 80 elsewhere, ±6.

## Bass

- The root of every chord, in the octave closest to the previous one and pulled towards the bottom of the range.
- **Styles**: *roots*, *octaves*, *fifths*, *walking* (scale notes towards the next root).
- **Approach**: with probability 0.7 the last note before a chord change is ±1/±2 semitones from the next root.

## Arpeggio

The notes of the chord in a 7-note window around the previous one, in steps of 4 / 2 / 1 sixteenths by density, in
the rising, falling, up and down, random directions.

## Riff

A **one-bar cell** of intervals built with `_pick` on the wave contour; on every chord it is transposed to its root and
"snapped" to the chord notes on the beats (scale + chord elsewhere). Every fourth bar the rhythm is mutated, so that
the riff is not mechanical.

## Pad and Keys

Close voicings of up to 4 notes (the fifth goes first) chosen for the minimum distance from the previous one. *Pad*:
held (low density), one per bar or one per half bar. *Keys*: rhythmic comping from a repertoire of rhythms.

## Chords from the melody

The inverse problem: given a melody, find a progression of the pack that harmonises it.

1. **Candidates**: the pack's chords distinct by (root, set of notes), optionally also from the nearby keys.
2. **Segments**: one chord per bar, two, or *automatic*: a bar is split if the best whole chord fits less than 0.7 and
   the two halves together are worth more than \(2\cdot\text{whole} + 0.3\).
3. **Note weight**: length × 1.5 if the note falls on a beat × 2 if it opens the segment.
4. **Fit** of a chord to a segment (normalised on the total weight):

    | Melody note | Contribution |
    |---|---|
    | chord note | \(+w\) |
    | in the scale, out of the chord | \(-0.15\,w\) |
    | out of the scale | \(-0.6\,w\) |
    | a semitone from a chord note | another \(-0.25\,w\) |
    | downbeat note = root | \(+0.15\) of the total |

    minus \(0.03\) for every chord note beyond the third (it prefers simple chords).

5. **Viterbi** over the sequence of segments, to choose the best chain and not just the best chord per segment:

    \[
    \text{emission} = 2.2\cdot\text{fit},\quad
    \text{start} = 0.5\cdot\text{start score},\quad
    \text{transition} = 0.6\cdot\text{transition}(a,b) - 0.5\,[a = b]
    \]

    with the same `transition` as the [suggestions](harmony.md#next-chord) and a +0.8 bonus if the last chord is the I.

6. **Alternatives**: the following versions add Gaussian noise (σ 0.25) and −0.35 for the chords already used in that
   segment.
7. **Clips**: repeated chords merged, voicings chained with `_fit` around the middle register and lowered by an
   octave while they sit under the melody.

## Key detection

**Krumhansl-Schmuckler** algorithm: the histogram of the 12 pitch classes (weighted by length, first and last note
count double) is correlated (Pearson) with the major and minor key profiles rotated over the 12 tonics; the highest
correlation among the 24 keys wins. It is used when a version has only the melody or for *Detect from the melody*.
