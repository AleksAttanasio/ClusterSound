# Audio analysis

Every file goes through `library.analyse_file` only once; the result stays in the SQLite cache.

## Preparing the signal (`audio_io.py`)

1. **Decoding** with libsndfile (`soundfile`): wav, aif, flac, ogg, mp3, caf, w64. At most the first **30 s** are
   read; the channels are averaged into float32 mono, NaNs are zeroed.
2. **Silence trim**: start and end below **−60 dB** relative to the peak are cut, leaving 2 ms before the first
   useful sample (the attack stays intact).
3. **Resampling** with soxr (HQ quality) in two versions: **16 kHz** for YAMNet (normalised to a 0.9 peak, at most
   10 s) and **32 kHz** for the features.

## The 22 features (`features.py`)

| Group | Feature | How |
|---|---|---|
| Duration | `duration`, `log_duration` | after the trim |
| Envelope | `attack` | time from 10% to 90% of the peak of the RMS envelope (10 ms window, 5 ms hop) |
| | `decay20` | time to fall by 20 dB from the peak |
| | `t60` | time to −60 dB, extrapolated from the slope if not reached (max 10 s) |
| | `tail_ratio` | share of energy after 200 ms from the peak |
| | `env_slope` | slope of the envelope in dB/s (only above 0.3 s) |
| Spectrum | `centroid`, `rolloff` | centroid and 85% rolloff, energy-weighted (STFT 2048 / hop 512) |
| | `flatness` | spectral flatness on the active bins only (within 50 dB of the frame peak) |
| | `zcr` | zero-crossing rate |
| | `band_sub`, `band_low`, `band_lowmid`, `band_highmid`, `band_high` | share of energy in 0–60, 60–250, 250–2k, 2k–6k, above 6k Hz |
| | `centroid_slope` | change of log₂ of the centroid over time (sweep) |
| Tonality | `harmonicity`, `f0` | autocorrelation of the loudest 100 ms (skipping the first 20 ms of transient), search 40–1000 Hz after the first negative minimum |
| Rhythm | `onset_count`, `onset_rate`, `ioi_regularity` | multi-band onsets (below); regularity = coefficient of variation of the intervals |

For the head the long-tailed features go through `log1p`.

## Mel profile (144 values)

Derived from the YAMNet log-mel, aligned to the peak of the sound:

- **attack spectrum** (0–60 ms after the peak, 64 bands);
- **body spectrum** (60–400 ms, 64 bands);
- **envelope** at 16 logarithmic instants from 0 to 2 s.

The two spectra are relative to the maximum of the attack spectrum, so they describe the *shape* regardless of the
volume. Together they say "what happens in the hit and what is left afterwards": the difference between a kick and
an 808, or between a closed and an open hat.

## Multi-band onsets

Used to count the hits (*Loop* type) and to [slice on transients](recorder-and-slicing.md):

1. STFT 1024 / hop 256; power summed in **8** logarithmic **bands**;
2. every band in dB, with a floor 35 dB below the loudest band;
3. **novelty** = mean of the 3 bands with the largest rise \(\max(0, dB_t - dB_{t-2})\);
4. frames more than 45 dB below the peak are ignored;
5. onsets = local maxima with a rise ≥ **9 dB**, at least **70 ms** apart.

Measuring the rise over a few milliseconds on several bands makes the detector insensitive to the vibrato and
beating of sustained sounds, which do not rise by several dB in ~16 ms.

## Type

| Type | Rule |
|---|---|
| **Loop** | duration ≥ 1.5 s **and** ≥ 4 onsets; or name/folders with loop tokens (`loop`, `bpm`, `groove`, `beat`, `break`, `fill`, `120bpm`…) and duration > 1 s |
| **Long/Texture** | duration ≥ 2.5 s and not a loop |
| **One-shot** | the rest |

## Measures of the drawer (`dynamics.py`)

Computed on the fly on the whole file (up to 30 s) when you open a sample: peak, RMS and crest in dBFS; waveform
(min/max over 1000 points); RMS envelope in dB; **estimated ADSR** — attack from 10% of the peak, sustain = median
of the 40–80% stretch after the peak, decay down to 3 dB from the sustain, release from the last point above
sustain − 3 dB down to −60 dB; T60; log-mel spectrogram thumbnail.
