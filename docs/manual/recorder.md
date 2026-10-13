# Recorder

Records what the computer sends to one or more **audio outputs**, then cuts samples out of the recording: they go
into the library and are classified like the others. It also opens any audio file or library sample.

![Recorder with regions on the transients](../assets/screenshots/recorder.png){ .shot }

## Recording

- **Outputs**: speakers, headphones, audio interfaces, AirPlay… plus *All outputs (mix)* (on Windows *Default
  output*). Several outputs start together, each with its own file and meter. *Refresh the list* reads the
  devices again.
- **Format** (Settings › Recorder): WAV 16/24 bit or 32 float, AIFF, FLAC 16/24, CAF, MP3 128–320 kbps, OGG
  Vorbis, Opus (48 kHz), M4A/AAC (macOS only). Device rate or 44.1/48/96 kHz; stereo, mono or all channels
  (uncompressed formats).
- **Folder**: `~/Music/ClusterSound Recordings/<date time> - <output>.<ext>` with a `.source.txt` of provenance.
  The recording goes on while you switch section.

## Opening audio

*Open file…* (or drag from the Finder onto the waveform) opens any audio file; *From the library…* opens samples and
loops browsing folders and packs or searching by name.

## Editor and regions

- When you stop, the recording opens in the editor. **Drag** on the waveform to create a region, the edges resize
  it, click to listen to it.
- **Slice on transients** creates one region per hit in the visible part; *Sensitivity* sets how many hits it
  finds.
- Wheel: zoom · `Shift`+wheel: scroll · the strip below moves the view · `Space` play/stop · `↑` `↓`
  previous/next region · `Del` delete.

## Exporting

- **Export selected**: 24-bit WAV in `~/Music/ClusterSound Samples/`, with fades (1 ms in, 10 ms out) and optional
  normalisation, at most 30 s each.
- **To the Drum Rack**: loads the regions on the free pads from the selected pad on, in note order, and opens the
  Drum Rack.
- **Send to Live**: a new audio track in Ableton with the region (or all the audio), in the first empty slot of
  the selected scene. It needs the ClusterSound device with *Receive* on.

## Extract stems

Separates the recording or the region into **Drums, Bass, Guitar, Piano, Vocals** (those you tick) plus always
**Other** with the rest, so the sum gives back the original. One 24-bit WAV per stem, which can be opened in the
editor. It runs locally with Demucs (`stems` extra, 55 MB model downloaded on first use). Details:
[Demucs](../ai/demucs.md).

## Enhance

Purple ✨ button, also on every region: **AI restoration** that rebuilds the cut high frequencies and cleans up the
artefacts of compression (MP3, streaming). The result is a new `… (enhanced).wav` file; the original stays as it
is. It runs locally with Apollo (`enhance` extra, 66 MB). Details: [Apollo](../ai/apollo.md).

!!! warning "Legal note"
    Nothing is decrypted or bypassed: apps that protect their stream record silence. Recordings are for personal
    use (private copy); to publish a track that contains a sample you need the rights to the original, or a
    sample with a free licence. There is no number of seconds below which a sample is free.

!!! info "Windows"
    Every output is recorded with WASAPI loopback: there is no mix of all the outputs, ClusterSound's own audio
    also ends up in the recording and the M4A format is not available. No permission to grant.
