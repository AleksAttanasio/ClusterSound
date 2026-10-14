"""Store catalogue: the providers (searchable through an API or curated) and the curated free packs.

Curated packs come from sites without a public API: the store shows them as cards and opens the
official page to download (no scraping). Only royalty-free sources usable in commercial music.
"""
import os

from ..i18n import N_

LOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "assets", "providers")

# kind: "api" = searched live by the store; "curated" = static showcase linking to the official page
PROVIDERS = [
    {"id": "freesound", "name": "Freesound", "kind": "api", "url": "https://freesound.org",
     "color": "#e04a3f", "licenses": ["cc0", "by", "nc"],
     "description": N_("Over 600,000 sounds uploaded by the community, organised in packs. Needs a free API key.")},
    {"id": "openverse", "name": "Openverse", "kind": "api", "url": "https://openverse.org",
     "color": "#ffe033", "licenses": ["cc0", "by", "by-sa"],
     "description": N_("WordPress search engine for openly licensed works: indexes Freesound and Wikimedia Commons.")},
    {"id": "archive", "name": "Internet Archive", "kind": "api", "url": "https://archive.org",
     "color": "#cfcfcf", "licenses": ["cc0", "pd", "by"],
     "description": N_("Non-profit digital library: whole sample packs and drum kits, browsable file by file.")},
    {"id": "ccmixter", "name": "ccMixter", "kind": "api", "url": "https://ccmixter.org",
     "color": "#7fb3d5", "licenses": ["cc0", "by", "nc"],
     "description": N_("Remix community: samples, stems and a cappellas under Creative Commons licences.")},
    {"id": "kenney", "name": "Kenney", "kind": "curated", "url": "https://kenney.nl/assets/category:Audio",
     "color": "#f5a623", "licenses": ["cc0"],
     "description": N_("CC0 (public domain) audio packs made for games: impacts, UI, sci-fi, foley.")},
    {"id": "sonniss", "name": "Sonniss", "kind": "curated", "url": "https://sonniss.com/gameaudiogdc",
     "color": "#d0021b", "licenses": ["rf"],
     "description": N_("GameAudioGDC: every year tens of GB of professional royalty-free effects, no attribution.")},
    {"id": "99sounds", "name": "99Sounds", "kind": "curated", "url": "https://99sounds.org",
     "color": "#2ecc71", "licenses": ["rf"],
     "description": N_("Free sample packs curated by sound designers: drums, cinematic textures, dub.")},
    {"id": "sampleradar", "name": "SampleRadar", "kind": "curated",
     "url": "https://www.musicradar.com/news/tech/free-music-samples-download-loops-hits-and-multis-627820",
     "color": "#e2001a", "licenses": ["rf"],
     "description": N_("Tens of thousands of loops and one-shots from Computer Music and Future Music, royalty-free.")},
]

_NO_REDIST = N_("Royalty-free, commercial use included; redistributing the files as they are is not allowed.")

# instruments: class ids of clustersound.taxonomy (used for the store's category tiles)
CURATED_PACKS = [
    {"id": "kenney-impact", "provider": "kenney", "title": "Impact Sounds", "count": 130, "license": "cc0",
     "instruments": ["impact", "foley"], "url": "https://kenney.nl/assets/impact-sounds",
     "description": N_("Hits, footsteps and impacts on different materials.")},
    {"id": "kenney-scifi", "provider": "kenney", "title": "Sci-fi Sounds", "count": None, "license": "cc0",
     "instruments": ["riser", "noise"], "url": "https://kenney.nl/assets/sci-fi-sounds",
     "description": N_("Sci-fi lasers, engines, computers and sweeps.")},
    {"id": "kenney-interface", "provider": "kenney", "title": "Interface Sounds", "count": None, "license": "cc0",
     "instruments": ["perc_other"], "url": "https://kenney.nl/assets/interface-sounds",
     "description": N_("Clicks, beeps and confirmations: great as micro-percussion.")},
    {"id": "kenney-digital", "provider": "kenney", "title": "Digital Audio", "count": None, "license": "cc0",
     "instruments": ["synth", "riser"], "url": "https://kenney.nl/assets/digital-audio",
     "description": N_("Chiptune synth sounds, zaps and power-ups.")},
    {"id": "kenney-jingles", "provider": "kenney", "title": "Music Jingles", "count": None, "license": "cc0",
     "instruments": ["synth", "keys"], "url": "https://kenney.nl/assets/music-jingles",
     "description": N_("Short musical jingles in several styles.")},
    {"id": "sonniss-gdc", "provider": "sonniss", "title": "GameAudioGDC Bundle (2015–2024)", "count": None,
     "license": "rf", "instruments": ["impact", "foley", "riser", "noise"],
     "url": "https://sonniss.com/gameaudiogdc",
     "description": N_("Yearly archive of professional sound effects, in high-resolution WAV."),
     "note": N_("Royalty-free, no attribution; redistribution and AI/ML training are not allowed.")},
    {"id": "99sounds-drums", "provider": "99sounds", "title": "99 Drum Samples I + II", "count": 209,
     "license": "rf", "instruments": ["kick", "snare", "closed_hat", "clap", "perc_other"],
     "url": "https://99sounds.org/drum-samples/",
     "description": N_("Hip-hop, trap, lo-fi and synthwave one-shots in 24-bit WAV."), "note": _NO_REDIST},
    {"id": "99sounds-dub", "provider": "99sounds", "title": "Dub Reggae Sounds", "count": None, "license": "rf",
     "instruments": ["bass", "perc_other", "riser"], "url": "https://99sounds.org/dub-reggae-sounds/",
     "description": N_("Dub sirens, delays and percussion."), "note": _NO_REDIST},
    {"id": "99sounds-cinematic", "provider": "99sounds", "title": "Cinematic Textures", "count": None,
     "license": "rf", "instruments": ["pad", "noise"], "url": "https://99sounds.org/cinematic-textures/",
     "description": N_("Atmospheres and textures for soundtracks."), "note": _NO_REDIST},
    {"id": "sampleradar-hub", "provider": "sampleradar", "title": N_("SampleRadar: all packs"), "count": None,
     "license": "rf", "instruments": ["kick", "snare", "bass", "synth", "vocal"],
     "url": "https://www.musicradar.com/news/tech/free-music-samples-download-loops-hits-and-multis-627820",
     "description": N_("Alphabetical index of hundreds of packs by genre: hip-hop, techno, breakbeat, classic synths…"),
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
