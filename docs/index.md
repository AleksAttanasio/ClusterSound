---
hide:
  - navigation
---

# ClusterSound

**Classifica, esplora in 3D e mette al lavoro la tua libreria di sample.** App desktop per macOS e Windows che
analizza una cartella di sample audio, assegna ogni file a una classe di suono — kick, snare, hat, 808, pad… — e
mostra l'intera libreria come una nuvola 3D in cui i suoni simili stanno vicini. Da lì costruisci kit, groove e
progressioni e li porti in Ableton Live. Tutto in locale, senza mai modificare i tuoi file.

![ClusterSound](assets/screenshots/libreria-3d.png){ .shot }

[Installa :material-download:](guida/installazione.md){ .md-button .md-button--primary }
[Manuale :material-book-open-variant:](manuale/index.md){ .md-button }
[Come funziona :material-cog:](tecnica/index.md){ .md-button }

## Cosa fa

<div class="grid cards" markdown>

- :material-scatter-plot: **Libreria** — 34 classi, sottogruppi di suoni simili, mappa 3D t-SNE, *Trova simili*,
  correzioni che insegnano al classificatore. [→](manuale/libreria.md)
- :material-store: **Store** — sample e pack gratuiti da Freesound, Openverse, Internet Archive e ccMixter, filtrati
  per strumento e licenza. [→](manuale/store.md)
- :material-microphone: **Recorder** — registra l'uscita audio, taglia sui transienti, separa gli stem e restaura
  l'audio compresso con l'AI. [→](manuale/recorder.md)
- :material-view-grid: **Sequencer** — 191 groove di 47 generi per provare i sample, layer, arrangiamento ed export
  per Ableton. [→](manuale/sequencer.md)
- :material-grid: **Drum Rack** — kit di sample simili per Launchpad 8×8 e Roland SPD-SX. [→](manuale/drum-rack.md)
- :material-piano: **Compose** — progressioni da un chord pack con suggerimenti armonici, variazioni, melodie e
  bassi generati. [→](manuale/compose.md)

</div>

## Come è fatta

<div class="grid cards" markdown>

- **[Guida rapida](guida/index.md)** — installazione, primo avvio, Ableton Live, build: pochi passi.
- **[Manuale](manuale/index.md)** — ogni sezione dell'app, con screenshot.
- **[Tecnica](tecnica/index.md)** — architettura, backend Python, frontend web, dati, integrazione con Live.
- **[Modelli AI](ai/index.md)** — YAMNet in numpy, classificatore MLP auto-addestrato, Demucs, Apollo.
- **[Algoritmi](algoritmi/index.md)** — classificazione, clustering, scelta dei sample, groove, armonia, melodia.
- **[Riferimento](riferimento/classi.md)** — classi, impostazioni, scorciatoie.

</div>
