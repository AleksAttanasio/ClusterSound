# Recorder

Registra ciò che il computer manda a una o più **uscite audio**, poi ritaglia i sample dalla registrazione: finiscono
nella libreria e vengono classificati come gli altri. Apre anche qualsiasi file audio o sample della libreria.

![Recorder con regioni sui transienti](../assets/screenshots/recorder.png){ .shot }

La schermata usa tutta la larghezza: la **barra del file** in alto, una **scheda per ogni traccia aperta** sopra
la forma d'onda, il **trasporto** sotto e le **Estrazioni** di tutte le tracce aperte in fondo.

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

Ogni file aperto ha la sua **scheda** sopra la forma d'onda (un file già aperto mostra solo la sua scheda); **+**
ne apre un altro, **×** (o il clic centrale) la chiude, chiedendo prima se ha tagli non ancora esportati. Taglio,
stem, Migliora e trasporto lavorano sulla traccia mostrata.

## Editor e regioni

- Allo stop la registrazione si apre in una nuova scheda. **Trascina** sulla forma d'onda per creare una regione,
  i bordi la ridimensionano, doppio clic per ascoltarla.
- **Clic** sulla forma d'onda per spostarci il **cursore** (e selezionare la regione sotto): la riproduzione parte
  dal cursore, e mentre suona un clic salta lì.
- **Taglia sui transienti** crea una regione per colpo nella parte visibile; il suo **⋯** regola la *Sensibilità*
  (quanti colpi trova).
- Trasporto: **■** stop (il cursore torna all'inizio della traccia), **▶/❚❚** riproduci e pausa dal cursore (la
  pausa lascia il cursore dove si è fermato), **⤢** mostra tutta la traccia.
- Rotella: zoom · `Maiusc`+rotella: scorri · la striscia sotto sposta la vista · `Spazio` riproduci/pausa · `↑` `↓`
  regione precedente/successiva · `Canc` elimina.

## Estrazioni

Tutto ciò che è stato estratto da **tutte le tracce aperte**, in tre schede con una spunta per riga; con più
tracce le righe sono raggruppate sotto il suo nome (clic per mostrare quella traccia):

- **✂ Tagli**: le regioni, tagliate a mano o sui transienti.
- **Stem**: gli stem delle tracce aperte, ritrovati sul disco quando si aprono. Gli stem dello stesso audio
  separato (una traccia, un taglio, un file migliorato) sono raggruppati: clic su un gruppo per aprirlo o chiuderlo,
  la sua spunta li spunta tutti.
- **✨ Migliorati**: i file migliorati ricavati dalle tracce, dai loro tagli o dai loro stem.

Ogni riga ha tasti solo icona: ascolta, mostra la forma d'onda (un taglio viene ingrandito; uno stem o un file
migliorato si apre in una nuova scheda), **Estrai stem** (tagli e file migliorati), ✨ Migliora (tagli e stem) e
**Invia**, lo stesso menu della libreria (un bus del Sequencer o un gruppo del Drum Rack). Stem e file migliorati
hanno anche mostra nel Finder (spento finché il file non è salvato o inviato alla libreria: cliccandolo
propone di fare una delle due) e 🗑 **elimina**: un file temporaneo viene eliminato, uno salvato va nel Cestino dopo
una conferma.

!!! info "Temporanei finché non li salvi"
    Tagli, stem e file migliorati nuovi sono **temporanei**: restano in una cartella di lavoro di ClusterSound
    finché è aperto, e vengono eliminati alla chiusura (○ accanto alla durata). **Esporta tutto** li salva (✓).
    Anche i tagli mandati al Drum Rack o al Sequencer senza salvarli restano temporanei: dopo un riavvio quei pad
    sono vuoti.

Accanto al titolo:

- **Svuota tutto** svuota la scheda, dopo una conferma (stem e file migliorati restano sul disco).
- **Invia a**: le righe spuntate ad **Ableton Live** (una nuova traccia audio ciascuna; senza tagli spuntati,
  tutta la traccia mostrata), al **Drum Rack** (sui pad liberi da quello selezionato) o al **Sequencer** (nuovi layer del bus
  scelto), oppure alla **Libreria**: una copia in `ClusterSound Recorder/<traccia>/` della cartella della libreria
  (chiesta se la libreria è fatta di più cartelle), analizzata come gli altri sample. Live richiede il device
  ClusterSound con *Ricevi* attivo.
- **Esporta tutto** salva le righe spuntate nella **cartella di esportazione** (Impostazioni › Recorder, di base
  `~/Music/ClusterSound Samples/`). I tagli diventano WAV 24 bit con fade (1 ms in, 10 ms out) e normalizzazione
  opzionale, massimo 30 s ciascuno; stem e file migliorati ci vengono spostati con la loro nota di provenienza.

## Estrai stem

Separa la traccia mostrata o la sua regione (o, dalla sua riga, un singolo taglio o file migliorato) in **tracce**,
ognuna un WAV 24 bit con i suoi stem sommati. A sinistra ci sono gli stem (**Batteria, Basso, Chitarra, Piano, Voce,
Altro**): trascinali nelle colonne a destra, una colonna per traccia. Il nome della colonna segue i suoi stem
(*Chitarra + Voce*), lo stesso stem può andare in più tracce e la colonna grigia **Nuova traccia** a destra diventa una
nuova traccia appena ci lasci uno stem. **×** toglie uno stem da una traccia o l'intera traccia. Gli stem che non sono
in nessuna traccia finiscono comunque in una traccia in più, **Altro** (**Resto** se *Altro* è già usato), così la somma
ridà l'originale; togli la spunta per lasciarli fuori. Tre pulsanti impostano una disposizione pronta: **Solo voce**,
**Voce + strumentale** (la seconda traccia, tutti gli stem tranne la voce, si chiama *Strumentale*) e **Tutti gli stem**
(una traccia ciascuno). Se due tracce hanno gli stessi stem, **Estrai** chiede se produrle tutte o solo una per ciascuna. La
disposizione viene ricordata per la volta dopo; la prima volta c'è una traccia per stem. Le tracce si aprono
nell'editor e compaiono nella scheda **Stem**. Gira in
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
