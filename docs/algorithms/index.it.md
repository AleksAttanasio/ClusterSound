# Strategie e algoritmi

Come ClusterSound prende le sue decisioni: dall'analisi del segnale alla scelta dei sample di un kit, dal prossimo
accordo suggerito alla melodia generata. Ogni pagina indica i moduli coinvolti e le costanti reali usate nel codice.

| Funzione | Strategia in una riga | Pagina |
|---|---|---|
| Analisi | 22 feature d'inviluppo e spettro + profilo mel + onset multi-banda | [Analisi audio](audio-analysis.md) |
| Classificazione | nome + zero-shot + regole + MLP, fusi in log-probabilità | [Classificazione](classification.md) |
| Sottogruppi | k-means per classe, k scelto con la silhouette | [Clustering e mappa](clustering-and-map.md) |
| Mappa 3D | PCA → t-SNE 3D, landmark oltre 2500 punti | [Clustering e mappa](clustering-and-map.md) |
| Simili | coseno sugli embedding YAMNet | [Clustering e mappa](clustering-and-map.md) |
| Kit del Drum Rack | vicini senza doppioni, scelta casuale pesata con temperatura, gruppi diversi, dinamiche simili | [Drum Rack](drum-rack.md) |
| SPD-SX | configurazioni casuali vincolate da limiti di suonabilità | [Drum Rack](drum-rack.md#roland-spd-sx) |
| Groove | pattern a step con swing MPC, roll, alternanza deterministica dei layer | [Sequencer](sequencer.md) |
| Prossimo accordo | punteggio additivo: funzione, cadenze, moto del basso, note comuni, voice leading, statistiche del pack | [Armonia](harmony.md) |
| Variazioni | voicing a minima distanza, riarmonizzazione pesata, ritmo armonico | [Armonia](harmony.md) |
| Melodia | contorno target + scelta nota per punteggio, frasi domanda/risposta | [Melodia](melody.md) |
| Accordi dalla melodia | punteggio di adattamento + Viterbi | [Melodia](melody.md#accordi-dalla-melodia) |
| Tonalità | profili di Krumhansl-Schmuckler | [Melodia](melody.md#rilevamento-della-tonalita) |
| Tagli | novelty spettrale multi-banda, picchi sopra soglia | [Recorder e slicing](recorder-and-slicing.md) |
| Store | ricerca federata parallela, filtri lato server o locali, etichettatura per strumento | [Store](store.md) |

!!! note "Determinismo"
    Quasi tutto ciò che è "casuale" usa un **seed** esplicito (`np.random.default_rng(seed)`, `random.Random(seed)` o
    un hash intero): la stessa scelta produce lo stesso risultato, e i pulsanti 🎲 / *Rigenera* cambiano il seed.
    Fa eccezione *Varia* nel Sequencer, che usa `Math.random`.
