"""Store catalogue: the providers (searchable through an API or curated) and the curated free packs.

Curated packs come from sites without a public API: the store shows them as cards and opens the
official page to download (no scraping). Only royalty-free sources usable in commercial music.
"""
import os

LOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "assets", "providers")

# kind: "api" = searched live by the store; "curated" = static showcase linking to the official page
PROVIDERS = [
    {"id": "freesound", "name": "Freesound", "kind": "api", "url": "https://freesound.org",
     "color": "#e04a3f", "licenses": ["cc0", "by", "nc"],
     "description": "Oltre 600.000 suoni caricati dalla community, organizzati in pack. Richiede una API key gratuita."},
    {"id": "openverse", "name": "Openverse", "kind": "api", "url": "https://openverse.org",
     "color": "#ffe033", "licenses": ["cc0", "by", "by-sa"],
     "description": "Motore di ricerca di WordPress per opere con licenza aperta: indicizza Freesound e Wikimedia Commons."},
    {"id": "archive", "name": "Internet Archive", "kind": "api", "url": "https://archive.org",
     "color": "#cfcfcf", "licenses": ["cc0", "pd", "by"],
     "description": "Biblioteca digitale no-profit: interi sample pack e drum kit sfogliabili file per file."},
    {"id": "ccmixter", "name": "ccMixter", "kind": "api", "url": "https://ccmixter.org",
     "color": "#7fb3d5", "licenses": ["cc0", "by", "nc"],
     "description": "Community di remix: sample, stem e a cappella con licenza Creative Commons."},
    {"id": "kenney", "name": "Kenney", "kind": "curated", "url": "https://kenney.nl/assets/category:Audio",
     "color": "#f5a623", "licenses": ["cc0"],
     "description": "Pack audio CC0 (pubblico dominio) pensati per i giochi: impatti, UI, sci-fi, foley."},
    {"id": "sonniss", "name": "Sonniss", "kind": "curated", "url": "https://sonniss.com/gameaudiogdc",
     "color": "#d0021b", "licenses": ["rf"],
     "description": "GameAudioGDC: ogni anno decine di GB di effetti professionali royalty-free, senza attribuzione."},
    {"id": "99sounds", "name": "99Sounds", "kind": "curated", "url": "https://99sounds.org",
     "color": "#2ecc71", "licenses": ["rf"],
     "description": "Sample pack gratuiti curati da sound designer: drum, texture cinematiche, dub."},
    {"id": "sampleradar", "name": "SampleRadar", "kind": "curated",
     "url": "https://www.musicradar.com/news/tech/free-music-samples-download-loops-hits-and-multis-627820",
     "color": "#e2001a", "licenses": ["rf"],
     "description": "Decine di migliaia di loop e one-shot di Computer Music e Future Music, royalty-free."},
]

_NO_REDIST = "Royalty-free anche per uso commerciale; vietato ridistribuire i file così come sono."

# instruments: class ids of clustersound.taxonomy (used for the store's category tiles)
CURATED_PACKS = [
    {"id": "kenney-impact", "provider": "kenney", "title": "Impact Sounds", "count": 130, "license": "cc0",
     "instruments": ["impact", "foley"], "url": "https://kenney.nl/assets/impact-sounds",
     "description": "Colpi, passi e impatti su materiali diversi."},
    {"id": "kenney-scifi", "provider": "kenney", "title": "Sci-fi Sounds", "count": None, "license": "cc0",
     "instruments": ["riser", "noise"], "url": "https://kenney.nl/assets/sci-fi-sounds",
     "description": "Laser, motori, computer e sweep fantascientifici."},
    {"id": "kenney-interface", "provider": "kenney", "title": "Interface Sounds", "count": None, "license": "cc0",
     "instruments": ["perc_other"], "url": "https://kenney.nl/assets/interface-sounds",
     "description": "Click, bip e conferme: ottimi come micro-percussioni."},
    {"id": "kenney-digital", "provider": "kenney", "title": "Digital Audio", "count": None, "license": "cc0",
     "instruments": ["synth", "riser"], "url": "https://kenney.nl/assets/digital-audio",
     "description": "Suoni sintetici chiptune, zap e power-up."},
    {"id": "kenney-jingles", "provider": "kenney", "title": "Music Jingles", "count": None, "license": "cc0",
     "instruments": ["synth", "keys"], "url": "https://kenney.nl/assets/music-jingles",
     "description": "Brevi jingle musicali in più stili."},
    {"id": "sonniss-gdc", "provider": "sonniss", "title": "GameAudioGDC Bundle (2015–2024)", "count": None,
     "license": "rf", "instruments": ["impact", "foley", "riser", "noise"],
     "url": "https://sonniss.com/gameaudiogdc",
     "description": "Archivio annuale di effetti sonori professionali, in WAV ad alta risoluzione.",
     "note": "Royalty-free, senza attribuzione; vietati ridistribuzione e addestramento AI/ML."},
    {"id": "99sounds-drums", "provider": "99sounds", "title": "99 Drum Samples I + II", "count": 209,
     "license": "rf", "instruments": ["kick", "snare", "closed_hat", "clap", "perc_other"],
     "url": "https://99sounds.org/drum-samples/",
     "description": "One-shot hip-hop, trap, lo-fi e synthwave in WAV 24 bit.", "note": _NO_REDIST},
    {"id": "99sounds-dub", "provider": "99sounds", "title": "Dub Reggae Sounds", "count": None, "license": "rf",
     "instruments": ["bass", "perc_other", "riser"], "url": "https://99sounds.org/dub-reggae-sounds/",
     "description": "Siren, delay e percussioni dub.", "note": _NO_REDIST},
    {"id": "99sounds-cinematic", "provider": "99sounds", "title": "Cinematic Textures", "count": None,
     "license": "rf", "instruments": ["pad", "noise"], "url": "https://99sounds.org/cinematic-textures/",
     "description": "Atmosfere e texture per colonne sonore.", "note": _NO_REDIST},
    {"id": "sampleradar-hub", "provider": "sampleradar", "title": "SampleRadar: tutti i pack", "count": None,
     "license": "rf", "instruments": ["kick", "snare", "bass", "synth", "vocal"],
     "url": "https://www.musicradar.com/news/tech/free-music-samples-download-loops-hits-and-multis-627820",
     "description": "Indice alfabetico di centinaia di pack per genere: hip-hop, techno, breakbeat, synth classici…",
     "note": _NO_REDIST},
]


def logo(provider_id: str) -> str | None:
    """Path of the provider logo relative to the UI root, if bundled."""
    for ext in ("svg", "png", "webp"):
        if os.path.exists(os.path.join(LOGO_DIR, f"{provider_id}.{ext}")):
            return f"assets/providers/{provider_id}.{ext}"
    return None


def providers() -> list[dict]:
    return [dict(p, logo=logo(p["id"])) for p in PROVIDERS]


def curated() -> list[dict]:
    return [dict(c) for c in CURATED_PACKS]
