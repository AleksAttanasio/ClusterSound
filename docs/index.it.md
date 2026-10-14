---
hide:
  - navigation
---

# ClusterSound

**Classifica, esplora in 3D e mette al lavoro la tua libreria di sample.** App desktop per macOS e Windows che
analizza una cartella di sample audio, assegna ogni file a una classe di suono — kick, snare, hat, 808, pad… — e
mostra l'intera libreria come una nuvola 3D in cui i suoni simili stanno vicini. Da lì costruisci kit, groove e
progressioni e li porti in Ableton Live. Tutto in locale, senza mai modificare i tuoi file.

![ClusterSound](assets/screenshots/library-3d.png){ .shot }

[Installa :material-download:](guide/installation.md){ .md-button .md-button--primary }
[Manuale :material-book-open-variant:](manual/index.md){ .md-button }
[Come funziona :material-cog:](technical/index.md){ .md-button }

## Cosa fa

<div class="grid cards" markdown>

- :material-scatter-plot: **Libreria** — 34 classi, sottogruppi di suoni simili, mappa 3D t-SNE, *Trova simili*,
  correzioni che insegnano al classificatore. [→](manual/library.md)
- :material-store: **Store** — sample e pack gratuiti da Freesound, Openverse, Internet Archive e ccMixter, filtrati
  per strumento e licenza. [→](manual/store.md)
- :material-microphone: **Recorder** — registra l'uscita audio, taglia sui transienti, separa gli stem e restaura
  l'audio compresso con l'AI. [→](manual/recorder.md)
- :material-view-grid: **Sequencer** — 191 groove di 47 generi per provare i sample, layer, arrangiamento ed export
  per Ableton. [→](manual/sequencer.md)
- :material-grid: **Drum Rack** — kit di sample simili per Launchpad 8×8 e Roland SPD-SX. [→](manual/drum-rack.md)
- :material-piano: **Compose** — progressioni da un chord pack con suggerimenti armonici, variazioni, melodie e
  bassi generati. [→](manual/compose.md)

</div>

## Come è fatta

<div class="grid cards" markdown>

- **[Guida rapida](guide/index.md)** — installazione, primo avvio, Ableton Live, build: pochi passi.
- **[Manuale](manual/index.md)** — ogni sezione dell'app, con screenshot.
- **[Tecnica](technical/index.md)** — architettura, backend Python, frontend web, dati, integrazione con Live.
- **[Modelli AI](ai/index.md)** — YAMNet in numpy, classificatore MLP auto-addestrato, Demucs, Apollo.
- **[Algoritmi](algorithms/index.md)** — classificazione, clustering, scelta dei sample, groove, armonia, melodia.
- **[Riferimento](reference/classes.md)** — classi, impostazioni, scorciatoie.

</div>

!!! note "Lingua"
    L'app e questa documentazione sono in inglese, con la versione italiana sempre disponibile. Nell'app la lingua si
    sceglie in **Impostazioni › Generale › Lingua**; qui con il menu della lingua in alto nella pagina.
