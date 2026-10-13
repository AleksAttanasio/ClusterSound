# Melodia

Codice: `chords/melody.py`. Tutti i generatori ricevono la **mappa degli accordi** (quale accordo suona su ogni
semicroma) e la tonalità, sono deterministici dato il seed e producono più proposte (fino a 3× quelle richieste,
deduplicate).

## Melodia (lead)

La strategia unisce un **contorno globale** con una **scelta locale nota per nota**, organizzate in **frasi**.

**Frasi e ritmo.**

- Frasi di 2 battute (densità alta), 4 (bassa) o a caso. Il ritmo di ogni battuta è scelto da un repertorio per
  densità.
- Le frasi dispari sono **risposte**: con probabilità 0,75 riprendono il ritmo della domanda, battuta per battuta;
  l'ultima battuta della risposta è mutata (un attacco aggiunto o tolto).
- **Respiro**: l'ultima battuta di una frase tiene solo gli attacchi fino al terzo tempo, così la frase finisce su
  una nota lunga, e quella nota è la **radice dell'accordo**.

**Altezze candidate.** Sui tempi forti le note dell'accordo; sui deboli la scala più le note dell'accordo.

**Contorno.** Il centro di attrazione nella frase (posizione \(x \in [0,1]\)) è

\[
\text{target}(x) = \text{centro} + 0{,}7\cdot\text{semi-estensione}\cdot f(x)
\]

con *arco* \(f = 1{,}2\sin(\pi x) - 0{,}4\), *sale* \(f = -0{,}6 + 1{,}2x\), *scende* \(f = 0{,}6 - 1{,}2x\), *onda*
\(f = 0{,}6\sin\big(\pi(2x + \varphi)\big)\).

**Scelta della nota** (`_pick`): tra i candidati vince il punteggio massimo di

| Termine | Valore |
|---|---|
| distanza dal contorno | \(-0{,}25\,|p - \text{target}|\) |
| intervallo dalla nota precedente (*a* semitoni) | \(-0{,}35\,a\) fino a 4; oltre \(-1{,}4 - 0{,}6\,(a-4)\); oltre la quinta altri −3 |
| nota ripetuta | −0,9 sui tempi forti, −1,6 sui deboli |
| salto non recuperato | −1,5 se dopo un salto > 4 semitoni non si torna per grado in direzione opposta |
| varietà | \(+0{,}9\,u\), *u* uniforme |

Sono le regole classiche del contrappunto (moto per grado, salti recuperati, poche ripetizioni) in forma di
punteggio. **Velocity**: 104 sul battere, 92 sui tempi, 80 altrove, ±6.

## Basso

- La fondamentale di ogni accordo, nell'ottava più vicina alla precedente e attratta verso il basso dell'estensione.
- **Stili**: *fondamentali*, *ottave*, *quinte*, *passaggi* (note della scala verso la prossima fondamentale).
- **Avvicinamento**: con probabilità 0,7 l'ultima nota prima di un cambio d'accordo è a ±1/±2 semitoni dalla
  fondamentale successiva.

## Arpeggio

Le note dell'accordo in una finestra di 7 note attorno alla precedente, a passi di 4 / 2 / 1 semicrome secondo la
densità, nelle direzioni sale, scende, sale e scende, casuale.

## Riff

Una **cellula di una battuta** di intervalli costruita con `_pick` sul contorno a onda; a ogni accordo viene trasposta
sulla sua fondamentale e "agganciata" alle note dell'accordo sui tempi (scala + accordo altrove). Ogni quarta
battuta il ritmo viene mutato, perché il riff non sia meccanico.

## Pad e Keys

Voicing stretti fino a 4 note (si toglie prima la quinta) scelti per la minima distanza dal precedente. *Pad*: tenuti
(densità bassa), uno per battuta o uno per mezza battuta. *Keys*: accompagnamento ritmato da un repertorio di ritmi.

## Accordi dalla melodia

Il problema inverso: data una melodia, trovare una progressione del pack che la armonizzi.

1. **Candidati**: gli accordi del pack distinti per (radice, insieme di note), eventualmente anche dalle tonalità
   vicine.
2. **Segmenti**: un accordo per battuta, due, o *automatico*: una battuta viene divisa se il miglior accordo intero
   si adatta meno di 0,7 e le due metà insieme valgono più di \(2\cdot\text{intero} + 0{,}3\).
3. **Peso delle note**: durata × 1,5 se la nota cade su un tempo × 2 se apre il segmento.
4. **Adattamento** di un accordo a un segmento (normalizzato sul peso totale):

    | Nota della melodia | Contributo |
    |---|---|
    | nota dell'accordo | \(+w\) |
    | della scala, fuori accordo | \(-0{,}15\,w\) |
    | fuori scala | \(-0{,}6\,w\) |
    | a un semitono da una nota dell'accordo | altri \(-0{,}25\,w\) |
    | nota sul battere = radice | \(+0{,}15\) del totale |

    meno \(0{,}03\) per ogni nota dell'accordo oltre la terza (preferisce accordi semplici).

5. **Viterbi** sulla sequenza dei segmenti, per scegliere la catena migliore e non solo il miglior accordo per
   segmento:

    \[
    \text{emissione} = 2{,}2\cdot\text{fit},\quad
    \text{inizio} = 0{,}5\cdot\text{start},\quad
    \text{transizione} = 0{,}6\cdot\text{transition}(a,b) - 0{,}5\,[a = b]
    \]

    con lo stesso `transition` dei [suggerimenti](harmony.md#prossimo-accordo) e un bonus +0,8 se l'ultimo accordo è
    il I.

6. **Alternative**: le versioni successive aggiungono rumore gaussiano (σ 0,25) e −0,35 per gli accordi già usati in
   quel segmento.
7. **Clip**: accordi ripetuti uniti, voicing concatenati con `_fit` attorno al registro centrale e abbassati di
   un'ottava finché stanno sotto la melodia.

## Rilevamento della tonalità

Algoritmo di **Krumhansl-Schmuckler**: l'istogramma delle 12 classi di altezza (pesato per durata, prima e ultima
nota contano doppio) viene correlato (Pearson) con i profili di tonalità maggiore e minore ruotati sulle 12 toniche;
vince la correlazione massima tra le 24 tonalità. Serve quando una versione ha solo la melodia o per *Rileva dalla
melodia*.
