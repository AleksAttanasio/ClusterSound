# Armonia e accordi

Codice: `chords/library.py`, `theory.py`, `harmony.py`, `variations.py`, `perform.py`. Gli accordi non vengono
generati da regole astratte: sono le **clip MIDI del chord pack**, indicizzate e poi ordinate, trasposte e variate.
Così ogni accordo ha un voicing suonato da un musicista.

## Indicizzazione del pack

- **Tonalità** dalle cartelle `NN - X Major - Y Minor`; il modo dalla presenza di "minor" nelle sottocartelle; la
  **categoria** (triadi, estesi, prestiti, progressioni…) da parole chiave delle cartelle.
- **Segmentazione**: note con attacchi entro 1/32 formano un accordo (ricampionato a 480 PPQ); ogni accordo dura fino
  al successivo e la fine del file è arrotondata alla battuta. Un file con più segmenti è una **progressione**; i
  gradi tra parentesi nel nome (`(I-V-vi-IV)`) sono letti se tutti validi.
- **Radice**: dal nome dell'accordo, altrimenti dal grado, altrimenti stimata (sotto).
- **Tonalità mancanti**: servite dalla tonalità del pack più vicina con la stessa categoria, trasponendo di −6…+5
  semitoni (a parità, verso il basso). I risultati sono marcati *trasposti*.
- **Statistiche**: per ogni progressione si contano i **bigrammi** di gradi (coppie consecutive, ripetizioni escluse;
  il ritorno ultimo → primo conta 0,5 perché le progressioni girano in loop).

## Teoria (`theory.py`)

**Qualità** dagli intervalli sopra la radice: con la terza maggiore → aumentato (5ª aumentata senza giusta), dominante
(7ª minore senza maggiore) o maggiore; con la terza minore → diminuito (5ª diminuita senza giusta) o minore;
altrimenti sus.

**Radice stimata**: per ogni classe di altezza *r*

\[
\text{score}(r) = 2[\text{3ª}] + 1{,}5[\text{5ª}] + 1[\text{5ª dim. con 3ª min.}] + 0{,}5[\text{7ª}] + 0{,}75[r = \text{basso}]
\]

**Funzione armonica**: un accordo è *diatonico* se la radice e il nucleo di triade (radice, 3ª, 5ª) stanno nella scala
(in minore è ammessa anche la sensibile). Gli accordi diatonici hanno funzione di **T**onica, **S**ottodominante o
**D**ominante secondo il grado; tutti gli altri sono **C** (colore / prestito modale). Sono i quattro colori del
browser.

## Prossimo accordo

Per ogni candidato *b* dopo l'accordo *a*, `transition(a, b)` somma:

| Termine | Valore |
|---|---|
| **Flusso di funzione** | tabella T/S/D/C: es. T→S 1,0 · S→D 1,0 · D→T 1,0 · T→D 0,75 · D→S 0,3 |
| **Cadenza** (la prima che corrisponde) | V→I +0,6 · ii→V +0,45 · plagale +0,35 · d'inganno +0,35 · bVI→bVII +0,35 · mixolidia bVII→I +0,35 · napoletana +0,3 · sensibile→tonica +0,3 … |
| **Moto del basso** | quarta su (quinta giù) +0,35 · quinta su +0,15 · per grado +0,15 · tritono −0,3 · stessa radice −0,3 (colore diverso) o −0,7 |
| **Note comuni** | +0,08 per nota, fino a 3 |
| **Voice leading** | \(\max(0,\;0{,}3 - 0{,}03\,d)\), con *d* = distanza media in semitoni |
| **Frequenza nel pack** | \(+0{,}6 \cdot \text{bigramma}(a,b) / \max\) |

La **distanza di voice leading** tra due voicing è la media di due medie: ogni nota di *b* verso la nota più vicina di
*a*, e viceversa.

Poi `suggest`:

- penalità −0,8 per lo stesso accordo della libreria e −0,15 per un ping-pong A-B-A;
- se dopo c'è già un accordo *n*, si aggiunge \(0{,}6 \cdot \text{transition}(b, n)\): il suggerimento deve anche
  *condurre* bene;
