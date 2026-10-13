# Store

Codice: `online/` (`search.py`, `instruments.py`, `base.py`, `cache.py`, `downloads.py`, `catalog.py` e un modulo per
provider).

## Ricerca federata

`search()` interroga **Freesound, Openverse, Internet Archive e ccMixter in parallelo** (`ThreadPoolExecutor`). Gli
errori sono per fonte: una fonte lenta o in errore mostra il suo messaggio senza bloccare le altre.

Ogni provider traduce i filtri nel proprio linguaggio di query:

| Fonte | Query |
|---|---|
| Freesound | filtro Solr `tag:(…)` + licenza, durata, BPM, tonalità, `single_event`/`loopable`, tipo di file; per i pack `group_by_pack=1` |
| Openverse | una query per strumento (fino a 4) in parallelo, risultati intercalati e deduplicati; fonti limitate a Freesound e Wikimedia (Jamendo ha brani interi, non sample) |
| Internet Archive | `mediatype:audio` + contesto "sample pack", MIDI esclusi; licenza dichiarata obbligatoria salvo richiesta |
| ccMixter | `reqtags=sample` + tag dello strumento |

Ogni modulo dichiara quali filtri applica **lato server** (`SERVER_FILTERS`, le etichette FS·OV·IA·CC nella UI); tutti
i risultati passano comunque dal filtro **locale** `passes()` (strumento, licenza, uso commerciale, file/pack, tipo,
durata, BPM, tonalità, lossless, pack sospetti), così i filtri valgono uguale su ogni fonte. I pack saltano i controlli
per file finché non vengono espansi.

## Etichettatura per strumento

Le fonti non conoscono le 34 classi: ogni risultato viene etichettato **con lo stesso parser dei nomi della
libreria** (`instruments.infer`):

1. se i tag contengono parole di contesto non musicale (soccer, door, gun…) senza parole musicali, nessuna classe;
2. frasi riscritte nelle keyword della tassonomia ("bass drum" → kick);
3. punteggio sul titolo, o sul percorso dentro un pack (con i pesi decrescenti delle cartelle); i tag contano 0,8;
4. la classe migliore se il punteggio è ≥ 0,45.

Un risultato è tenuto se la classe è nel filtro, oppure se il server l'ha già trovato per quello strumento e non ha
contesto non musicale. Il **tipo** viene da nome, tag e durata (one-shot ≤ 2,5 s, loop se ha un BPM nel titolo, …);
**BPM** (50–220) e **tonalità** dal titolo (la tonalità richiede un'alterazione o la parola del modo, per non leggere
parole normali come note).

## Pack sospetti

Una regex di produttori commerciali (Big Fish Audio, Sound Ideas, Native Instruments, Splice, Loopmasters, Cymatics,
Apple Loops, pack di Ableton…) e di parole da pirateria (leaked, cracked, warez, torrent) viene applicata a titolo,
autore e soggetti dei pack di Internet Archive. I file ereditano il flag dal pack; i sospetti sono nascosti salvo
richiesta.

**Espansione dei pack di Internet Archive**: file sciolti solo originali, contenuto degli ZIP letto dalla pagina di
elenco (4 thread, `__MACOSX` escluso), duplicati con lo stesso nome ridotti al formato migliore (wav > aif > flac > ogg
> mp3), al massimo 3000 file.

## Cache e licenze

- **Risposte HTTP**: cache in memoria per URL + parametri + header, 10 minuti (1 ora per i pack di Freesound),
  svuotata oltre 500 voci.
- **Anteprime audio**: file con nome SHA-1 dell'URL, solo da host consentiti, al massimo 60 MB ciascuno, scrittura
  atomica; l'accesso aggiorna la data (LRU) e `prune` elimina i più vecchi oltre il limite (300 MB), **tranne** i
  sample usati dal pattern o dal rack aperti.
- **Licenze** normalizzate in cc0, pd, by, by-sa, by-nd, by-nc, by-nc-sa, by-nc-nd, sampling+, rf, unknown;
  *uso commerciale* = cc0, pd, by, by-sa, rf.
- **Download** solo da host consentiti, nomi sicuri anche su Windows, con `.license.txt` (autore, licenza, link,
  attribuzione).
