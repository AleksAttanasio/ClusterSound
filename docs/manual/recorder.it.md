# Recorder

Registra ciò che il computer manda a una o più **uscite audio**, poi ritaglia i sample dalla registrazione: finiscono
nella libreria e vengono classificati come gli altri. Apre anche qualsiasi file audio o sample della libreria.

![Recorder con regioni sui transienti](../assets/screenshots/recorder.png){ .shot }

## Registrare

- **Uscite**: casse, cuffie, interfacce audio, AirPlay… più *Tutte le uscite (mix)* (su Windows *Uscita
  predefinita*). Più uscite partono insieme, ognuna con il suo file e il suo meter. *Aggiorna l'elenco* rilegge i
  dispositivi.
- **Formato** (Impostazioni › Recorder): WAV 16/24 bit o 32 float, AIFF, FLAC 16/24, CAF, MP3 128–320 kbps, OGG
  Vorbis, Opus (48 kHz), M4A/AAC (solo macOS). Frequenza del dispositivo o 44,1/48/96 kHz; stereo, mono o tutti i
  canali (formati non compressi).
- **Cartella**: `~/Music/ClusterSound Recordings/<data ora> - <uscita>.<ext>` con un `.source.txt` di provenienza.
  La registrazione continua anche cambiando sezione.

## Aprire audio

*Apri file…* (o trascina dal Finder sulla forma d'onda) apre qualsiasi file audio; *Dalla libreria…* apre sample e
loop navigando per cartelle e pack o cercando per nome.

## Editor e regioni

- Allo stop la registrazione si apre nell'editor. **Trascina** sulla forma d'onda per creare una regione, i bordi
  la ridimensionano, clic per ascoltarla.
- **Taglia sui transienti** crea una regione per colpo nella parte visibile; *Sensibilità* regola quanti colpi
  trova.
- Rotella: zoom · `Maiusc`+rotella: scorri · la striscia sotto sposta la vista · `Spazio` play/stop · `↑` `↓`
  regione precedente/successiva · `Canc` elimina.

## Esportare

- **Esporta selezionate**: WAV 24 bit in `~/Music/ClusterSound Samples/`, con fade (1 ms in, 10 ms out) e
  normalizzazione opzionale, massimo 30 s ciascuno.
- **Al Drum Rack**: carica le regioni sui pad liberi dal pad selezionato, in ordine di nota, e apre il Drum Rack.
- **Invia a Live**: una nuova traccia audio in Ableton con la regione (o tutto l'audio), nel primo slot vuoto
  della scena selezionata. Serve il device ClusterSound con *Ricevi* attivo.

## Estrai stem

Separa la registrazione o la regione in **Batteria, Basso, Chitarra, Piano, Voce** (quelli che spunti) più sempre
**Altro** con il resto, così la somma ridà l'originale. Un WAV 24 bit per stem, apribile nell'editor. Gira in
locale con Demucs (extra `stems`, modello da 55 MB scaricato al primo uso). Dettagli: [Demucs](../ai/demucs.md).

## Migliora

Pulsante viola ✨, anche su ogni regione: **restauro AI** che ricostruisce le alte frequenze tagliate e ripulisce
gli artefatti della compressione (MP3, streaming). Il risultato è un nuovo file `… (migliorato).wav`; l'originale
resta com'è. Gira in locale con Apollo (extra `enhance`, 66 MB). Dettagli: [Apollo](../ai/apollo.md).

!!! warning "Nota legale"
    Nulla viene decifrato o aggirato: le app che proteggono il flusso registrano silenzio. Le registrazioni sono
    per uso personale (copia privata); per pubblicare un brano che contiene un sample servono i diritti
    sull'originale, oppure un sample con licenza libera. Non esiste una soglia di secondi sotto la quale un sample
    è libero.

!!! info "Windows"
    Ogni uscita è registrata in WASAPI loopback: non c'è un mix di tutte le uscite, nella registrazione finisce
    anche l'audio di ClusterSound e il formato M4A non è disponibile. Nessun permesso da concedere.
