# Recorder and slicing

Code: `sampler/recorder.py`, `capture.py`, `wasapi.py`, `native/cs_tap.swift`, `sampler/slicing.py`,
`sampler/session.py`, `sampler/export.py`.

## Recording the audio output

The Recorder has to capture **what a device plays**, several devices together too, without virtual drivers. Every
chosen output is a `Track` with its own backend and its own `Writer`; they start together and an error on one device
does not stop the others (the recording fails only if all of them fail).

| Platform | Backend | How |
|---|---|---|
| macOS 14.2+ | `cs-tap` | Swift helper with **Core Audio process taps**: it gets the same audio the device plays; it excludes ClusterSound's process (`--exclude-pid`); it writes a JSON header and then float32 PCM on stdout |
| macOS, without the helper | ScreenCaptureKit | only *All outputs*: a minimal mandatory video stream (2×2 px, 1 fps), 48 kHz stereo audio, the app's audio excluded |
| Windows | WASAPI loopback (`soundcard`) | one thread per output with its own COM initialisation, 48 kHz, 1024-frame blocks; the "mix" is the default output |

The `Writer` creates the file at the first block (when it knows the channels), maps the channels (mono = mean,
stereo, all), resamples in streaming with `soxr.ResampleStream` if needed and writes with libsndfile (WAV, AIFF, FLAC,
CAF, constant-bitrate MP3, OGG, Opus at 48 kHz). M4A goes through an intermediate CAF converted with `afconvert`. An
RMS meter per track feeds the UI.

Protected streams record silence: nothing is decrypted.

## Slicing on transients

It uses the [multi-band](audio-analysis.md#multi-band-onsets) onset detector, adapted to long recordings:

1. **Sensitivity** → rise threshold: linear from **18 dB** (0) to **4 dB** (1).
2. **Blocks** of 30 s with 1 s of overlap: every block "owns" the interval \([a + 0.5,\; a + \text{hop} + 0.5)\) s, so an
   onset close to the edge is counted only once; 50 ms of silence are prepended to the first block so that a hit at
   t = 0 shows a rise. Onsets within 30 ms are merged.
3. **Regions**: from 5 ms before the onset (pre-roll) to the next one minus the pre-roll, limited to the maximum
   length (30 s); every region is then shortened to the last 10 ms RMS window above **−50 dB** relative to its peak
   (no silent tails). Regions under 30 ms are discarded.

## Rendering the samples

When a region becomes a file (`slicing.render`):

- the start moves to the nearest **zero crossing**, at most 2 ms earlier (no clicks);
- 1 ms fade-in and 10 ms fade-out;
- optional normalisation to −0.3 dBFS;
- 24-bit WAV in `<samples folder>/<source>/<title>/`, with `.license.txt` (Store links) or `.source.txt`
  (recordings: private use). A region already exported and not changed reuses its file.

Sources are limited to 20 minutes (beyond that they are cut and flagged); the waveform is computed as min/max columns
with `np.minimum.reduceat` / `np.maximum.reduceat` for the visible width.

## Links

`links.py` recognises Freesound, Internet Archive, ccMixter, Openverse and Wikimedia Commons links and resolves them
with the providers' APIs (a ccMixter zip pack is replaced by its preview, because the editor opens a single file);
links to streaming services (YouTube, Spotify, SoundCloud…) are refused with an explanation.
