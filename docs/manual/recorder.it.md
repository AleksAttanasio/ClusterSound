# Recorder

Registra ciò che il computer manda a una o più **uscite audio**, poi ritaglia i sample dalla registrazione: finiscono
nella libreria e vengono classificati come gli altri. Apre anche qualsiasi file audio o sample della libreria.

![Recorder con regioni sui transienti](../assets/screenshots/recorder.png){ .shot }

La schermata usa tutta la larghezza: la **barra del file** in alto, la forma d'onda, il **trasporto** sotto e le
**Estrazioni** dell'audio aperto in fondo.

## Registrare

- **● Registra** è nel trasporto, con l'orologio e un piccolo meter per uscita (passaci sopra per il nome
  dell'uscita). Il ⚠ giallo accanto ricorda la nota legale qui sotto; ⋯ apre le impostazioni del Recorder.
- **Uscite**: casse, cuffie, interfacce audio, AirPlay… più *Tutte le uscite (mix)* (su Windows *Uscita
  predefinita*). Più uscite partono insieme, ognuna con il suo file e il suo meter. *Aggiorna l'elenco* rilegge i
  dispositivi.
- **Formato** (Impostazioni › Recorder): WAV 16/24 bit o 32 float, AIFF, FLAC 16/24, CAF, MP3 128–320 kbps, OGG
  Vorbis, Opus (48 kHz), M4A/AAC (solo macOS). Frequenza del dispositivo o 44,1/48/96 kHz; stereo, mono o tutti i
  canali (formati non compressi).
- **Cartella**: `~/Music/ClusterSound Recordings/<data ora> - <uscita>.<ext>` con un `.source.txt` di provenienza.
  La registrazione continua anche cambiando sezione.

## Aprire audio

La barra del file mostra il percorso dell'audio aperto. Il suo tasto cartella chiede da dove aprire: **Cartella
locale…** (qualsiasi file audio del computer), **Libreria dei sample…** (sample e loop per cartella, pack o nome)
o una delle **Registrazioni recenti** della sessione. Si apre anche un file audio trascinato dal Finder sulla forma
d'onda.

## Editor e regioni

- Allo stop la registrazione si apre nell'editor. **Trascina** sulla forma d'onda per creare una regione, i bordi
  la ridimensionano, clic per ascoltarla.
- **Taglia sui transienti** crea una regione per colpo nella parte visibile; *Sensibilità* regola quanti colpi
  trova.
- Trasporto: **■** stop (torna all'inizio), **▶/❚❚** riproduci e pausa (riparte da dove si era fermato), **⤢**
  mostra tutta la traccia.
- Rotella: zoom · `Maiusc`+rotella: scorri · la striscia sotto sposta la vista · `Spazio` riproduci/pausa · `↑` `↓`
  regione precedente/successiva · `Canc` elimina.

## Estrazioni

Tre schede, con una spunta per riga:

- **✂ Tagli**: le regioni, tagliate a mano o sui transienti.
- **Stem**: gli stem già estratti dall'audio aperto, ritrovati sul disco quando si apre.
- **✨ Migliorati**: i file migliorati ricavati dall'audio, dai suoi tagli o dai suoi stem.

Ogni riga ha tasti solo icona: ascolta, mostra la forma d'onda (un taglio viene ingrandito; uno stem o un file
migliorato si apre nell'editor, e le liste restano quelle della sua sorgente), ✨ Migliora (tagli e stem) e
**Invia**, lo stesso menu della libreria (un bus del Sequencer o un gruppo del Drum Rack).

Accanto al titolo:

- **Svuota tutto** svuota la scheda, dopo una conferma (stem e file migliorati restano sul disco).
- **Invia a**: le righe spuntate ad **Ableton Live** (una nuova traccia audio ciascuna; senza tagli spuntati,
  tutto l'audio), al **Drum Rack** (sui pad liberi da quello selezionato) o al **Sequencer** (nuovi layer del bus
  scelto). Live richiede il device ClusterSound con *Ricevi* attivo.
- **Esporta tutto**: le righe spuntate nella **cartella di esportazione** (Impostazioni › Recorder, di base
  `~/Music/ClusterSound Samples/`). I tagli diventano WAV 24 bit con fade (1 ms in, 10 ms out) e normalizzazione
  opzionale, massimo 30 s ciascuno; stem e file migliorati vengono copiati con la loro nota di provenienza.

## Estrai stem

Separa la registrazione o la regione in **Batteria, Basso, Chitarra, Piano, Voce** (quelli che spunti) più sempre
**Altro** con il resto, così la somma ridà l'originale. Un WAV 24 bit per stem, apribile nell'editor. Gli stem compaiono nella scheda **Stem**. Gira in
locale con Demucs (extra `stems`, modello da 55 MB scaricato al primo uso). Dettagli: [Demucs](../ai/demucs.md).

## Migliora

Pulsante viola ✨, anche su ogni taglio e stem: **restauro AI** che ricostruisce le alte frequenze tagliate e ripulisce
gli artefatti della compressione (MP3, streaming). Il risultato è un nuovo file `… (migliorato).wav`, elencato nella
scheda **Migliorati**; l'originale resta com'è. Gira in locale con Apollo (extra `enhance`, 66 MB). Dettagli: [Apollo](../ai/apollo.md).

!!! warning "Nota legale"
    Nulla viene decifrato o aggirato: le app che proteggono il flusso registrano silenzio. Le registrazioni sono
    per uso personale (copia privata); per pubblicare un brano che contiene un sample servono i diritti
    sull'originale, oppure un sample con licenza libera. Non esiste una soglia di secondi sotto la quale un sample
    è libero.

!!! info "Windows"
    Ogni uscita è registrata in WASAPI loopback: non c'è un mix di tutte le uscite, nella registrazione finisce
    anche l'audio di ClusterSound e il formato M4A non è disponibile. Nessun permesso da concedere.
