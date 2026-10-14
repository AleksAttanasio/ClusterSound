# Library

The Library analyses a folder of samples (recursively), assigns every file to one of the
[34 classes](../reference/classes.md) and shows the whole library as a **3D cloud**: similar sounds sit close
together, the colour of a point is its class.

![3D view](../assets/screenshots/library-3d.png){ .shot }

## Folder and scan

- **Choose folder…** (from the empty library or from Settings › Library): wav, aif, flac, ogg, mp3, caf, w64
  formats.
- The results go into a cache: a **Rescan** only reads new or modified files again. At startup the last folder is
  restored from a snapshot without analysing anything again.
- Store downloads saved inside the library folder are added with an automatic rescan.

## 3D view

- Drag to rotate, scroll to zoom, right-click to pan. At the bottom: auto-rotate, reset view, class labels on/off.
- **Click on a point**: immediate playback and the detail drawer opens.
- **Double-click**: *Find similar* on that sample.
- **Right-click**: *Send* menu (Sequencer, Drum Rack).

## Detail drawer

![Detail of a sample](../assets/screenshots/library-detail.png){ .shot }

- **Dynamics**: waveform with the RMS envelope in dB and the estimated ADSR phases.
- **Spectrogram**: click to play from that point.
- **Measures**: duration, peak, RMS, crest, attack, decay, sustain, release, T60, format, channels/bit, type,
  centroid, harmonicity, subcluster.
- **Class and alternatives**: the most likely classes with their confidence.
- **Actions**: *Play*, *Show in folder*, *Find similar*, *Send ▾*, *More in the Store* (opens the Store on the
  same class).

## Correcting a class

Change the class from the *Class* menu of the drawer: the sample becomes a **training example** and within a few
seconds every other classification is updated (the library head is retrained). Manual labels stay in the cache and
survive rescans. See [Classifier](../ai/classifier.md).

## Find similar

![Similar samples](../assets/screenshots/library-similar.png){ .shot }

Shows the closest samples (cosine similarity on the YAMNet embeddings) laid out around the centre, with the
similarity percentage. The slider chooses how many to show (5–60).

- **Click** listens, **double-click** re-centres on the sample: the stops form a **trail**, which the Drum Rack can
  use to fill a group (*Trail*).
- **▦ Drum Rack** fills the selected group with the similar samples; **Exit** goes back to the cloud.

## Filters and list

![List](../assets/screenshots/library-list.png){ .shot }

- **Class**: click to turn on/off, `Alt`+click = only that one; *All · None*.
- **Type**: One-shot, Loop, Long/Texture.
- **Minimum confidence** and **search** by name or folder.
- **List**: sortable table; `↑` `↓` move and listen.

## Export report

Settings › Library › **Export report**: CSV or JSON with path, class, confidence, alternatives, subcluster and
type of every sample. The same report can be produced without the GUI with `--headless`.

Shortcuts: `Space` play/stop, `Esc` closes the drawer.
