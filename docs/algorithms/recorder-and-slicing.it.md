# Recorder e slicing

Codice: `sampler/recorder.py`, `capture.py`, `wasapi.py`, `native/cs_tap.swift`, `sampler/slicing.py`,
`sampler/session.py`, `sampler/export.py`.

## Registrare l'uscita audio

Il Recorder deve catturare **ciò che un dispositivo riproduce**, anche più dispositivi insieme, senza driver virtuali.
Ogni uscita scelta è una `Track` con il suo backend e il suo `Writer`; partono insieme e un errore su un dispositivo non
ferma gli altri (la registrazione fallisce solo se falliscono tutti).

| Piattaforma | Backend | Come |
|---|---|---|
| macOS 14.2+ | `cs-tap` | helper Swift con i **Core Audio process tap**: riceve lo stesso audio che il dispositivo riproduce; esclude il processo di ClusterSound (`--exclude-pid`); scrive un'intestazione JSON e poi PCM float32 su stdout |
| macOS, senza helper | ScreenCaptureKit | solo *Tutte le uscite*: uno stream video minimo (2×2 px, 1 fps) obbligatorio, audio 48 kHz stereo, audio dell'app escluso |
| Windows | WASAPI loopback (`soundcard`) | un thread per uscita con la sua inizializzazione COM, 48 kHz, blocchi da 1024 frame; il "mix" è l'uscita predefinita |

Il `Writer` crea il file al primo blocco (quando conosce i canali), mappa i canali (mono = media, stereo, tutti),
ricampiona in streaming con `soxr.ResampleStream` se serve e scrive con libsndfile (WAV, AIFF, FLAC, CAF, MP3 a
bitrate costante, OGG, Opus a 48 kHz). M4A passa da un CAF intermedio convertito con `afconvert`. Un meter RMS per
traccia alimenta la UI.

I flussi protetti registrano silenzio: nulla viene decifrato.

## Taglio sui transienti

Usa il detector di onset [multi-banda](audio-analysis.md#onset-multi-banda), adattato a registrazioni lunghe:

1. **Sensibilità** → soglia di salita: lineare da **18 dB** (0) a **4 dB** (1).
2. **Blocchi** di 30 s con 1 s di sovrapposizione: ogni blocco "possiede" l'intervallo \([a + 0{,}5,\; a + \text{hop} +
   0{,}5)\) s, così un onset vicino al bordo è contato una volta sola; al primo blocco si antepongono 50 ms di silenzio
   perché un colpo a t = 0 mostri una salita. Onset entro 30 ms sono fusi.
3. **Regioni**: da 5 ms prima dell'onset (pre-roll) fino al successivo meno il pre-roll (senza durata
   massima); ogni regione è poi accorciata all'ultima finestra RMS di 10 ms sopra **−50 dB** rispetto al suo
   picco (via le code di silenzio). Regioni sotto 30 ms vengono scartate.

## Rendering dei sample

Quando una regione diventa un file (`slicing.render`):

- l'inizio si sposta al **passaggio per lo zero** più vicino, al massimo 2 ms prima (niente click);
- fade-in di 1 ms e fade-out di 10 ms;
- normalizzazione opzionale a −0,3 dBFS;
- WAV 24 bit in `<cartella sample>/<sorgente>/<titolo>/`, con `.license.txt` (link dello Store) o `.source.txt`
  (registrazioni: uso privato). Una regione già esportata e non modificata riusa il file.

Le sorgenti sono limitate a 20 minuti (oltre vengono troncate e segnalate); la forma d'onda è calcolata come colonne
min/max con `np.minimum.reduceat` / `np.maximum.reduceat` per la larghezza visibile.

## Link

`links.py` riconosce i link di Freesound, Internet Archive, ccMixter, Openverse e Wikimedia Commons e li risolve con le
API dei provider (un pack zip di ccMixter viene sostituito dalla sua anteprima, perché l'editor apre un solo file);
i link di servizi di streaming (YouTube, Spotify, SoundCloud…) vengono rifiutati con una spiegazione.
