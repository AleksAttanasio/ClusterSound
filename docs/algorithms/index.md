# Strategies and algorithms

How ClusterSound makes its decisions: from the signal analysis to the choice of the samples of a kit, from the next
suggested chord to the generated melody. Every page names the modules involved and the real constants used in the
code.

| Function | Strategy in one line | Page |
|---|---|---|
| Analysis | 22 envelope and spectrum features + mel profile + multi-band onsets | [Audio analysis](audio-analysis.md) |
| Classification | name + zero-shot + rules + MLP, fused in log-probability | [Classification](classification.md) |
| Subgroups | k-means per class, k chosen with the silhouette | [Clustering and map](clustering-and-map.md) |
| 3D map | PCA → 3D t-SNE, landmarks beyond 2500 points | [Clustering and map](clustering-and-map.md) |
| Similar | cosine on the YAMNet embeddings | [Clustering and map](clustering-and-map.md) |
| Drum Rack kits | neighbours without duplicates, weighted random choice with temperature, different groups, similar dynamics | [Drum Rack](drum-rack.md) |
| SPD-SX | random configurations bound by playability limits | [Drum Rack](drum-rack.md#roland-spd-sx) |
| Grooves | step patterns with MPC swing, rolls, deterministic layer alternation | [Sequencer](sequencer.md) |
| Next chord | additive score: function, cadences, bass motion, common notes, voice leading, pack statistics | [Harmony](harmony.md) |
| Variations | minimum-distance voicings, weighted reharmonisation, harmonic rhythm | [Harmony](harmony.md) |
| Melody | target contour + note choice by score, question/answer phrases | [Melody](melody.md) |
| Chords from the melody | fit score + Viterbi | [Melody](melody.md#chords-from-the-melody) |
| Key | Krumhansl-Schmuckler profiles | [Melody](melody.md#key-detection) |
| Slices | multi-band spectral novelty, peaks above a threshold | [Recorder and slicing](recorder-and-slicing.md) |
| Store | parallel federated search, server-side or local filters, labelling by instrument | [Store](store.md) |

!!! note "Determinism"
    Almost everything that is "random" uses an explicit **seed** (`np.random.default_rng(seed)`, `random.Random(seed)`
    or an integer hash): the same choice produces the same result, and the 🎲 / *Regenerate* buttons change the seed.
    The exception is *Vary* in the Sequencer, which uses `Math.random`.
