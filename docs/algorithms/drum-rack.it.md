# Scelta dei sample nei Drum Rack

Il Drum Rack deve riempire gruppi di pad con sample **simili tra loro ma non identici**, rispettando famiglia,
filtri e, per la SPD-SX, la suonabilità del kit. Codice: `racks/select.py`, `racks/dynamics_match.py`,
`racks/spdsx.py`, maschere e auto-riempimento in `api.py`.

## Spazio e candidati

- **Somiglianza**: coseno tra embedding YAMNet normalizzati.
- **Maschera dei candidati** (`_rack_mask`): stessa classe del seed (default), le classi della famiglia del gruppo, o
  tutta la libreria; *solo one-shot* (default sì); *evita sample già nel kit*; per i kit casuali anche il filtro
  cartella/pack (sottostringa del percorso).
- **Pool**: si considerano i **400** candidati più simili al seed.
- **Doppioni**: un candidato è scartato se il suo coseno con uno già scelto (seed compreso) è ≥ **0,995** — copie e
  file rinominati non occupano due pad.

## Modalità di riempimento

**Più simili** (`neighbours`): scorre la classifica e prende i primi *k* non doppioni.

**Casuale** (`pick`, modalità `random`): costruisce un pool dei
\(\text{count} + \operatorname{round}(v \cdot 5 \cdot \text{count})\) più simili, dove \(v \in [0,1]\) è lo slider
*variazione* (a \(v = 1\) il pool è 6 volte il numero di pad). Poi estrae senza reinserimento con pesi

\[
w_i = \exp\!\Big(\frac{s_i - s_{\max}}{T}\Big), \qquad T = 0{,}05
\]

La temperatura bassa favorisce nettamente i più simili ma lascia spazio agli altri; lo slider allarga il pool. Il
risultato è riordinato per somiglianza e riproducibile dal seed casuale (*Rigenera* lo cambia).

**Manuale**: i 60 vicini più simili in una lista da spuntare.

**Percorso** (`trail`): le tappe di *Trova simili* scelte a mano, nell'ordine e senza ripetizioni, tagliate alla
dimensione del gruppo; se sono poche, si completano con i vicini dell'ultima tappa (i filtri valgono solo per il
completamento).

## Gruppo casuale e kit casuale

`random_group` è il mattone di *🎲 Casuale*, del kit casuale del Sequencer e di *Genera kit*:

1. tra i candidati ammessi si elencano i **gruppi** `classe:sottocluster`;
2. se ne sceglie uno **uniformemente** (non in proporzione alla dimensione: anche i gruppi piccoli escono);
3. un seed a caso dentro il gruppo;
4. gli altri `count − 1` con `pick` casuale attorno al seed.

`rack_randomize` lo applica a ogni gruppo non bloccato (o solo ai vuoti):

- i sample già usati sono esclusi;
- con **gruppi distinti** (sempre per la SPD-SX) si escludono prima i sottocluster già usati da altri gruppi, così
  due righe di hat o il kick del pedale e quello di un pad suonano diversi; se così restano troppo pochi candidati,
  si rinuncia al vincolo;
- con **dinamiche simili** il riferimento è l'insieme dei sample già messi nel kit (vedi sotto).

**Auto-riempi** (`rack_autofill`) è la versione deterministica: per ogni gruppo vuoto sceglie come seed il miglior
one-shot non usato della famiglia — ordinando per classe della famiglia, one-shot prima, nomi non da loop prima,
confidenza decrescente — preferendo tra i primi 300 un sottocluster non ancora usato nella stessa famiglia; poi
completa con `pick` casuale a variazione 0,3.

## Dinamiche simili (`dynamics_match.py`)

Un kit suona coeso se i suoi colpi hanno inviluppi compatibili. Ogni sample ha un vettore d'inviluppo di 5 valori:

| Feature | Scala | Peso |
|---|---|---|
| attacco | log₁₀ | 0,7 |
| decay a −20 dB | log₁₀ | 1,2 |
| T60 | log₁₀ | 1,2 |
| quota di coda | lineare | 1,0 |
| pendenza dell'inviluppo (dB/s, clip [−200, 50]) | lineare | 0,6 |

I valori sono **standardizzati dentro ogni classe** (con statistiche dell'intera libreria per le classi con meno di
5 sample): così un kick *corto per essere un kick* risulta vicino a un hat *corto per essere un hat*. Il riferimento è
la media dei sample già scelti; la distanza è l'RMS sulle 5 dimensioni e il punteggio \(\exp(-d^2/2)\). Il margine
tiene la frazione più vicina dei candidati (almeno 8), che poi passa alla scelta casuale.

## Layout 8×8

- Pad numerati `riga·8 + colonna`, riga 0 in basso.
- Note *Launchpad*: \(b_{Q[q]} + 4\,(r \bmod 4) + (c \bmod 4)\), con quadrante \(q = 2[r \ge 4] + [c \ge 4]\) e
  \(Q\) la disposizione dei blocchi del kit, C = 36, D = 52, A = 68, B = 84 (default `DBCA`: in alto a sinistra
  36–51, in alto a destra 68–83, in basso a sinistra 52–67, in basso a destra 84–99, come li suona il
  Launchpad). Note *righe*: \(36 + p\).
- Geometrie: 8 colonne da 8, 16 blocchi 2×2, 4 quadranti 4×4, 16 colonne da 4 (una famiglia per quadrante),
  libero; ogni geometria ha famiglie di default (18 famiglie in tutto). Il choke è attivo di default per le famiglie
  di hat.

## Roland SPD-SX

**Pad e trigger**: 9 pad (note 60–68) più Trig 1 (pedale, 69) e Trig 2 (70). Senza pedale il pad 8 diventa un gruppo
a sé con il kick; ogni trigger collegato è un gruppo (T1 kick, T2 piatto).

**Limiti di suonabilità**: al massimo **2 kick**, **3 snare/clap**, **5 hat/piatti**. Il ruolo di un gruppo viene
dalla sua famiglia; per le famiglie generiche ("qualsiasi", "fx") si conta la classe del sample su ogni pad. Una
famiglia è proposta per un gruppo solo se, cambiandola, nessun ruolo supera \(\max(\text{limite}, \text{conteggio
attuale})\).

**Genera kit** (`random_config` + `rack_randomize`):

1. fino a 50 tentativi: una configurazione a caso (escluso *Libero*), in cui ogni gruppo cambia famiglia con una
   variante dello **stesso ruolo** (snare ↔ clap, hat ↔ hat + piatti, perc ↔ shaker ↔ tom…); T1 resta kick;
2. si accetta la prima che rispetta tutti i limiti;
3. si riempie con gruppi distinti (sopra). Se un gruppo è bloccato, o è chiesto di mantenere la configurazione,
   cambia solo il riempimento.

## Export

- `.adg`: XML gzip da template neutri di Live 10; un `DrumBranch` per pad con nota (`ReceivingNote = 128 − nota`),
  choke group e un Simpler in modalità one-shot con percorso **relativo** al preset.
- SPD-SX: anche WAV 16 bit / 44,1 kHz (ricampionati con soxr) per Wave Manager, nominati `P1`…`P9`, `T1 Pedale`,
  `T2`, più `LEGGIMI.txt` con la mappa dei pad.
