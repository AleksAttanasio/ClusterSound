# Analisi audio

Ogni file passa una sola volta da `library.analyse_file`; il risultato resta nella cache SQLite.

## Preparazione del segnale (`audio_io.py`)

1. **Decodifica** con libsndfile (`soundfile`): wav, aif, flac, ogg, mp3, caf, w64. Si leggono al massimo i primi
   **30 s**; i canali sono mediati in mono float32, i NaN azzerati.
2. **Trim del silenzio**: si tagliano inizio e fine sotto **−60 dB** rispetto al picco, lasciando 2 ms prima del
   primo campione utile (l'attacco resta intatto).
3. **Ricampionamento** con soxr (qualità HQ) in due versioni: **16 kHz** per YAMNet (normalizzato a picco 0,9,
   massimo 10 s) e **32 kHz** per le feature.

## Le 22 feature (`features.py`)

| Gruppo | Feature | Come |
|---|---|---|
| Durata | `duration`, `log_duration` | dopo il trim |
| Inviluppo | `attack` | tempo dal 10% al 90% del picco dell'inviluppo RMS (finestra 10 ms, hop 5 ms) |
| | `decay20` | tempo per scendere di 20 dB dal picco |
| | `t60` | tempo per −60 dB, estrapolato dalla pendenza se non raggiunto (max 10 s) |
| | `tail_ratio` | quota di energia dopo 200 ms dal picco |
| | `env_slope` | pendenza dell'inviluppo in dB/s (solo sopra 0,3 s) |
| Spettro | `centroid`, `rolloff` | baricentro e rolloff 85%, pesati per energia (STFT 2048 / hop 512) |
| | `flatness` | piattezza spettrale sui soli bin attivi (entro 50 dB dal picco del frame) |
| | `zcr` | zero-crossing rate |
| | `band_sub`, `band_low`, `band_lowmid`, `band_highmid`, `band_high` | quota di energia in 0–60, 60–250, 250–2k, 2k–6k, oltre 6k Hz |
| | `centroid_slope` | variazione di log₂ del centroide nel tempo (sweep) |
| Tonalità | `harmonicity`, `f0` | autocorrelazione dei 100 ms più forti (saltati i primi 20 ms di transiente), ricerca 40–1000 Hz dopo il primo minimo negativo |
| Ritmo | `onset_count`, `onset_rate`, `ioi_regularity` | onset multi-banda (sotto); regolarità = coefficiente di variazione degli intervalli |

Per la head le feature con code lunghe passano da `log1p`.

## Profilo mel (144 valori)

Ricavato dal log-mel di YAMNet, allineato al picco del suono:

- **spettro d'attacco** (0–60 ms dopo il picco, 64 bande);
- **spettro del corpo** (60–400 ms, 64 bande);
- **inviluppo** in 16 istanti logaritmici da 0 a 2 s.

I due spettri sono relativi al massimo dello spettro d'attacco, quindi descrivono la *forma* indipendentemente dal
volume. Insieme dicono "cosa succede nel colpo e cosa resta dopo": la differenza tra un kick e un 808, o tra un hat
chiuso e uno aperto.

## Onset multi-banda

Usato per contare i colpi (tipo *Loop*) e per [tagliare sui transienti](recorder-e-slicing.md):

1. STFT 1024 / hop 256; potenza sommata in **8 bande** logaritmiche;
2. ogni banda in dB, con un pavimento a 35 dB sotto la banda più forte;
3. **novelty** = media delle 3 bande con la maggiore salita \(\max(0, dB_t - dB_{t-2})\);
4. frame più di 45 dB sotto il picco ignorati;
5. onset = massimi locali con salita ≥ **9 dB**, distanti almeno **70 ms**.

Misurare la salita in pochi millisecondi su più bande rende il detector insensibile a vibrato e battimenti dei suoni
sostenuti, che non salgono di diversi dB in ~16 ms.

## Tipo

| Tipo | Regola |
|---|---|
| **Loop** | durata ≥ 1,5 s **e** ≥ 4 onset; oppure nome/cartelle con token da loop (`loop`, `bpm`, `groove`, `beat`, `break`, `fill`, `120bpm`…) e durata > 1 s |
| **Long/Texture** | durata ≥ 2,5 s e non è un loop |
| **One-shot** | il resto |

## Misure della tendina (`dynamics.py`)

Calcolate al volo sul file intero (fino a 30 s) quando apri un sample: picco, RMS e crest in dBFS; forma d'onda
(min/max su 1000 punti); inviluppo RMS in dB; **ADSR stimato** — attacco dal 10% del picco, sustain = mediana del
tratto 40–80% dopo il picco, decay fino a 3 dB dal sustain, release dall'ultimo punto sopra sustain − 3 dB fino a
−60 dB; T60; miniatura dello spettrogramma log-mel.
