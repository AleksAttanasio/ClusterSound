# Classi

ClusterSound assegna ogni sample a una di **34 classi** in 5 gruppi, più *Unsorted* per i sample a bassa confidenza. Ogni classe ha un colore (lo stesso nella vista 3D, nei filtri e nello Store), un elenco di keyword usate dal parser dei nomi e una mappatura pesata sulle classi AudioSet di YAMNet.

La tassonomia è definita in un solo punto, `clustersound/taxonomy.py`: aggiungere o rinominare una classe richiede di riaddestrare la head base (vedi [Classificatore](../ai/classificatore.md)).

## Drums

| | Classe | Keyword (estratto) | Classi AudioSet principali |
|---|---|---|---|
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#ff4d4d"></span> | **Kick** | `kick`, `kik`, `kck`, `kicks`, `bd`, `bassdrum`, `bdrum` | Bass drum (1), Thump, thud (0.6), Thunk (0.4) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#ff9eaa"></span> | **808 / Sub Kick** | `808`, `808s`, `subkick`, `boom` | Rumble (0.6), Boom (0.6), Bass drum (0.5) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#e0603a"></span> | **Tom** | `tom`, `toms`, `floortom`, `hitom`, `lotom`, `midtom`, `lowtom` | Drum (1), Timpani (0.8), Tabla (0.3) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#ff9f1c"></span> | **Snare** | `snare`, `snr`, `sd`, `snares`, `sn`, `snre` | Snare drum (1), Drum roll (0.5), Drum (0.3) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#ffd1a1"></span> | **Rimshot / Sidestick** | `rim`, `rimshot`, `sidestick`, `stick`, `xstick`, `rims` | Rimshot (1), Wood block (0.4), Knock (0.4) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#d9480f"></span> | **Clap** | `clap`, `claps`, `clp`, `handclap`, `cp` | Clapping (1), Applause (0.6), Slap, smack (0.5) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#fff1e6"></span> | **Snap** | `snap`, `snaps`, `fingersnap`, `snp`, `finger` | Finger snapping (1), Clicking (0.4) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#ffe14d"></span> | **Closed Hat** | `chh`, `ch`, `closedhat`, `hhc`, `hatc`, `closed`, `cl` | Hi-hat (1), Spray (0.3), Clicking (0.3) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#c9a227"></span> | **Open Hat** | `oh`, `ohh`, `ohat`, `openhat`, `hho`, `hatopen`, `open` | Hi-hat (0.8), Cymbal (0.5), Sizzle (0.4) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#fff59d"></span> | **Ride** | `ride`, `rides`, `rd` | Cymbal (0.7), Bell (0.3) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#a3a336"></span> | **Crash** | `crash`, `crsh`, `crashes`, `cr` | Cymbal (1), Smash, crash (0.5), Gong (0.3) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#f4c430"></span> | **Other Cymbal** | `cymbal`, `cym`, `splash`, `china`, `cymbals`, `cymb` | Cymbal (0.8), Gong (0.6) |

## Percussion

| | Classe | Keyword (estratto) | Classi AudioSet principali |
|---|---|---|---|
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#7bd389"></span> | **Shaker** | `shaker`, `shk`, `shake`, `maraca`, `maracas`, `cabasa`, `egg` | Maraca (1), Rattle (instrument) (0.8), Rattle (0.6) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#2fa84f"></span> | **Tambourine** | `tamb`, `tambourine`, `tambo`, `tamborine`, `tmb`, `tambourin` | Tambourine (1), Jingle bell (0.6), Jingle, tinkle (0.5) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#c5f5c8"></span> | **Cowbell** | `cowbell`, `cow`, `cb`, `agogo` | Cowbell (1), Bell (0.3) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#1fb5a0"></span> | **Woodblock / Clave** | `woodblock`, `block`, `wood`, `clave`, `claves`, `blk`, `click` | Wood block (1), Wood (0.5), Knock (0.5) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#a6d75b"></span> | **Conga / Bongo / Hand Drum** | `conga`, `congas`, `bongo`, `bongos`, `djembe`, `tabla`, `cajon` | Tabla (1), Drum (0.6), Percussion (0.4) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#5aa832"></span> | **Bell / Triangle** | `bell`, `bells`, `triangle`, `tri`, `chime`, `chimes`, `gong` | Bell (1), Chime (0.9), Wind chime (0.8) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#5fd3bc"></span> | **Other Perc** | `perc`, `percussion`, `prc`, `percs`, `guiro`, `vibraslap`, `whistle` | Percussion (1), Drum machine (0.5), Drum kit (0.4) |

