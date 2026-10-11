# ClusterSound

App desktop per macOS che analizza una cartella di sample audio (ricorsivamente), assegna ogni
file a una classe di suono — kick, snare, hat, … — e mostra l'intera libreria come nuvola 3D in
cui suoni simili stanno vicini e il colore di ogni punto è la sua classe. I file originali non
vengono mai modificati.

## Uso

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -e ".[dev]"
.venv/bin/python -m clustersound            # GUI
.venv/bin/python -m clustersound --headless ~/Samples --out report.csv   # batch, senza GUI
```

- **Scegli cartella…**: analizza wav/aif/flac/ogg/mp3/caf. I risultati finiscono in cache
  (`~/Library/Application Support/ClusterSound/cache.sqlite`): una riscansione rilegge solo i
  file nuovi o modificati.
- **Vista 3D**: trascina per ruotare, scroll per lo zoom, tasto destro per spostare.
  **Clic su un punto** = riproduzione immediata e apertura della tendina di dettaglio.
- **Tendina**: forma d'onda + inviluppo RMS in dB con fasi ADSR stimate, spettrogramma
  (clic per riprodurre da quel punto), peak/RMS/crest, attack/decay/sustain/release, T60,
  formato. Azioni: *Mostra nella cartella* (Finder), *Trova simili*, cambio classe.
- **Correzioni**: cambiare la classe di un sample la rende un esempio di training; le altre
  classificazioni si aggiornano in pochi secondi. Le etichette manuali restano in cache.
- **Filtri**: classe (clic; Alt+clic = solo quella), tipo (One-shot / Loop / Long), confidenza
  minima, ricerca per nome. **Lista**: tabella ordinabile, frecce ↑↓ per scorrere e ascoltare.
- **Esporta report**: CSV o JSON con classe, confidenza, alternative, sottocluster, tipo.

Scorciatoie: `Spazio` play/stop, `Esc` chiude la tendina.

## Classi

| Gruppo | Classi |
|---|---|
| Drums | Kick, 808/Sub Kick, Tom, Snare, Rimshot/Sidestick, Clap, Snap, Closed Hat, Open Hat, Ride, Crash, Other Cymbal |
| Percussion | Shaker, Tambourine, Cowbell, Woodblock/Clave, Conga/Bongo/Hand Drum, Bell/Triangle, Other Perc |
| Melodic/Bass | Bass, Synth (lead/pluck), Pad, Keys/Piano, Guitar, Strings, Brass/Wind, Mallets |
| Vocal | Vocal/Vox, Spoken/Chant |
| FX & altro | Riser/Sweep, Impact/Hit, Downlifter, Noise/Texture/Ambience, Foley, *Unsorted* (bassa confidenza) |

Ogni sample ha anche un **Tipo** (One-shot / Loop / Long-Texture) e un **sottocluster** dentro
la sua classe (k-means sugli embedding, k scelto con silhouette).
Colori, keyword e mappatura AudioSet stanno in `clustersound/taxonomy.py`.

## Scheda Online: sample gratuiti

Il tab **Online** in alto (alternato a **Libreria**) cerca sample gratuiti su quattro fonti e li
mostra raggruppati **per fonte** oppure **per strumento**:

| Fonte | Cosa offre | Accesso |
|---|---|---|
| Freesound | ~600k suoni CC (one-shot, loop, field recording) con BPM, tonalità, waveform | API key gratuita (⚙ → "richiedi una chiave") |
| Openverse | Aggregatore CC (Freesound, Wikimedia Commons) | anonimo, limiti di frequenza bassi |
| Internet Archive | Sample pack interi, sfogliabili file per file anche dentro gli ZIP | anonimo |
| ccMixter | Stem, a cappella e loop CC | anonimo |

- **Filtro per strumento**: le stesse 34 classi e gli stessi colori della libreria. Ogni fonte
  riceve la query nel proprio formato (tag Freesound, ricerca Openverse, subject/title su IA, tag
  ccMixter), poi ogni risultato viene etichettato da titolo/tag/cartelle con lo stesso parser dei
  nomi della libreria. I falsi positivi non musicali ("soccer kick", "waves crashing") vengono scartati.
- **Altri filtri**: fonte, licenza (CC0/PD, BY, BY-SA, NC, ND, non dichiarata), *solo uso
  commerciale*, tipo (one-shot/loop/long), durata, BPM, tonalità, solo lossless, file singoli o
  pack, ordinamento. Accanto a ogni filtro un'etichetta (FS·OV·IA·CC) indica quali fonti lo applicano
  lato server; sulle altre viene applicato localmente.
- **Anteprima**: ▶ riproduce subito (l'audio passa da Python, con cache in `~/Library/Caches/ClusterSound`).
- **Download** (⬇): in `~/Music/ClusterSound Downloads/<Fonte>/` (configurabile), con accanto un
  `.license.txt` che riporta autore, licenza, link e testo di attribuzione. Da Freesound senza
  login OAuth si scarica l'anteprima HQ mp3; l'originale si scarica dalla pagina (↗).
- I pack di Internet Archive che sembrano librerie commerciali ricaricate con una licenza libera
  (Big Fish Audio, Sound Ideas, Loopmasters, GarageBand…) sono marcati ⚠ e nascosti per default;
  quelli senza licenza dichiarata compaiono solo se scegli "Non dichiarata".

## Come classifica

Quattro segnali fusi in log-probabilità (`clustersound/classifier.py`):

1. **Nome e cartelle**: keyword tipiche dei sample pack (`kick|kck|bd`, `snr|sd`, `hh|chh`,
   `oh|open hat`, `808`, `perc`, `vox`, `riser`, …); il nome del file pesa più delle cartelle.
2. **YAMNet** (MobileNet, AudioSet): embedding a 1024 dimensioni e score zero-shot,
   eseguito in **numpy puro** (`yamnet_np.py`, pesi float16 da 6.9 MB). Niente
   TensorFlow/PyTorch/onnxruntime: l'onnxruntime da solo avrebbe aggiunto ~70 MB.
3. **Feature acustiche**: attack, decay, T60, bande di energia, flatness, armonicità, onset,
   più un profilo spettro-temporale (spettro d'attacco e del corpo, inviluppo) con regole leggere.
4. **Due head MLP** (numpy) su embedding + profilo + feature:
   - una **head base** inclusa nell'app (`models/base_head.npz`, 0.6 MB), addestrata su ~27k
     sample etichettati;
   - una **head auto-addestrata** su ogni libreria: i file con un nome chiaro diventano esempi
     di training, così vengono classificati bene anche i file con nomi anonimi della stessa libreria.

La vista 3D è una t-SNE (numpy, con landmark oltre 2500 file) su embedding + probabilità di classe.
Durante il calcolo viene mostrata subito una PCA.

### Accuratezza misurata

`tools/evaluate.py` nasconde nome e cartelle dei file e confronta la classe prevista con quella
indicata dal nome. Libreria reale di test: 4.932 file, 2.845 etichettati. La head base è stata
addestrata su **altri** ~22k sample (duplicati esclusi).

| Scenario | Tutti | Solo one-shot |
|---|---|---|
| File senza nome, ma la libreria contiene altri file con nomi (caso tipico) | 72% | 77% |
| Nessun nome in tutta la libreria (solo audio + head base) | 57% | 65% |
| Solo YAMNet zero-shot + regole, senza head (riferimento) | 16% | — |

I file con un nome parlante vengono classificati quasi sempre in base al nome. Gli errori residui
sono soprattutto confusioni tra classi vicine (snare/clap/rimshot, closed/open hat, bass/synth)
e rumore delle etichette (es. "snare roll" dentro un fill di batteria).

## Build dell'app

```bash
.venv/bin/pyinstaller --noconfirm ClusterSound.spec   # -> dist/ClusterSound.app
```

## Strumenti di sviluppo

- `tools/build_yamnet_npz.py` — converte i pesi Keras di YAMNet nel modello numpy.
- `tools/train_base_head.py` — riaddestra la head base su una o più librerie.
- `tools/evaluate.py` — accuratezza a nomi nascosti (`--oneshots`, `--all-hidden`, `--no-base`).
- `tools/devserver.py` — UI in un browser normale con l'API Python via HTTP.
- `pytest` — test su segnali sintetici e pipeline end-to-end; per le fonti online usa risposte registrate
  in `tests/fixtures/online` (`CLUSTERSOUND_NETWORK_TESTS=1 pytest` interroga anche i servizi reali).
