# Max for Live

Il device **ClusterSound** (effetto MIDI, Live 10.1 Suite o successivo) importa nel set pattern, sequenze, drum
rack e progressioni, senza trascinare file. Installazione: [Guida › Ableton Live](../guida/ableton-live.md).

## Importare

Con l'app aperta:

- **Dal device**: scegli il tipo (pattern salvati, sequenze, drum rack, progressioni) e l'elemento, poi
  *Importa*. *Aggiorna* rilegge il catalogo.
    - un pattern crea le tracce *Drums* e *Bass*, ognuna con il proprio rack e la clip;
    - una sequenza fa lo stesso con una clip lunga quanto la sequenza;
    - un drum rack crea una traccia con il rack;
    - una progressione crea una traccia *Accordi* (una clip per versione) e una *Melodia* se c'è.
- **Dall'app**: *Invia a Live* nel Sequencer, nella barra della sequenza, nel Drum Rack, nel Recorder e nel menu
  *Esporta* di Compose. Con **Ricevi** attivo il device importa subito, anche ciò che non è salvato.
- **Clip → Melodia**: manda all'app le note della clip MIDI selezionata (Compose → Melodia → *Importa ▾ → Clip da
  Ableton*).

Regole: *Nuove tracce* (default) le crea dopo quella selezionata; *Tempo* imposta il BPM del set; le clip partono
dalla scena selezionata e vanno sempre in uno slot vuoto, senza sovrascrivere nulla. Senza Remote Script le clip
vengono create comunque e il device indica il rack da trascinare dal browser.

## Provare strumenti di Live

Nella colonna destra del device:

- **Traccia**: le tracce dell'ultimo import; per *Drums* anche una voce per ogni bus (*Drums › Kick*…).
- **Tipo**: le categorie dei Sounds di Live (Bass, Pad, Piano & Keys, Synth Lead…), i kit di batteria, i preset di
  ogni strumento (Operator, Wavetable, Analog…) e, per i bus, i colpi di quel bus.
- **Strumento**: i preset del tipo, 60 alla volta. Sceglierne uno, o scorrere con **◀ ▶**, lo carica e fa partire
  la clip in loop; **Prova ▶** lo ricarica, **Stop** ferma.
- **★ Sample ClusterSound** (o *Kit ClusterSound*) rimette i sample dell'app.

Le tracce che arrivano senza strumento ricevono il primo preset del loro tipo (*Piano & Keys* per gli accordi,
*Bass* per il basso, un kit per la batteria), così ogni import suona subito.

## Sequenze e kit

Salvando una sequenza si salva anche il kit del Sequencer, e il device la importa con quello. Per le sequenze più
vecchie usa il pattern utente del primo blocco, oppure solo il MIDI (*(solo MIDI)*) se il blocco viene da un
preset di genere; in mancanza usa il kit aperto ora (*(kit attuale)*).

Se qualcosa non si carica, il motivo è nello stato del device e nel `Log.txt` di Live (righe
`ClusterSoundBridge`). Protocollo e architettura: [Tecnica › Integrazione con Live](../tecnica/integrazione-live.md).