## Melodic/Bass

| | Classe | Keyword (estratto) | Classi AudioSet principali |
|---|---|---|---|
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#3b82f6"></span> | **Bass** | `bass`, `bs`, `bassline`, `reese`, `subbass`, `sub`, `basses` | Bass guitar (1), Double bass (0.8) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#60c0ff"></span> | **Synth (lead/pluck)** | `synth`, `lead`, `pluck`, `arp`, `stab`, `saw`, `square` | Synthesizer (1), Sampler (0.5), Electronic music (0.3) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#b3d4ff"></span> | **Pad** | `pad`, `pads`, `drone`, `swell` | Ambient music (0.8), New-age music (0.6), Synthesizer (0.5) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#818cf8"></span> | **Keys / Piano** | `keys`, `key`, `piano`, `pno`, `rhodes`, `ep`, `organ` | Piano (1), Electric piano (1), Organ (1) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#6366f1"></span> | **Guitar** | `guitar`, `gtr`, `gtrs`, `strum`, `riff`, `guitars`, `banjo` | Guitar (1), Electric guitar (1), Acoustic guitar (1) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#a78bfa"></span> | **Strings** | `strings`, `string`, `violin`, `viola`, `cello`, `str`, `orch` | Bowed string instrument (1), String section (1), Violin, fiddle (1) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#e0d4ff"></span> | **Brass / Wind** | `brass`, `horn`, `horns`, `trumpet`, `trombone`, `sax`, `saxophone` | Brass instrument (1), French horn (1), Trumpet (1) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#8b5cf6"></span> | **Mallets** | `marimba`, `xylophone`, `vibraphone`, `vibes`, `glock`, `glockenspiel`, `kalimba` | Mallet percussion (1), Marimba, xylophone (1), Glockenspiel (1) |

## Vocal

| | Classe | Keyword (estratto) | Classi AudioSet principali |
|---|---|---|---|
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#ff5fa2"></span> | **Vocal / Vox** | `vocal`, `vox`, `vocals`, `voice`, `vocalchop`, `acapella`, `adlib` | Singing (1), Choir (1), Child singing (1) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#e0559b"></span> | **Spoken / Chant** | `spoken`, `speech`, `talk`, `phrase`, `word`, `words`, `shout` | Speech (1), Child speech, kid speaking (1), Conversation (1) |

## FX & altro

| | Classe | Keyword (estratto) | Classi AudioSet principali |
|---|---|---|---|
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#22d3ee"></span> | **Riser / Sweep** | `riser`, `rise`, `uplifter`, `uplift`, `sweep`, `sweepup`, `buildup` | Whoosh, swoosh, swish (1), Chirp tone (0.5), Siren (0.4) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#0fa3b1"></span> | **Impact / Hit** | `impact`, `hit`, `hits`, `slam`, `thud`, `braam`, `impacts` | Bang (1), Explosion (1), Whack, thwack (0.8) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#a5f3fc"></span> | **Downlifter** | `downlifter`, `downer`, `down`, `fall`, `sweepdown`, `downsweep` | Whoosh, swoosh, swish (0.7), Chirp tone (0.4) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#94a3b8"></span> | **Noise / Texture / Ambience** | `noise`, `texture`, `ambience`, `ambient`, `atmo`, `atmos`, `atmosphere` | Noise (1), White noise (1), Pink noise (1) |
| <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#b08968"></span> | **Foley** | `foley`, `fol`, `footstep`, `footsteps`, `door`, `glass`, `metal` | Walk, footsteps (1), Door (1), Glass (1) |

!!! note "Unsorted"
    Un sample finisce in *Unsorted* quando la probabilità della classe migliore è sotto **0,22** (`UNSORTED_THRESHOLD` in `classifier.py`). Correggerlo a mano lo rende un esempio di training.

## Tipo

Oltre alla classe ogni sample ha un **tipo**:

| Tipo | Regola |
|---|---|
| **Loop** | durata ≥ 1,5 s e almeno 4 onset, oppure un nome/cartella con token da loop (`loop`, `bpm`, `groove`, `break`, `120bpm`…) e durata > 1 s |
| **Long/Texture** | durata ≥ 2,5 s e non è un loop |
| **One-shot** | tutto il resto |

