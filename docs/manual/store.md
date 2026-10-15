# Store

A store of **free samples**: it searches four free sources at once, plays straight away and downloads with the
licence next to the file. You also get there from the empty library (*Browse the free Store*) and from the drawer
of a sample (*More in the Store*).

![Store home](../assets/screenshots/store-home.png){ .shot }

## Sources

| Source | What it offers | Access |
|---|---|---|
| Freesound | ~600k CC sounds (one-shots, loops, field recordings) with BPM, key, waveform, organised in packs | free API key (Settings › Store → *request a key*) |
| Openverse | CC aggregator (Freesound, Wikimedia Commons) | anonymous, low rate limits |
| Internet Archive | Whole sample packs, browsable file by file even inside ZIPs | anonymous |
| ccMixter | CC stems, a cappellas and loops | anonymous |

The **showcase** lists packs from sites without a public API, usable in commercial productions: Kenney (CC0),
Sonniss GameAudioGDC, 99Sounds, SampleRadar. The button opens the official page to download them from.

## Searching

![Results](../assets/screenshots/store-results.png){ .shot }

- **Home**: a carousel of the sites (arrows to scroll, click to open the site page), then for every live site a
  carousel of example samples picked across categories (kick, snare, hat, percussion, bass, synth, keys, vocal,
  FX), then the showcase of curated packs. The filter sidebar only appears on the results.
- **Category badge** on every card: the class colour and name; **Class ?** when the label is uncertain (only
  ambiguous words, or a near tie); **Mix** for loops, beats and kits with several instruments.
- **Results**: *Sounds* or *Packs*, in a grid (cards with waveform, licence, duration, BPM, key) or in a list
  grouped by source or by instrument.
- **Instrument filter**: the same 34 classes and colours as the library. Non-musical false positives
  ("soccer kick", "waves crashing") are discarded.
- **Other filters**: source, licence (CC0/PD, BY, BY-SA, NC, ND, not declared), *commercial use only*, type,
  duration, BPM, key, lossless only, single files or packs, sort order. The tag next to each filter (FS·OV·IA·CC)
  shows the sources that apply it server-side; on the others it is applied locally.
- **Pack page**: description, licence, number of sounds, *Listen to all*, *Download pack*, tracks one by one and
  more packs by the same author. **Provider page**: description, typical licences, link, packs and sounds.

## Listening, downloading, using

- **▶** plays straight away; **→** sends the sample to the Sequencer or the Drum Rack without downloading it (it
  stays in the temporary cache until you export).
- **⬇** downloads into `~/Music/ClusterSound Downloads/<Source>/` (configurable) with a `.license.txt` that holds
  author, licence, link and attribution text. From Freesound without an OAuth login you download the HQ mp3
  preview; the original is downloaded from the page (↗).
- If the downloads folder is inside the open library, the library updates by itself when the download ends;
  otherwise the downloads panel offers *Open in library*.

!!! warning "Suspect packs"
    Internet Archive packs that look like commercial libraries re-uploaded with a free licence (Big Fish Audio,
    Sound Ideas, Loopmasters, GarageBand…) are marked ⚠ and hidden by default (Settings › Store ›
    *Suspect packs*). Those without a declared licence only show up when choosing *Not declared*.

How federated search, labelling and the cache work: [Algorithms › Store](../algorithms/store.md).
