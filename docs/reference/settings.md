# Settings

Saved in `settings.json` in the app's data folder. Those that can be changed from the app go through
`Api.set_setting`, which only accepts the keys below; other interface choices (view, filters, last tab…) stay in the
WebView's `localStorage`.

| Key | Default | Where | Description |
|---|---|---|---|
| `language` | `en` | General | interface language: `en` (English) or `it` (Italiano); changing it reloads the app |
| `last_folder` | — | Library | last analysed folder, restored at startup |
| `freesound_key` | — | Store | Freesound API key (the app only shows its first and last characters) |
| `download_dir` | `~/Music/ClusterSound Downloads` | Store | downloads folder |
| `cache_mb` | 300 | General | limit of the temporary cache (50–10000 MB) |
| `live_port` | 8770 | General | port of the bridge for the Max for Live device (1024–65535) |
| `live_library` | Live's User Library | General | where to write the racks for Live |
| `sampler_dir` | `~/Music/ClusterSound Samples` | Recorder | export folder: cuts, stems and enhanced files (Settings › Recorder › *Export folder*) |
| `sampler_max_seconds` | 30 | Recorder | maximum length of an extracted sample |
| `recorder_dir` | `~/Music/ClusterSound Recordings` | Recorder | recordings folder |
| `recorder_format` | — | Recorder | format, bits, bitrate, sample rate and channels |
| `chord_pack_dir` | `~/Documents/Unison MIDI Chord Pack` | Compose | chord pack folder (set by *Choose the folder…*) |

The Drum Rack note mapping is saved with the kit, not in `settings.json`.

The language also decides the texts written into exported files (`README.txt` / `LEGGIMI.txt`, `.license.txt`,
`.source.txt`) and the names of the tracks sent to Live.
