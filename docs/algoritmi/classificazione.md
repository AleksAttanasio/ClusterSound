# Classificazione

La parte di modello (head MLP, training, fusione, accuratezza) è descritta in
[Modelli AI › Classificatore](../ai/classificatore.md). Qui la **strategia**: perché quattro segnali e come si
completano.

## Il problema

Una libreria di sample reale è eterogenea: pack commerciali con nomi perfetti (`Snare 07.wav`), registrazioni con
nomi anonimi (`A101.wav`), cartelle che dicono la classe (`/Kicks/…`) o la confondono (`/Drum Loops/…`), loop,
texture. Nessun segnale da solo basta:

| Segnale | Forte quando | Debole quando |
|---|---|---|
| Nome e cartelle | nomi dei pack | nomi anonimi, nomi ambigui (`cl`, `op`, `sd`) |
| Zero-shot YAMNet | categorie che AudioSet conosce (snare, clap, guitar) | distinzioni da produttore (closed/open hat, kick/808) |
| Regole acustiche | proprietà fisiche nette (basso vs acuto, corto vs lungo) | casi intermedi |
| Head MLP | sempre, se ha visto esempi simili | classi rare |

La fusione somma evidenze in **log-probabilità**: ogni segnale sposta la distribuzione senza poterla dominare, e
quando un segnale manca (nome anonimo → log-prior nullo) gli altri decidono.

## Parser dei nomi

- **Tokenizzazione**: separatori, camelCase (`ClosedHat` → `closed`, `hat`), confini lettera/cifra (`kick04` →
  `kick`, `04`), più le varianti unite (`open hat` → `openhat`).
- **Keyword per classe** da `taxonomy.py`, con peso ridotto per i token ambigui.
- **Regole di contesto**:
    - una parola da hat con "open" → open hat 1,0; senza → closed hat 0,8 (e open hat 0,3); "open"/"closed" senza
      parola da hat dimezzano l'evidenza;
    - "808" accanto a un altro nome di tamburo pesa ×0,2 (è la drum machine TR-808, non un sub kick), accanto a
      "kick" ×0,6, accanto a "bass" vince l'808;
    - le parole generiche ("cymbal", "perc") perdono contro una specifica nello stesso nome;
    - `fx`, `sfx`, `transition`… danno 0,3 a riser, impact, downlifter e noise.
- **Profondità**: il file pesa 1, la cartella madre 0,65, poi 0,45, 0,3, 0,2; per ogni classe si tiene il massimo.

## Regole acustiche (`features.rule_logits`)

Priori additivi costruiti con sigmoidi morbide \(\sigma\big((x-c)/w\big)\), quindi senza soglie nette:

| Regola | Effetto |
|---|---|
| **Energia sotto 250 Hz** \(> 0{,}55\) | + kick, 808, bass, tom; − hat, shaker, piatti |
| **Energia sopra 6 kHz** \(> 0{,}35\) | + hat, shaker, piatti, tamburello; − kick, 808, bass, tom |
| **Decay a −20 dB** \(> 0{,}25\) s | + open hat, − closed hat |
| **T60** \(> 0{,}8\) s | + crash |
| **Coda tonale bassa** (T60 lungo × armonico × basso) | + 808, − kick |
| **Thump** (basso × decay < 0,35 s × attacco < 10 ms) | + kick, + tom, − bass |
| **Durata** < 0,12 s | + snap, rimshot, woodblock, closed hat |
| **Durata** > 2 s | + pad, noise, riser, downlifter (− se one-shot corto) |
| **Tonale** (armonicità alta × piattezza bassa) | + strumenti melodici e voce |
| **Rumoroso** (piattezza alta) | + hat, shaker, snare, clap, noise, riser, crash |
| **Sweep** (centroide e inviluppo in salita/discesa, su suoni lunghi) | + riser / + downlifter |
| **Attacco leggermente lento** e rumoroso | + clap (più colpi in ~40 ms allungano l'attacco) |

## Self-training sulla libreria

L'idea chiave: **i nomi chiari di una libreria insegnano a classificare i file anonimi della stessa libreria**.
Ogni classificazione addestra una head sui file il cui nome ha una keyword forte (≥ 0,75) e sulle correzioni
manuali (peso 3). Poiché i suoni di uno stesso pack si somigliano, la head generalizza ai file senza nome molto
meglio dello zero-shot (72% contro 16% nella [valutazione](../ai/classificatore.md#accuratezza)).

## Unsorted e correzioni

Sotto il 22% di probabilità la classe è *Unsorted*: meglio un "non so" che un errore sicuro. Ogni correzione:

1. salva l'etichetta in `cache.sqlite` (sopravvive alle riscansioni);
2. aggiorna subito quel sample;
3. riaddestra in background la head di libreria e ricalcola classi e sottocluster di tutta la libreria;
4. invalida lo snapshot (l'impronta include le etichette).
