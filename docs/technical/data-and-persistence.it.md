# Dati e persistenza

## Cartelle

| | macOS | Windows |
|---|---|---|
| Dati (`paths.data_dir()`) | `~/Library/Application Support/ClusterSound` | `%APPDATA%\ClusterSound` |
| Cache (`paths.cache_dir()`) | `~/Library/Caches/ClusterSound` | `%LOCALAPPDATA%\ClusterSound\Cache` |
| Output utente | `~/Music/ClusterSound Downloads · Samples · Recordings · Patterns` | idem sotto `~\Music` |

Nella cartella dei dati:

| File | Contenuto |
|---|---|
| `settings.json` | impostazioni (vedi [Riferimento](../reference/settings.md)) |
| `cache.sqlite` | analisi di ogni file, etichette manuali, proiezioni |
| `snapshots/<sha1(root)>.npz` | stato completo di una cartella, per l'avvio istantaneo |
| `patterns.json` | pattern, varianti, sequenze e progressioni di Compose dell'utente |
| `racks.json` | kit del Drum Rack salvati |
| `live_kit.json` | kit corrente del Sequencer per il device di Live |
| `models/demucs`, `models/apollo` | pesi dei modelli scaricati, con un marcatore `.ready` |

Nella cache: `previews/` (anteprime online, LRU con limite in MB) e `bin/cs-tap` (helper compilato).

## Cache delle analisi (`cache.py`)

SQLite in modalità **WAL** con tre tabelle:

| Tabella | Colonne | Uso |
|---|---|---|
| `files` | `path` (PK), `mtime`, `size`, `version`, `blob` | risultato di `analyse_file` |
| `labels` | `path`, `cls` | correzioni manuali dell'utente |
| `projections` | `key`, `blob` | layout 3D, chiave = SHA-1 di cartella + elenco dei file |

Il `blob` è un archivio `np.savez` con gli array float16 (`embedding` 1024, `profile` 144, `scores_max` e
`scores_mean` 521) e un JSON `__meta__` (feature e info del file). Un file è riusato se `mtime` e `size` coincidono
e `version == ANALYSIS_VERSION` (oggi 4): cambiare l'analisi invalida la cache in modo sicuro. Le righe di una
cartella si leggono con una sola query per intervallo di percorsi; durante la scansione si fa commit ogni 200 file.

## Snapshot (`snapshot.py`)

Uno snapshot è l'intero stato finale di una cartella (item, classi, sottocluster, coordinate) in un `.npz`. È valido
solo se coincide un'impronta SHA-1 di:

- versione dello snapshot e dell'analisi;
- `mtime` e dimensione della head base;
- ogni percorso con `mtime` e dimensione;
- le etichette manuali di quei percorsi.

Se l'impronta coincide, all'avvio non si analizza, classifica o proietta nulla. Si tengono gli ultimi 5 snapshot;
la scrittura è atomica (file temporaneo + rename).

## Salvataggi dell'utente

`patterns.json` e `racks.json` sono scritti in modo atomico sotto un lock; gli id hanno un prefisso di tipo
(`rack:` + 10 caratteri esadecimali). Le progressioni di Compose stanno in `patterns.json` con tutte le versioni e le melodie.

## Export

| Da | Cosa |
|---|---|
| Libreria | report CSV/JSON (`export.py`): percorso, classe, confidenza, alternative, sottocluster, tipo |
| Sequencer | MIDI, WAV, cartella Ableton (`.adg`, `.mid`, `.wav`, `LEGGIMI.txt`, `.license.txt`) |
| Drum Rack | cartella Ableton; per SPD-SX anche WAV 16 bit / 44,1 kHz |
| Compose | MIDI tipo 0 (accordi) o tipo 1 (accordi + layer), 480 PPQ |
| Recorder | WAV 24 bit con `.license.txt` o `.source.txt` |

I rack `.adg` sono XML gzip generati da template neutri di Live 10 (`patterns/templates/live10_racks.xml.gz`),
con percorsi dei sample relativi al preset: la cartella esportata si può spostare.