- senza accordo precedente, punteggio di partenza: T 1,0 (+0,4 se è il I) · S 0,55 · D 0,35 · C 0,2;
- i candidati sono raggruppati per (radice, minore, diminuito): vince il voicing migliore, gli altri diventano le
  **varianti di colore** sotto la proposta;
- i punteggi sono riscalati tra 0,35 e 1 per la barra; i **motivi** mostrati sono le etichette dei termini scattati.

In tonalità libera i candidati includono le tonalità vicine: dominante, sottodominante, relativa e parallela.

## Variazioni

Tutte deterministiche dato il seed (`random.Random(seed)`).

**Adattare un voicing** (`_fit`): prova rivolti −2…+2 × ottave −1…+1 (note tra 24 e 100) e sceglie quello che
minimizza \(d(\text{precedente}) + 0{,}15\,|\text{centro} - \text{centro di riferimento}|/3\).

**Di un accordo**:

- *voicing*: 1° e 2° rivolto, rivolto in basso, drop-2, open (2ª voce un'ottava su), close, basso raddoppiato; in
  testa quello a voice leading minimo dal precedente;
- *colore*: stessa radice e stesso modo dal pack, preferendo un numero di note diverso;
- *sostituzione*: i primi 2 di `suggest` nel contesto (accordo prima e dopo) più 2 a caso tra gli altri.

**Della progressione** (`vary_progression`), con *Quanto variare* \(a \in [0{,}05, 1]\):

| Tipo | Strategia |
|---|---|
| *riarmonizzazione* | sostituisce \(\operatorname{round}(a \cdot \text{interni})\) accordi (primo e ultimo restano); ogni scelta prende il rango \(\lfloor u^2 \cdot 5\rfloor\) tra i 5 migliori suggerimenti, con *u* uniforme: favorisce i migliori senza essere sempre la stessa |
| *ritmo armonico* | anticipo di un ottavo, lungo-corto (1,5 + 0,5), divisione di un accordo ≥ 1 battuta con il miglior suggerimento nella seconda metà |
| *voice leading* | catena di `_fit` per il moto minimo |
| *più ricca / più scarna* | stessa radice con più o meno note (scarna preferisce le triadi) |
| *finale* | cadenza tipica del modo sugli ultimi 2 accordi (IV→V, bVI→bVII, IV→iv, ii→V…) |

Le proposte sono deduplicate per firma; se ne generano fino a 4× il numero richiesto.

## Esecuzione (`perform.py`)

Dagli accordi alle note, a 480 PPQ; **la stessa funzione** produce anteprima, MIDI e clip per Live.

- **Colpi**: la griglia ritmica si ripete sulla timeline assoluta; una durata 0 significa "fino al prossimo colpo".
  Un accordo che inizia fuori tempo riceve un colpo al suo inizio.
- **Swing**: semicrome dispari ritardate di \((\text{swing}/50 - 1)\cdot 120\) tick.
- **Strum**: direzione *chitarra* (giù sui tempi, su in mezzo), alternata, sempre su/giù; spread totale limitato a metà
  della durata; curve lineare, accelerando \(1-(1-x)^2\), rallentando \(x^2\); inclinazione della velocity e upstroke
  più morbidi; upstroke limitabile alle note alte.
- **Arpeggio**: su, giù, su-giù, casuale su 1–3 ottave; le note in levare a 0,86 di velocity.
- **Dinamica**: crescendo \(0{,}72 + 0{,}42f\), diminuendo \(1{,}14 - 0{,}42f\), accento sul basso ×1,12; accenti
  sui battere.
- **Humanize** deterministico (seed dell'humanize XOR CRC32 dell'accordo): il timing sposta un intero colpo insieme,
  con una *deriva* che mescola rumore bianco e rumore "value" interpolato a coseno (periodo 2 tempi); in più spread
  per nota, durata ±% e velocity ±. Infine si accorciano le sovrapposizioni sulla stessa nota e si scartano le note
  sotto 12 tick.
