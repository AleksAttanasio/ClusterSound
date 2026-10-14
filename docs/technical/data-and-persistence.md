# Data and persistence

## Folders

| | macOS | Windows |
|---|---|---|
| Data (`paths.data_dir()`) | `~/Library/Application Support/ClusterSound` | `%APPDATA%\ClusterSound` |
| Cache (`paths.cache_dir()`) | `~/Library/Caches/ClusterSound` | `%LOCALAPPDATA%\ClusterSound\Cache` |
| User output | `~/Music/ClusterSound Downloads · Samples · Recordings · Patterns` | the same under `~\Music` |

In the data folder:

| File | Content |
|---|---|
| `settings.json` | settings, including the interface language (see [Reference](../reference/settings.md)) |
| `cache.sqlite` | analysis of every file, manual labels, projections |
| `snapshots/<sha1(root)>.npz` | complete state of a folder, for an instant startup |
| `patterns.json` | the user's patterns, variants, sequences and Compose progressions |
| `racks.json` | saved Drum Rack kits |
| `live_kit.json` | current Sequencer kit for the Live device |
| `models/demucs`, `models/apollo` | downloaded model weights, with a `.ready` marker |

In the cache: `previews/` (online previews, LRU with a limit in MB) and `bin/cs-tap` (compiled helper).

## Analysis cache (`cache.py`)

SQLite in **WAL** mode with three tables:

| Table | Columns | Use |
|---|---|---|
| `files` | `path` (PK), `mtime`, `size`, `version`, `blob` | result of `analyse_file` |
| `labels` | `path`, `cls` | the user's manual corrections |
| `projections` | `key`, `blob` | 3D layout, key = SHA-1 of folder + file list |

The `blob` is an `np.savez` archive with the float16 arrays (`embedding` 1024, `profile` 144, `scores_max` and
`scores_mean` 521) and a `__meta__` JSON (features and file info). A file is reused if `mtime` and `size` match
and `version == ANALYSIS_VERSION` (4 today): changing the analysis invalidates the cache safely. The rows of a
folder are read with a single query on a range of paths; during the scan a commit is made every 200 files.

## Snapshots (`snapshot.py`)

A snapshot is the whole final state of a folder (items, classes, subclusters, coordinates) in an `.npz`. It is valid
only if a SHA-1 fingerprint of these matches:

- snapshot and analysis version;
- `mtime` and size of the base head;
- every path with `mtime` and size;
- the manual labels of those paths.

If the fingerprint matches, nothing is analysed, classified or projected at startup. The last 5 snapshots are kept;
writing is atomic (temporary file + rename).

## User saves

`patterns.json` and `racks.json` are written atomically under a lock; the ids have a type prefix
(`rack:` + 10 hex characters). Compose progressions live in `patterns.json` with all their versions and melodies.

## Exports

| From | What |
|---|---|
| Library | CSV/JSON report (`export.py`): path, class, confidence, alternatives, subcluster, type |
| Sequencer | MIDI, WAV, Ableton folder (`.adg`, `.mid`, `.wav`, `README.txt`, `.license.txt`) |
| Drum Rack | Ableton folder; for the SPD-SX also 16-bit / 44.1 kHz WAVs |
| Compose | type 0 (chords) or type 1 (chords + layers) MIDI, 480 PPQ |
| Recorder | 24-bit WAV with `.license.txt` or `.source.txt` |

The texts written into exported files (`README.txt`, `.license.txt`, `.source.txt`, track names) follow the
interface language: with Italian chosen the README is `LEGGIMI.txt`.

The `.adg` racks are gzipped XML generated from neutral Live 10 templates (`patterns/templates/live10_racks.xml.gz`),
with sample paths relative to the preset: the exported folder can be moved.
