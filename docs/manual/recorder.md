# Recorder

Records what the computer sends to one or more **audio outputs**, then cuts samples out of the recording: they go
into the library and are classified like the others. It also opens any audio file or library sample.

![Recorder with regions on the transients](../assets/screenshots/recorder.png){ .shot }

The screen uses its whole width: the **file bar** on top, the waveform, the **transport** under it and the
**Extractions** of the open audio at the bottom.

## Recording

- **● Record** is in the transport, with the clock and a small level meter per output (hover it for the output's
  name). The yellow ⚠ next to it recalls the legal note below; ⋯ opens the Recorder settings.
- **Outputs**: speakers, headphones, audio interfaces, AirPlay… plus *All outputs (mix)* (on Windows *Default
  output*). Several outputs start together, each with its own file and meter. *Refresh the list* reads the
  devices again.
- **Format** (Settings › Recorder): WAV 16/24 bit or 32 float, AIFF, FLAC 16/24, CAF, MP3 128–320 kbps, OGG
  Vorbis, Opus (48 kHz), M4A/AAC (macOS only). Device rate or 44.1/48/96 kHz; stereo, mono or all channels
  (uncompressed formats).
- **Folder**: `~/Music/ClusterSound Recordings/<date time> - <output>.<ext>` with a `.source.txt` of provenance.
  The recording goes on while you switch section.

## Opening audio

The file bar shows the path of the open audio. Its folder button asks where to open from: **Local folder…** (any
audio file of the computer), **Sample library…** (samples and loops by folder, pack or name) or one of the
**Recent recordings** of the session. An audio file dragged from the Finder onto the waveform opens too.

## Editor and regions

- When you stop, the recording opens in the editor. **Drag** on the waveform to create a region, the edges resize
  it, click to listen to it.
- **Slice on transients** creates one region per hit in the visible part; *Sensitivity* sets how many hits it
  finds.
- Transport: **■** stop (back to the start), **▶/❚❚** play and pause (play resumes where it paused), **⤢** shows
  the whole track.
- Wheel: zoom · `Shift`+wheel: scroll · the strip below moves the view · `Space` play/pause · `↑` `↓`
  previous/next region · `Del` delete.

## Extractions

Three tabs, each with a tick per row:

- **✂ Cuts**: the regions, cut by hand or on the transients.
- **Stems**: the stems already extracted from the open audio, found again on disk when it opens.
- **✨ Enhanced**: the enhanced files made from the audio, from its cuts or from its stems.

Every row has icon-only buttons: listen, show the waveform (a cut is zoomed in; a stem or an enhanced file opens
in the editor, and the lists stay those of its source), ✨ Enhance (cuts and stems) and **Send**, the same menu as
in the library (a Sequencer bus or a Drum Rack group).

Next to the title:

- **Clear all** empties the tab, after a confirmation (stems and enhanced files stay on disk).
- **Send to**: the ticked rows to **Ableton Live** (one new audio track each; with no cut ticked, all the audio),
  to the **Drum Rack** (on the free pads from the selected one) or to the **Sequencer** (new layers of the chosen
  bus). Live needs the ClusterSound device with *Receive* on.
- **Export all**: the ticked rows into the **export folder** (Settings › Recorder, by default
  `~/Music/ClusterSound Samples/`). Cuts become 24-bit WAVs with fades (1 ms in, 10 ms out) and optional
  normalisation, at most 30 s each; stems and enhanced files are copied with their provenance note.

## Extract stems

Separates the recording or the region into **Drums, Bass, Guitar, Piano, Vocals** (those you tick) plus always
**Other** with the rest, so the sum gives back the original. One 24-bit WAV per stem, which can be opened in the
editor. The stems show up in the **Stems** tab. It runs locally with Demucs (`stems` extra, 55 MB model downloaded on first use). Details:
[Demucs](../ai/demucs.md).

## Enhance

Purple ✨ button, also on every cut and stem: **AI restoration** that rebuilds the cut high frequencies and cleans up the
artefacts of compression (MP3, streaming). The result is a new `… (enhanced).wav` file, listed in the **Enhanced** tab; the
original stays as it is. It runs locally with Apollo (`enhance` extra, 66 MB). Details: [Apollo](../ai/apollo.md).

!!! warning "Legal note"
    Nothing is decrypted or bypassed: apps that protect their stream record silence. Recordings are for personal
    use (private copy); to publish a track that contains a sample you need the rights to the original, or a
    sample with a free licence. There is no number of seconds below which a sample is free.

!!! info "Windows"
    Every output is recorded with WASAPI loopback: there is no mix of all the outputs, ClusterSound's own audio
    also ends up in the recording and the M4A format is not available. No permission to grant.
