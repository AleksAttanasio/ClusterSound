# Impostazioni

Salvate in `settings.json` nella cartella dei dati dell'app. Quelle modificabili dall'app passano da
`Api.set_setting`, che accetta solo le chiavi seguenti; altre scelte di interfaccia (vista, filtri, ultimo tab…)
restano nel `localStorage` della WebView.

| Chiave | Default | Dove | Descrizione |
|---|---|---|---|
| `language` | `en` | Generale | lingua dell'interfaccia: `en` (English) o `it` (Italiano); cambiarla ricarica l'app |
| `last_folder` | — | Libreria | ultima cartella analizzata, ripristinata all'avvio |
| `freesound_key` | — | Store | API key di Freesound (nell'app se ne vedono solo i primi e ultimi caratteri) |
| `download_dir` | `~/Music/ClusterSound Downloads` | Store | cartella dei download |
| `cache_mb` | 300 | Generale | limite della cache temporanea (50–10000 MB) |
| `live_port` | 8770 | Generale | porta del bridge per il device Max for Live (1024–65535) |
| `live_library` | User Library di Live | Generale | dove scrivere i rack per Live |
| `sampler_dir` | `~/Music/ClusterSound Samples` | Recorder | cartella di esportazione: tagli, stem e file migliorati (Impostazioni › Recorder › *Cartella di esportazione*) |
| `sampler_max_seconds` | 30 | Recorder | durata massima di un sample estratto |
| `recorder_dir` | `~/Music/ClusterSound Recordings` | Recorder | cartella delle registrazioni |
| `recorder_format` | — | Recorder | formato, bit, bitrate, frequenza e canali |
| `chord_pack_dir` | vuoto (pack incluso) | Compose | cartella del tuo chord pack (impostata da *Scegli…*, svuotata da *Usa quello incluso*) |

La mappatura delle note del Drum Rack è salvata con il kit, non in `settings.json`.
