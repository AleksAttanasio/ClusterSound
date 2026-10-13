# Sequencer e groove

Codice: `patterns/model.py` (formato e tempo), `patterns/genres.py` (generi), `patterns/render.py` (audio),
`patterns/midi.py`, `patterns/arrange.py`, `patterns/ableton.py`; in JS `ui/pattern.js` e `ui/sequencer.js`.

## Il modello di un pattern

- **Griglia**: 16 step per battuta, 96 PPQ, quindi **24 tick per step** (una semicroma).
- **Bus**: 10 bus di batteria con una nota GM ciascuno, più il bus Bass.
- **Notazione compatta** nei generi: `X` = 127 (accento), `x` = 100, `o` = 55 (ghost), `2`/`3`/`4` = roll a
  velocity 100, `.` = pausa; una stringa più corta del pattern viene ripetuta. Il basso usa token
  `step:durata:semitoni` con `g` = glide e `!` = accento (velocity 120).

### Swing

Swing in stile MPC sulle semicrome dispari:

\[
\text{tick}(s) = 24\,s + \big[s \text{ dispari}\big]\cdot\operatorname{round}\!\Big(\frac{\text{swing}}{100}\cdot 48 - 24\Big)
\]

A 50% nessuno spostamento, a 75% le semicrome in levare arrivano 12 tick dopo (shuffle pieno). Le sequenze
conservano lo swing di ogni battuta (`swing_bars`).

### Roll

Un roll ×*r* divide lo step in *r* colpi equidistanti; il *k*-esimo ha velocity \(v\,(1 - 0{,}12k)\), così suona
come un rullo e non come una mitragliatrice.

### Alternanza dei layer

Con 2+ layer che condividono gli step del bus, un solo layer suona a ogni colpo:

| Modo | Layer del colpo *h* sullo step *s* |
|---|---|
| *a giro* | \(h \bmod n\) |
| *casuale* | \(\text{hash}(seed, s) \bmod n\) — stessa scelta a ogni giro |
| *casuale ogni giro* | \(\text{hash}(seed, s + \text{loop}\cdot N) \bmod n\) — nuova scelta a ogni ripetizione |

`hash` è un hash intero a 32 bit (moltiplicazione per 2654435761, xor-shift, moltiplicazione per `0x45D9F3B`)
**identico bit per bit** in Python (`alt_hash`) e in JS (`altHash`): l'anteprima Web Audio, il WAV e il MIDI
esportati suonano gli stessi layer. ⚄ cambia il seed. I layer con step propri suonano sempre.

## Generi

Ogni genere (`G`) ha BPM tipico e intervallo, swing, tonalità, ottava del basso, eventuale *half-time* e varianti
scritte a mano (`V`: step dei bus, linea di basso, battute). Due varianti si **derivano automaticamente** dalla
prima:

- **Fill**: le ultime 4 semicrome dello snare (o del clap) diventano `xx33` (`3x33` nei generi half-time): un
  rullo sull'ultimo tempo; un giro di tom `..xx` sull'ultimo tempo; un crash sul battere se il pattern non ha piatti.
- **Breakdown**: via kick, snare, tom e basso; se non resta nulla, un hat in levare; un colpo di FX sul battere.

### Varia

*Varia* (in `pattern.js`) applica piccole mutazioni idiomatiche:

1. sposta di ±1 semicroma un colpo di cassa fuori dai tempi (se lo step di arrivo è libero), oppure ne aggiunge uno a
   6 step dalla fine;
2. aggiunge fino a 2 ghost di snare (velocity 55) in levare liberi;
3. dà a un colpo di hat chiuso un roll ×2 o ×3;
4. con probabilità 50%, se c'è un open hat, ne accende o spegne uno su un "e" (step 2 + 4k).

### Kit casuale

Per ogni bus che suona e non è bloccato chiede `random_refs(classi del bus, n)` — lo stesso
[gruppo casuale](drum-rack.md#gruppo-casuale-e-kit-casuale) del Drum Rack — con *n* = 1, 2 o 4 (il basso sempre 1),
escludendo i sample già scelti. Con *dinamiche simili* il riferimento sono i layer udibili dei bus non rigenerati più
quelli scelti man mano. I bus con più layer passano ad alternanza *casuale*, tranne kick, FX e basso.

## Rendering (`render.py`)

Il WAV del loop è mixato in numpy, con la stessa logica dello scheduler Web Audio:

- **Guadagno** di velocity \((v/127)^{1{,}5}\), pan a potenza costante, volume e pan per bus e layer.
- **Sample** caricati fino a 30 s, stereo, 44,1 kHz; il **pitch** è un ricampionamento (come un sampler: cambia
  anche la durata); l'offset in ms sposta il layer.
- **Loop senza giunte**: le code che superano la fine del loop rientrano dall'inizio.
- **Choke**: ogni open hat viene chiuso (fade di 10 ms) al successivo closed hat, anche a cavallo del loop.
- **Filtri** passa-alto/passa-basso per bus: risposta in modulo di un Butterworth del 2° ordine applicata nel
  dominio FFT (fase zero).
- **Limitazione**: se il mix supera 0,98 viene scalato.

### Intonazione del basso

Un sample di basso suona intonato perché ne viene stimata la **nota radice**: 3 s, trim, autocorrelazione dei
100 ms più forti (dopo il transiente), ricerca della fondamentale 40–1000 Hz; se l'armonicità supera 0,4 (0,5 per i
sample della libreria) \(\text{root} = \operatorname{round}\big(69 + 12\log_2(f_0/440)\big)\). Ogni nota del basso è
poi trasposta di

\[
12(\text{ottava}+1) + \text{tonalità} + \text{semitoni} - \text{root} + \text{pitch del layer}.
\]

## MIDI ed export

- **Writer SMF** senza dipendenze: tipo 0 o 1, note-off prima dei note-on allo stesso tick.
- **Mappatura Drum Rack**: note consecutive da 36 per i bus usati; un bus in alternanza riceve un pad per layer e
  ogni colpo va al pad del layer che lo suona. **GM**: una nota per bus. Note di batteria lunghe 1/32.
- **Glide**: una nota con glide si sovrappone alla successiva di 1/64 (legato), così il Simpler in modalità mono
  scivola.
- **Ableton**: Drum Rack con un pad per bus (Instrument Rack annidato per i layer, choke sugli hat), basso in un
  Simpler classico mono con `RootKey` = radice stimata, release 60 ms e glide 60 ms se serve.
- **Sequenze** (`arrange.flatten`): i blocchi × ripetizioni sono concatenati in un unico pattern (massimo 256
  battute), con swing per battuta e confini delle sezioni; i layer con step propri sono ripetuti su tutta la
  lunghezza.
