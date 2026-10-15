# Store

Code: `online/` (`search.py`, `instruments.py`, `base.py`, `cache.py`, `downloads.py`, `catalog.py` and one module per
provider).

## Federated search

`search()` queries **Freesound, Openverse, Internet Archive and ccMixter in parallel** (`ThreadPoolExecutor`). Errors
are per source: a slow or failing source shows its message without blocking the others.

Every provider translates the filters into its own query language:

| Source | Query |
|---|---|
| Freesound | Solr filter `tag:(…)` + licence, duration, BPM, key, `single_event`/`loopable`, file type; for packs `group_by_pack=1` |
| Openverse | one query per instrument (up to 4) in parallel, results interleaved and deduplicated; sources limited to Freesound and Wikimedia (Jamendo has whole songs, not samples) |
| Internet Archive | `mediatype:audio` + "sample pack" context, MIDI excluded; a declared licence is required unless asked otherwise |
| ccMixter | `reqtags=sample` + instrument tags |

Every module declares which filters it applies **server-side** (`SERVER_FILTERS`, the FS·OV·IA·CC tags in the UI);
all the results go through the **local** `passes()` filter anyway (instrument, licence, commercial use, file/pack,
type, duration, BPM, key, lossless, suspect packs), so the filters work the same on every source. Packs skip the
per-file checks until they are expanded.

## Labelling by instrument

The sources do not know the 34 classes: every result is labelled **with the same name parser as the library**
(`instruments.infer_label`), which returns a class and a state: *sure*, *weak* (shown as "Class ?"), *mix* or none:

1. phrases rewritten into the taxonomy keywords ("bass drum" → kick, "down sweep" → downlifter, "SDR" → snare);
2. score on the title, or on the path inside a pack (with the decreasing folder weights), plus the tags at 0.8:
   evidence from both adds up, and every extra tag that backs the same class adds 0.1;
3. ties are broken by the title, then by the number of agreeing tags, then by taxonomy order — never by tag order
   (Freesound sorts tags alphabetically, so "bass, kick" used to win over "kick, bass");
4. non-musical context (soccer, car, gun…) in the title **or** the tags without musical words: no musical class
   (FX and foley classes stay allowed);
5. **mix**: a drum class with "kit" in the title, a beat/loop whose title does not name the drum, or several strong
   classes at once. A one-shot (≤ 1.5 s, or tagged "one shot") is never a mix;
6. a near tie (< 0.15) with nothing in the name: no class (pack-wide tags like "kick snare toms" say nothing about
   one file);
7. *sure* from 0.7 (0.6 inside a pack), *weak* from 0.45.

Freesound packs are labelled from their own name, not from the sound that stands for them. The store home only
shows *sure* results of the category it queried, so the badge always matches.

A result is kept if its class is in the filter, or if the server already found it for that instrument and it has no
non-musical context. The **type** comes from name, tags and duration (one-shot ≤ 2.5 s, loop if it has a BPM in the
title, …); **BPM** (50–220) and **key** from the title (the key needs an accidental or the mode word, so that normal
words are not read as notes).

## Suspect packs

A regex of commercial producers (Big Fish Audio, Sound Ideas, Native Instruments, Splice, Loopmasters, Cymatics,
Apple Loops, Ableton packs…) and of piracy words (leaked, cracked, warez, torrent) is applied to the title, author and
subjects of Internet Archive packs. Files inherit the flag from the pack; suspect ones are hidden unless asked for.

**Expanding Internet Archive packs**: only original loose files, ZIP contents read from the listing page (4 threads,
`__MACOSX` excluded), duplicates with the same name reduced to the best format (wav > aif > flac > ogg > mp3), at
most 3000 files.

## Cache and licences

- **HTTP responses**: in-memory cache per URL + parameters + headers, 10 minutes (1 hour for Freesound packs),
  cleared beyond 500 entries.
- **Audio previews**: files named after the SHA-1 of the URL, only from allowed hosts, at most 60 MB each, atomic
  write; access updates the date (LRU) and `prune` deletes the oldest beyond the limit (300 MB), **except** the
  samples used by the open pattern or rack.
- **Licences** normalised into cc0, pd, by, by-sa, by-nd, by-nc, by-nc-sa, by-nc-nd, sampling+, rf, unknown;
  *commercial use* = cc0, pd, by, by-sa, rf.
- **Downloads** only from allowed hosts, safe names on Windows too, with `.license.txt` (author, licence, link,
  attribution) in the interface language.
