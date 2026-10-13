# Primo avvio

1. Avvia l'app (`python -m clustersound` o `ClusterSound.app`).
2. Nella Libreria vuota premi **Scegli cartella…** e indica la cartella dei sample (viene letta ricorsivamente).
3. Attendi l'analisi: la barra in alto mostra le fasi *Ricerca file → Analisi → Classificazione → Mappa*.
   Durante il calcolo della mappa compare subito un'anteprima (PCA), poi la vista definitiva (t-SNE).
4. Clicca un punto della nuvola: il sample suona e si apre la tendina di dettaglio.

![La libreria dopo l'analisi](../assets/screenshots/libreria-3d.png){ .shot }

!!! tip "Tempi"
    La prima analisi usa tutti i core e mostra file/s in tempo reale. Le successive sono quasi istantanee: i file
    non modificati vengono dalla cache e, se nulla è cambiato, l'intera libreria si ripristina da uno snapshot.

!!! note "I tuoi file non vengono toccati"
    ClusterSound non modifica, sposta o rinomina mai i file originali. Classi, correzioni e mappa stanno nella
    cartella dei dati dell'app.

| | macOS | Windows |
|---|---|---|
| Dati (impostazioni, cache, snapshot, modelli) | `~/Library/Application Support/ClusterSound` | `%APPDATA%\ClusterSound` |
| Cache (anteprime online, helper) | `~/Library/Caches/ClusterSound` | `%LOCALAPPDATA%\ClusterSound\Cache` |
| Download, Sample, Registrazioni, Pattern | `~/Music/ClusterSound …` | `~\Music\ClusterSound …` |

**Non hai ancora sample?** Premi *Sfoglia lo Store gratuito*: vedi [Store](../manuale/store.md).
