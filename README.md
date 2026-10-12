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

## Store: sample e pack gratuiti (Libreria → Store)

Nella scheda **Libreria** il selettore **La mia libreria | Store** passa dalla cartella locale a uno
store di sample gratuiti. Ci si arriva anche dalla libreria vuota ("Sfoglia lo Store gratuito") e
dalla tendina di un sample ("Altri nello Store": apre lo store sulla stessa classe).

- **Home**: i provider con il loro logo, le categorie (Kick, Snare, Hat, 808…), i pack in evidenza
  di Freesound e Internet Archive, i nuovi suoni CC0 e una **vetrina** di pack royalty-free.
- **Risultati**: *Suoni* o *Pack*, in griglia (card con forma d'onda, licenza, durata, BPM,
  tonalità) oppure nella lista classica raggruppata per fonte o per strumento.
- **Pagina pack**: descrizione, licenza, numero di suoni e download, "Ascolta tutto", "Scarica pack",
  tracce una per una e gli altri pack dello stesso autore. Per Freesound i nomi dei pack arrivano
  con la ricerca (`group_by_pack`), senza richieste aggiuntive.
- **Pagina provider**: descrizione, licenze tipiche, link al sito e i suoi pack/suoni.
- Se la cartella dei download sta dentro la cartella della libreria aperta, a fine download la
  libreria si riscansiona da sola (i file già analizzati vengono dalla cache); altrimenti il pannello
  dei download offre "Apri in libreria".

| Fonte | Cosa offre | Accesso |
|---|---|---|
| Freesound | ~600k suoni CC (one-shot, loop, field recording) con BPM, tonalità, waveform, organizzati in pack | API key gratuita (⚙ → "richiedi una chiave") |
| Openverse | Aggregatore CC (Freesound, Wikimedia Commons) | anonimo, limiti di frequenza bassi |
| Internet Archive | Sample pack interi, sfogliabili file per file anche dentro gli ZIP | anonimo |
| ccMixter | Stem, a cappella e loop CC | anonimo |

La **vetrina** (`clustersound/online/catalog.py`) elenca pack di siti senza API pubblica, tutti
utilizzabili in produzioni commerciali: Kenney (CC0), Sonniss GameAudioGDC, 99Sounds e SampleRadar
(royalty-free, vietata la ridistribuzione dei file così come sono). Il pulsante apre la pagina
ufficiale da cui scaricarli: niente scraping. I loghi stanno in `clustersound/ui/assets/providers/`.

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

## Scheda Sequencer: prova dei sample su groove tipici

La seconda scheda (**Libreria | Sequencer | Drum Rack | Compose**) è un sequencer per provare i sample su pattern tipici e portarli in Ableton.

- **47 generi, 191 pattern**, con la bass music in primo piano:
  - *Bass music UK*: UK garage 2-step, speed garage, bassline, UK funky, grime, dubstep, riddim, tearout, halftime, breaks, future garage;
  - *Drum & bass / jungle*: liquid, rollers, jump-up, neurofunk, dancefloor, jungle (amen), minimal, drumfunk, footwork;
  - *Hip hop / trap*: boom bap, lo-fi, trap, UK e NY drill, phonk, memphis, jersey club, baltimore club;
  - *House / techno*: house, deep, tech house, techno, minimal, electro, trance, hardstyle, disco;
  - *Global*: afrobeats, amapiano, reggaeton/dembow, dancehall, moombahton, pop, funk, rock, breakbeat.

  Ogni genere ha le sue varianti tipiche più *Fill* e *Breakdown* generate automaticamente, con BPM, swing e tonalità del genere. **Varia** crea una variazione; **Salva variante** la salva tra le tue (★).
- **Bus separati**: Kick, Snare, Clap, Rim, Closed Hat, Open Hat, Ride/Crash, Perc, Tom, FX e Bass. Ogni bus ha step, volume, pan, filtro, mute/solo e meter.
- **Layer**: ogni bus può avere più sample che suonano insieme (es. 3 snare nel bus Snare), ciascuno con volume, pitch, offset in ms, mute/solo ed eventualmente step propri.
- **Step**: clic per accendere/spegnere, Shift per l'accento, Alt per la ghost note, tasto destro per i roll ×2/×3/×4. Hi-hat chiuso e aperto sono in choke.
- **Basso**: piano-roll con glide (Alt+clic su una nota); la radice del sample viene rilevata da sola, così il basso suona intonato.
- **Invio ai bus**: dalla Libreria (tasto destro su un punto 3D o su una riga, oppure "Invia ▾" nella tendina) e dallo Store (→), come nuovo layer o al posto di quello selezionato.
- **Alternanza dei layer**: quando un bus ha 2 o più layer, accanto al nome scegli come suonano:
  - *insieme*: tutti a ogni colpo;
  - *a giro*: uno dopo l'altro;
  - *casuale*: un layer estratto a caso per ogni colpo, uguale a ogni giro (⚄ rifà l'estrazione);
  - *casuale ogni giro*: un'estrazione nuova a ogni ripetizione.

  L'export registra esattamente quello che senti: nel Drum Rack ogni layer alternato ha il suo pad e il MIDI suona quello giusto (con *casuale ogni giro* viene registrato il primo giro).
- **🎲 Kit casuale**: per ogni bus che suona sceglie a caso un gruppo di sample simili (classe e sotto-gruppo) e ne prende sample a caso. Puoi chiedere 1, 2 o 4 sample per bus (alternati a caso), limitare la scelta a una cartella o pack e tenere solo i one-shot. I bus bloccati con 🔒 non cambiano, e il groove resta lo stesso.
- **▦ Carica dal Drum Rack**: porta i sample del Drum Rack nei bus della loro classe (vedi sotto).
  - I sample online restano in una **cache temporanea limitata** (300 MB, configurabile in ⚙ insieme a "Svuota cache"); diventano file veri solo quando esporti.
- **Export**:
  - **MIDI**, con mappatura Drum Rack (pad consecutivi da C1) o General MIDI;
  - **WAV** del loop;
  - **Esporta per Ableton**: una cartella con
    - `Samples/<Bus>/…wav`, più un `.license.txt` per i sample online;
    - `… Drum Rack.adg`: un pad per bus, con Instrument Rack annidato quando il bus ha più layer;
    - `… Bass.adg`: Simpler mono con nota radice e glide;
    - `Drums.mid`, `Bass.mid`, `Loop.wav` e `LEGGIMI.txt` con i 3 passi da fare in Live.

- **Sequenza (arrangiamento)**: nel pannello *Sequenza* sopra la griglia componi una scaletta di pattern, anche di generi diversi:
  - per aggiungere un pattern trascina un chip di variante (o fai doppio clic), oppure usa "+ Pattern corrente";
  - le card si riordinano trascinandole e hanno ×N ripetizioni, duplica, rinomina ed elimina;
  - ogni card mostra la miniatura del groove ed è larga in proporzione alle battute;
  - clic su una card: la griglia mostra e modifica quel blocco;
  - "Play sequenza" fa scorrere un cursore sulla timeline e, con "Segui", la griglia mostra il blocco che suona;
  - kit e BPM sono condivisi, mentre lo swing resta quello di ogni blocco;
  - "Esporta sequenza" crea MIDI, WAV o il pacchetto Ableton dell'intera sequenza, con `Sequenza.wav` e la scaletta in `LEGGIMI.txt`;
  - "Salva…" e "Apri…" gestiscono le sequenze salvate.

  Verificato con Ableton Live 10.1: i preset si aprono con i sample al loro posto.

## Scheda Drum Rack: kit per Launchpad Pro (64 pad) e Roland SPD-SX

La quarta scheda costruisce un Drum Rack 8×8 pensato per un controller come il Novation Launchpad Pro MK3.

- **Mappatura delle note**: *Launchpad / Live* (default), cioè 4 quadranti 4×4 con 36–51 in basso a sinistra, 52–67 in basso a destra, 68–83 in alto a sinistra e 84–99 in alto a destra; oppure *righe sequenziali* (36 + riga×8 + colonna), per le Custom Mode.
- **Geometrie**: ognuna divide i 64 pad in gruppi di sample simili; i pad restano al loro posto quando cambi geometria.
  - *Colonne ×8*: 8 colonne da 8 (es. tutti gli hat su una colonna);
  - *Blocchi 2×2*: 16 gruppi da 4;
  - *Blocchi 4×4*: 4 quadranti da 16;
  - *4×4 a colonne*: ogni quadrante è una famiglia e ogni colonna un gruppo di 4 (gruppi diversi della stessa classe prendono sotto-cluster diversi);
  - *Libero*: un pad alla volta.
- **Seed**: è l'ultimo sample cliccato, nel browser a sinistra o su un pad. **Riempi gruppo** mette il seed sul pad selezionato e i sample simili sugli altri pad del gruppo.
- **Dalla vista 3D**: tasto destro su un punto (o "Invia ▾" nel pannello del sample) apre il menu *Invia*. In alto c'è la sezione **Drum Rack** con **+ aggiungi** (sul pad selezionato, o sul primo libero del gruppo) e **+ aggiungi e apri ▦**, che passa anche alla scheda Drum Rack. Con *con i simili* il sample riempie l'intero gruppo insieme ai suoi simili.
- **Modalità**:
  - *Più simili*;
  - *Casuale*: pesca per somiglianza con uno slider di variazione; *Rigenera* rifà l'estrazione;
  - *Manuale*: spunti i simili da una lista ordinata per somiglianza;
  - *Percorso*: usa le tappe di "Trova simili" (anche dal pulsante ▦ Drum Rack nella barra dei simili) e, se sono poche, le completa con i simili dell'ultima tappa.
- **Filtri**: stessa classe del seed, famiglia del gruppo o tutta la libreria; solo one-shot; evita i sample già presenti nel kit.
- **Gruppi**: famiglia (usata da *Auto-riempi* e dal browser), choke group (attivo di default sugli hat) e **🔒 blocca gruppo**. Trascina i pad per scambiarli e un sample dal browser per metterlo su un pad; il tasto destro apre il menu del pad.
- **🎲 Casuale**: ogni gruppo non bloccato prende un gruppo di sample simili scelto a caso tra quelli della sua famiglia, con sample a caso da lì. Puoi applicarlo a tutti i gruppi o solo a quelli vuoti, limitarlo a una cartella o pack e tenere solo i one-shot.
- **→ Sequencer**: carica i sample nei bus del Sequencer secondo la loro classe, fino a 8 per bus. Un riquadro chiede:
  - quali bus caricare;
  - se *sovrascrivere* i bus scelti, *aggiungere* ai layer esistenti o *svuotare anche gli altri bus*;
  - per ogni bus, come alternare i sample. Il default è *casuale*, tranne per kick, FX e basso, dove suona solo il primo sample e gli altri entrano muti.
- **Esporta per Ableton**: una cartella con `Samples/<gruppo>/<nota> - <nome>.wav`, `… Drum Rack.adg` (un pad per tasto, con la nota del Launchpad e i choke group), i `.license.txt` dei sample online e `LEGGIMI.txt` con la mappa 8×8 dei pad.

### Kit per Roland SPD-SX

Il menu in alto a sinistra della barra sceglie lo strumento: **Controller 8×8 (Launchpad)** o **Roland SPD-SX**. Ogni strumento ha il suo kit, quindi passare dall'uno all'altro non tocca l'altro kit.

- **Pad**: sono disegnati come sullo strumento. In alto la riga stretta dei pad 1–3, sotto i pad 4–6 e 7–9. Più sotto ci sono gli ingressi **Pedale (Trig 1)** e **Trig 2**, che si attivano e disattivano con la loro spunta.
  - Il pedale prende un kick di default.
  - Senza pedale, il kick passa sul pad 8 (in basso al centro).
- **Note MIDI**: quelle di fabbrica della SPD-SX. Pad 1–9 = 60–68 (C3–G#3 in Live), Trig 1 = 69, Trig 2 = 70.
- **Configurazioni**: dicono quali pad formano un gruppo di sample simili e di che famiglia.
  - *Kit classico*: hat e piatti in alto, snare e clap al centro (snare sul pad 5), tom in basso;
  - *Righe*;
  - *Colonne*;
  - *Croce*: snare al centro, percussioni a croce, hat agli angoli;
  - *Percussioni*;
  - *Libero*.
- **Suonabilità**: al massimo 2 kick (pedale + 1 pad), 3 snare/clap e 5 tra hat e piatti.
  - Nel menu *Famiglia* le scelte che supererebbero questi limiti sono disattivate.
  - Se il kit li supera, per esempio in *Libero* o con sample trascinati, sotto i pad compare un avviso.
- **🎲 Genera kit**: sceglie una configurazione suonabile a caso, con varianti di famiglia dello stesso ruolo (snare / clap, hat / hat + piatti, perc / shaker / tom…).
  - Riempie ogni gruppo con sample simili tra loro, presi da un gruppo di suoni (classe + sotto-cluster) che nessun altro gruppo usa. Così il kick del pedale e un eventuale kick su un pad, o due righe di hat, suonano diversi.
  - Si può mantenere la configurazione attuale; resta invariata anche se un gruppo è bloccato (🔒).
  - Come per *🎲 Casuale*, si può limitare a una cartella o pack, tenere solo i one-shot e far combaciare le dinamiche.
  - *Auto-riempi*, *🎲 Casuale*, *→ Sequencer* e *Invia a Live* funzionano come per l'8×8.
- **Esporta (Live + SPD-SX)**: crea una cartella con:
  - `… SPD-SX Drum Rack.adg` sulle note della SPD-SX, per suonare Live con la SPD-SX via USB MIDI;
  - `SPD-SX/` con i WAV a 16 bit / 44,1 kHz, chiamati `P1 - …` … `P9 - …`, `T1 Pedale - …` e `T2 - …`, da importare con SPD-SX Wave Manager;
  - `LEGGIMI.txt` con la mappa dei pad e i passaggi per Live e per la SPD-SX.

## Scheda Compose: progressioni di accordi

La quinta scheda costruisce progressioni con le clip MIDI di un chord pack organizzato come l'**Unison MIDI
Chord Pack** (default `~/Documents/Unison MIDI Chord Pack`; *Cambia…* in alto a sinistra per un'altra cartella).
Il pack non viene mai modificato: i file vengono letti e indicizzati in memoria.

- **Browser**: gli accordi della tonalità scelta, raggruppati per grado (I, ii, bVII…) e colorati per funzione
  (verde tonica, blu sottodominante, arancio dominante, viola colore/prestito modale). Filtri per *Triadi*,
  *Estesi*, *Prestito & modali*, *Progressioni* e ricerca per nome o grado. Clic: ascolta; doppio clic, **+** o
  trascinamento sulla timeline: aggiunge. Le progressioni del pack entrano come un blocco per accordo. Le
  tonalità (o le categorie) che mancano nel pack vengono trasposte dalla tonalità più vicina.
- **Tonalità**: *🔒 bloccata* mostra solo gli accordi di quella tonalità e cambiarla traspone l'intera
  progressione; *Libera* permette di prendere accordi da qualsiasi tonalità e di trasporre ogni accordo
  (±12 semitoni). In entrambi i casi la tonalità in alto è il riferimento per gradi e suggerimenti.
- **Timeline**: lunghezza in battute e griglia (1 battuta … 1/16) a scelta. Trascina un blocco per spostarlo e
  il bordo destro per cambiarne la durata; gli accordi successivi scorrono in avanti invece di sovrapporsi.
  *⇔ Distribuisci* dà a tutti la stessa durata sull'intera lunghezza. Ogni blocco mostra le note che suonano
  davvero (dopo strum, arpeggi e ritmo).
- **Prossimo accordo**: suggerimenti per l'accordo selezionato (o l'ultimo), con punteggio e motivi: funzione
  armonica, cadenze (V → I, ii → V, d'inganno, plagale, bVI → bVII…), moto del basso, note comuni, voice
  leading e frequenza della mossa nelle progressioni del pack. Se dopo il blocco selezionato c'è già un
  accordo, conta anche quanto bene il suggerimento ci conduce. Sotto ogni proposta ci sono le varianti di
  colore dello stesso grado.
- **Esecuzione** (per accordo, o come default della sequenza): *Block*, *Strum* (↑, ↓ o alternato, 5–80 ms),
  *Arpeggio* (su, giù, su-giù, casuale; 1/4…1/16 e terzine; 1–2 ottave), *Ritmo* (semiminime, ottavi, offbeat,
  charleston, tresillo, sincopato house, minime, pulse 1/16) suonato a block o a strum, durata delle note,
  curva di dinamica, **humanize** (timing e velocity, 🎲 per rigenerarlo) e **Alterna** stili a ogni colpo o a
  ogni battuta. Anteprima ed export usano gli stessi eventi, calcolati in Python.
- **Variazioni di un accordo** (*✦ Varia…* o `V`): voicing (rivolti, drop-2, open/close, basso raddoppiato,
  voice leading minimo dal precedente), colore (stesso grado con estensioni diverse), sostituzioni scelte nel
  contesto e modi di esecuzione. ▶ ascolta la proposta dalla battuta prima.
- **Variazioni della progressione** (*✦ Genera variazioni…*): riarmonizzazione (primo e ultimo accordo restano),
  ritmo armonico (anticipi, lungo-corto, accordi divisi), voice leading, più ricca / più scarna, esecuzione e
  finale (IV → V, bVI → bVII, IV → iv, ii → V…), con uno slider *Quanto variare*. *Tieni* la salva come nuova
  **versione** (A, B, C… nelle schede sopra la timeline), *Accoda* la aggiunge in fondo (A A' …).
- **Esporta MIDI**: un `.mid` (tipo 0, 480 PPQ, con il tempo) per la versione corrente, oppure uno per versione
  in una cartella; *solo accordi* esporta i voicing a block senza stile. In Ableton basta trascinarlo su una
  traccia MIDI. *Salva* / *Apri…* tengono le progressioni con tutte le versioni; ⌘Z / ⇧⌘Z annullano e ripetono.

Scorciatoie: `Spazio` play/stop, `←` `→` accordo precedente/successivo, `Canc` elimina, `⌘D` duplica, `V` variazioni.

### Vista Melodia

In alto a sinistra **Armonia | Melodia** cambia vista. Ogni versione (A, B, C…) ha la sua melodia, che suona
insieme agli accordi in entrambe le viste (♫ nella barra la silenzia).

- **Layer**: la melodia è fatta di uno o più layer sovrapposti sugli stessi accordi — *Melodia*, *Basso*,
  *Arpeggio*, *Riff*, *Pad*, *Keys* — ognuno col suo suono e colore. *＋ Layer ▾* ne aggiunge uno vuoto; clic sul
  nome lo rende attivo (il piano roll modifica quello, gli altri si vedono in trasparenza), doppio clic lo
  rinomina, **M** lo silenzia, ✕ lo elimina. Due cursori: volume del layer attivo e di tutti i layer.

- **Piano roll** sotto la corsia degli accordi: le righe della scala sono più chiare e sotto ogni accordo sono
  evidenziate le sue note. Clic su uno spazio vuoto: nuova nota (trascina per allungarla); trascina una nota per
  spostarla, il bordo destro per allungarla, `Alt`+trascina per la velocity; doppio clic la elimina.
  `↑` `↓` traspongono (`⇧` di un'ottava), `←` `→` spostano, `⌘D` duplica, `⌘A` seleziona tutto.
- **Importa ▾** (nel layer attivo): da un *File MIDI* (la nota più alta di ogni accordo, quantizzata), da una *Clip di Ableton*
  (nel device premi *Clip → Melodia* con una clip MIDI selezionata) o dalla *Tastiera MIDI*: 4 click di attacco,
  poi suoni sopra la progressione. La registrazione richiede `pip install python-rtmidi` (la WebView di macOS
  non ha Web MIDI). Se la versione non ha accordi, la tonalità viene rilevata dalla melodia.
- **Genera dagli accordi**: *Tipo*, densità ed estensione (si imposta da sola sul registro del tipo).
  - *Melodia*: contorno (arco, sale, scende, onda); note dell'accordo sui tempi forti, della scala in mezzo,
    frasi di 2–4 battute con una risposta.
  - *Basso*: stile (fondamentali, ottave, quinte, passaggi); la fondamentale sul primo tempo di ogni accordo e
    una nota di avvicinamento a quello dopo.
  - *Arpeggio*: direzione (sale, scende, sale e scende, casuale) sulle note dell'accordo, a semiminime, crome o
    semicrome secondo la densità.
  - *Riff*: una cellula di una battuta che segue gli accordi, variata ogni 4 battute.
  - *Pad* / *Keys*: accordi con voicing legati, tenuti o ritmati.

  *Solo sugli accordi selezionati* rigenera solo quelle battute. ▶ ascolta insieme agli altri layer, *Usa*
  sostituisce il layer attivo (se è dello stesso tipo), *＋ Layer* aggiunge la linea come nuovo layer.
- **Accordi dalla melodia** (dal layer attivo): un accordo per battuta, due, o quanti ne servono alla melodia, scelto tra quelli
  del pack che contengono le sue note e concatenato con gli stessi criteri dei suggerimenti. La tonalità può
  essere quella della versione o rilevata dalla melodia. *Nuova versione* aggiunge una versione con accordi e
  melodia, *Sostituisci* cambia gli accordi della versione corrente.
- **Esporta MIDI**: con una melodia scegli *Accordi + melodia* (un `.mid` tipo 1 con una traccia per gli accordi
  e una per ogni layer non muto), *Solo accordi* o *Solo melodia*. *Invia a Live* crea anche una traccia per
  ogni layer accanto agli *Accordi* (il basso con un suono da basso, pad e keys da tastiera).

## Scheda Recorder: registrare l'uscita audio del Mac

Registra ciò che il Mac manda a una o più uscite audio, ognuna nel suo file, poi ritaglia i sample dalla
registrazione: finiscono nella libreria e vengono classificati come gli altri.

- **Uscite da registrare**: casse, cuffie, interfacce audio, AirPlay… più *Tutte le uscite (mix)*. Se ne
  selezioni più di una, partono insieme e ognuna ha il suo file, il suo meter e la sua dimensione.
  *aggiorna* rilegge i dispositivi collegati.
- **Formato**: WAV (16/24 bit, 32 float), AIFF, FLAC (16/24 bit), CAF, MP3 (128–320 kbps), OGG Vorbis,
  Opus (48 kHz) e M4A/AAC (128–256 kbps, convertito con `afconvert`). Frequenza del dispositivo oppure
  44,1/48/96 kHz; stereo, mono o tutti i canali (solo nei formati non compressi).
- **Cartella**: `~/Music/ClusterSound Recordings/<data ora> - <uscita>.<ext>`, con accanto un `.source.txt`
  di provenienza. La registrazione continua anche se cambi scheda (pallino rosso sulla tab).
- **Editor**: allo stop la registrazione si apre sotto. Trascina sulla forma d'onda per creare una regione, i
  bordi la ridimensionano, clic per ascoltarla. *Taglia sui transienti* crea una regione per colpo nella parte
  visibile. Rotella: zoom · Maiusc+rotella: scorri · la striscia sotto sposta la vista. `Spazio` play/stop,
  `↑↓` regione precedente/successiva, `Canc` elimina.
- **Sample estratti**: WAV 24 bit in `~/Music/ClusterSound Samples/`, con fade e normalizzazione opzionali,
  massimo 30 s ciascuno (impostazione `sampler_max_seconds`).
- **Al Drum Rack**: carica le regioni selezionate (o una sola, dall'icona sulla sua riga) sui pad liberi del Drum
  Rack, a partire dal pad selezionato e in ordine di nota (C1, C#1, D1…), e apre la scheda per suonarle. Le
  regioni vengono esportate come sopra; una regione già esportata e non modificata riusa il suo file.

**Come funziona.** Ogni uscita è letta da `cs-tap` (`clustersound/native/cs_tap.swift`), un piccolo helper
basato sui Core Audio process tap (macOS 14.2+): riceve lo stesso audio che il dispositivo riproduce. Lo
compila `tools/build_tap.sh` (lo lancia anche `build_app.sh`); da sorgente, con `swiftc` installato, si
compila da solo al primo uso. Al primo avvio macOS chiede il permesso *Registrazione audio di sistema*. Senza
helper resta solo *Tutte le uscite* tramite ScreenCaptureKit (extra `pip install -e ".[capture]"`).

**Nota legale.** Nulla viene decifrato o aggirato: le app che proteggono il flusso registrano silenzio. Le
registrazioni sono per uso personale (copia privata); per pubblicare un brano che contiene un sample servono i
diritti sull'originale, oppure un sample con licenza libera. Non esiste una soglia di secondi sotto la quale
un sample è libero.

## Max for Live: importare in Ableton Live

Il device **ClusterSound** (effetto MIDI, Live 10.1 Suite o successivo) importa direttamente nel set i pattern,
i drum rack e le progressioni di Compose, senza trascinare file. È fatto di tre pezzi:

- **l'app**, che all'avvio apre un piccolo server solo locale (`127.0.0.1:8770`, porta modificabile nelle
  Impostazioni) con il catalogo e i contenuti pronti per Live;
- **il device** `m4l/ClusterSound.maxpat` + `ClusterSound.js`, che crea tracce MIDI e clip con le note via
  Live API;
- **la Remote Script** `remote_script/ClusterSoundBridge` (Python 2.7 in Live 10), che carica i preset `.adg`
  dei rack e gli strumenti della libreria di Live: la Live API di Max non può farlo.

I rack per Live vengono scritti in `User Library/ClusterSound`, che il browser di Live indicizza sempre: non
serve aggiungere cartelle ai Places. Se la User Library è altrove, impostala nelle Impostazioni dell'app
(`live_library`). Senza User Library l'app usa `~/Music/ClusterSound Patterns/Live Import`, da aggiungere ai
Places.

Installazione (una volta):

1. `tools/install_live.sh`: costruisce `ClusterSound.amxd` e lo copia con la Remote Script nella User Library
   (`~/Music/Ableton/User Library`, oppure passa il percorso come argomento).
2. Riavvia Live. In *Preferenze → Link/MIDI* scegli **ClusterSoundBridge** come Control Surface, con Input e
   Output su *Nessuno*.
3. Trascina il device *ClusterSound* (in *Max MIDI Effect*) su una traccia MIDI qualsiasi. Per avere un unico
   file autonomo, aprilo in Max e usa *Freeze Device*, poi salva.

Uso, con l'app ClusterSound aperta:

- **Dal device**: scegli il tipo (pattern salvati, sequenze, drum rack, progressioni) e l'elemento, poi
  *Importa*. *Aggiorna* rilegge il catalogo.
  - Un pattern crea le tracce *Drums* e *Bass*, ognuna con il proprio rack e la clip.
  - Una sequenza fa lo stesso, con una clip lunga quanto tutta la sequenza.
  - Un drum rack crea una traccia con il rack.
  - Una progressione crea una traccia *Accordi* con una clip per versione, suonate con la Modalità attiva, e
    una traccia *Melodia* se c'è una melodia.
- **Clip → Melodia**: manda all'app le note della clip MIDI selezionata in Live; in Compose → Melodia →
  *Importa ▾ → Clip da Ableton* diventa la melodia della versione corrente.
- **Dall'app**: *Invia a Live* nel Sequencer, nella barra della sequenza (*Live*), nel Drum Rack e nel menu
  *Esporta* di Compose. Con *Ricevi* attivo, il device importa subito quello che arriva, anche se non è salvato.
- *Nuove tracce* (attivo di default) crea le tracce dopo quella selezionata; se lo spegni, la prima traccia
  importata va su quella selezionata. *Tempo* imposta il BPM del set.
- Le clip partono dalla scena selezionata e vanno sempre in uno slot vuoto: non sovrascrivono mai le clip
  esistenti.
- Senza la Remote Script le clip vengono create comunque, e il device indica il rack da trascinare dal browser.

**Strumenti di Live da provare** (colonna destra del device):

- **Traccia**: le tracce dell'ultimo import. Per la traccia *Drums* di un pattern o di una sequenza c'è anche
  una voce per ogni bus che suona (*Drums › Kick*, *› Snare*…), e quello che scegli va solo sul pad di quel bus.
- **Tipo**: tutte le categorie di Sounds della libreria di Live, compresi i preset dei pack installati (Bass,
  Brass, Guitar & Plucked, Mallets, Pad, Piano & Keys, Strings, Synth Keys, Synth Lead, Voices, Winds…). Poi i
  *Kit di batteria*, i *Preset di* ogni strumento (Operator, Wavetable, Analog, Sampler…) e, per i bus, i *Colpi*
  di quel bus.
- **Strumento**: tutti i preset del tipo, in ordine alfabetico, 60 alla volta (*… altri N* carica i
  successivi).
- Scegliere uno strumento, o passare al precedente o al successivo con **◀ ▶**, lo carica sulla traccia e fa
  partire la clip importata in loop. **Prova ▶** ricarica quello selezionato, **Stop** ferma la traccia.
- **★ Sample ClusterSound** (o *Kit ClusterSound* per i bus) rimette i sample dell'app.
- Le tracce che arrivano senza strumento ricevono subito il primo preset del loro tipo: *Piano & Keys* per gli
  accordi, *Bass* per il basso, un kit per la batteria. Così ogni import suona già.

Se un rack o uno strumento non si carica, il motivo è nello stato del device e in `Log.txt` di Live
(`~/Library/Preferences/Ableton/Live 10.x/Log.txt`, righe `ClusterSoundBridge`), dove la Remote Script registra
ogni comando.

Quando salvi una sequenza, con lei si salva anche il kit aperto nel Sequencer (sample, layer e mix), e il device
la importa con quello. Le sequenze salvate prima di questa versione non hanno il kit. Il device usa allora il
pattern utente da cui viene il primo blocco. Se il blocco viene da un preset di genere, importa solo il MIDI e
lo segnala con *(solo MIDI)*: per avere anche il kit, apri la sequenza e salvala di nuovo.

In mancanza di questi, il device usa il kit aperto ora nel Sequencer e lo segnala con *(kit attuale)*.

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
tools/build_app.sh   # -> dist/ClusterSound.app (compila anche l'helper cs-tap del Recorder)
```

Apri e copia solo `ClusterSound.app`: la cartella `dist/ClusterSound/` contiene un eseguibile nudo che
il Finder lancia dentro il Terminale (lo script la elimina dopo la build).

## Strumenti di sviluppo

- `tools/build_yamnet_npz.py` — converte i pesi Keras di YAMNet nel modello numpy.
- `tools/train_base_head.py` — riaddestra la head base su una o più librerie.
- `tools/extract_adg_template.py` — rigenera i template (solo struttura) dei rack Live 10 dai preset installati con Live.
- `tools/evaluate.py` — accuratezza a nomi nascosti (`--oneshots`, `--all-hidden`, `--no-base`).
- `tools/devserver.py` — UI in un browser normale con l'API Python via HTTP.
- `pytest` — test su segnali sintetici e pipeline end-to-end; per le fonti online usa risposte registrate
  in `tests/fixtures/online` (`CLUSTERSOUND_NETWORK_TESTS=1 pytest` interroga anche i servizi reali).
