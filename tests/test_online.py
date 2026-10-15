import json
import os
from pathlib import Path

import pytest

from clustersound.online import archive, catalog, ccmixter, downloads, freesound, openverse
from clustersound.online import instruments as inst
from clustersound.online import search as S
from clustersound.online.base import OnlineResult, SourceError, normalize_license

FIX = Path(__file__).parent / "fixtures" / "online"


def load(name):
    return json.loads((FIX / name).read_text())


# ---------------------------------------------------------------- licences
@pytest.mark.parametrize("text,expected", [
    ("http://creativecommons.org/publicdomain/zero/1.0/", "cc0"),
    ("Creative Commons 0", "cc0"),
    ("https://creativecommons.org/publicdomain/mark/1.0/", "pd"),
    ("https://creativecommons.org/licenses/by/4.0/", "by"),
    ("Attribution", "by"),
    ("Attribution NonCommercial", "by-nc"),
    ("Attribution Noncommercial (4.0)", "by-nc"),
    ("https://creativecommons.org/licenses/by-nc-sa/3.0/", "by-nc-sa"),
    ("https://creativecommons.org/licenses/by-nd/4.0/", "by-nd"),
    ("http://creativecommons.org/licenses/sampling+/1.0/", "sampling+"),
    (None, "unknown"),
    ("all rights reserved", "unknown"),
])
def test_normalize_license(text, expected):
    assert normalize_license(text) == expected


def test_commercial_flag():
    r = OnlineResult(uid="x", source="s", source_label="S", title="t")
    for lic, ok in [("cc0", True), ("by", True), ("by-sa", True), ("by-nc", False), ("by-nd", False),
                    ("unknown", False)]:
        r.license = lic
        assert r.commercial_ok is ok, lic


# ---------------------------------------------------------------- instruments
def test_instrument_terms_per_source():
    fs = freesound.build_params({"instruments": ["closed_hat"]}, 1)["filter"]
    assert "hihat" in fs and "hi-hat" in fs and "closed" in fs
    assert "snare" not in " ".join(inst.query_terms(["sub808"]))
    ov = openverse.build_params({"instruments": ["open_hat"]}, 1, "open_hat")["q"]
    assert ov == "open hihat"
    ia = archive.build_params({"instruments": ["kick"]}, 1)["q"]
    assert '"bass drum"' in ia and "licenseurl:*" in ia and "midi" in ia
    cc = ccmixter.build_params({"instruments": ["kick", "snare"]}, 2)
    assert cc["type"] == "any" and "kick" in cc["tags"] and "snare" in cc["tags"] and cc["offset"] == 30


@pytest.mark.parametrize("title,tags,path,expected", [
    ("soccer kick 02.wav", ["ball", "football", "kick", "soccer"], "", None),
    ("808 Snare", [], "", "snare"),
    ("hihat closed.aif", [], "", "closed_hat"),
    ("open hihat 2", [], "", "open_hat"),
    ("Ganon Kick Bass Drum", ["drum"], "", "kick"),
    ("BrRidC.wav", [], "DR660 Samples/Cymbal/BrRidC.wav", "cymbal_other"),
    ("K1.wav", [], "Pack/Kicks/K1.wav", "kick"),
    ("Some sound", ["hi-hat", "drum"], "", "closed_hat"),
])
def test_infer_instrument(title, tags, path, expected):
    assert inst.infer(title, tags, path) == expected


@pytest.mark.parametrize("title,tags,path,expected", [
    # tag order (Freesound sorts tags alphabetically) must not decide the class
    ("Some sound", ["bass", "kick"], "", ("kick", "weak")),
    ("Some sound", ["kick", "bass"], "", ("kick", "weak")),
    ("Kick 01", [], "", ("kick", "sure")),
    ("Deep house bass", ["bass", "house", "synth"], "", ("bass", "sure")),
    ("K1.wav", [], "Pack/Kicks/K1.wav", ("kick", "sure")),
    # several instruments together
    ("Trap drum loop", ["808", "hihat", "kick", "snare", "trap"], "", (None, "mix")),
    ("TR-909 Drum Kit", [], "", (None, "mix")),
    ("808 Drum Kit", [], "", (None, "mix")),
    ("01 - hip hop drum beat", ["drums", "hip_hop", "beat", "beats", "snare"], "", (None, "mix")),
    ("Kick loop 120bpm", ["kick", "loop"], "", ("kick", "sure")),
    ("Express Yourself", ["arp", "bass", "beat", "clap", "cymbals", "dance"], "", (None, "mix")),
    # non-musical context in the title, not only in the tags
    ("Car crash", [], "", (None, None)),
    ("Football kick", [], "", (None, None)),
    # only ambiguous words
    ("Square wave beep", [], "", ("synth", "weak")),
    ("Metal clang", [], "", ("foley", "weak")),
    # phrases
    ("Down sweep", [], "", ("downlifter", "sure")),
    ("Sub drop", [], "", ("downlifter", "sure")),
])
def test_infer_label(title, tags, path, expected):
    assert inst.infer_label(title, tags, path) == expected


def test_infer_is_deterministic():
    """Ties between classes must not depend on PYTHONHASHSEED (it changed results between runs)."""
    import subprocess
    import sys
    code = ("from clustersound.online import instruments as inst;"
            "print(inst.infer('Express Yourself', ['arp', 'bass', 'beat', 'clap', 'cymbals', 'dance']),"
            " inst.infer('SDR-204.wav', ['16bit', 'pcm', 'drumkit', 'drums', 'hertz', 'kick']))")
    root = Path(__file__).parent.parent
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=root,
                           env={**os.environ, "PYTHONHASHSEED": str(seed)}).stdout for seed in (1, 2, 3)}
    assert len(outs) == 1 and outs.pop().split() == ["None", "kick"]


def test_name_metadata():
    assert inst.bpm_from_text("Drum Loop 128bpm") == 128
    assert inst.bpm_from_text("BPM 90 groove") == 90
    assert inst.bpm_from_text("Kick 01") is None
    assert inst.key_from_text("Bass_C#min.wav") == "C# minor"
    assert inst.key_from_text("Pad Am 120") == "A minor"
    assert inst.key_from_text("A Snare hit") is None
    assert inst.infer_type(0.4, "Kick") == "One-shot"
    assert inst.infer_type(8.0, "Drum loop") == "Loop"
    assert inst.infer_type(20.0, "Rain texture") == "Long/Texture"


# ---------------------------------------------------------------- parsers
def test_parse_freesound():
    # shape follows the documented APIv2 search response (no key available to record a real one)
    rs = freesound.parse(load("freesound_kick.json"))
    assert [r.license for r in rs] == ["cc0", "by-nc"]
    assert rs[0].type == "One-shot" and rs[1].type == "Loop"
    assert rs[1].bpm == 128 and rs[1].key == "A minor"
    assert rs[0].preview_url.endswith("-hq.mp3") and rs[0].waveform_img
    assert rs[0].page_url.startswith("https://freesound.org/")


def test_freesound_needs_key():
    with pytest.raises(SourceError, match="API key"):
        freesound.search({}, 1, {})


def test_freesound_filters():
    f = freesound.build_params({"commercial": True, "dur_max": 2, "bpm_min": 120, "key": "C minor",
                                "types": ["One-shot"], "lossless": True, "sort": "downloads"}, 1)
    assert '"Creative Commons 0"' in f["filter"] and "NonCommercial" not in f["filter"]
    assert "duration:[* TO 2]" in f["filter"] and "bpm:[120 TO *]" in f["filter"]
    assert 'tonality:"C minor"' in f["filter"] and "single_event:true" in f["filter"]
    assert "type:(wav OR aiff OR flac)" in f["filter"] and f["sort"] == "downloads_desc"


def test_freesound_packs(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, as_json=True, ttl=None):
        calls.append((url, params))
        return load("freesound_packs_grouped.json")

    monkeypatch.setattr(freesound, "http_get", fake_get)
    cards, total, more = freesound.packs({"q": "kick", "commercial": True, "sort": "downloads"}, 1,
                                         {"freesound_key": "k"})
    assert len(calls) == 1  # names come with the search: no request per pack
    params = calls[0][1]
    assert params["group_by_pack"] == 1 and params["sort"] == "downloads_desc"
    assert params["filter"].endswith(" pack:*") and "license:" in params["filter"]
    assert [c.uid for c in cards] == ["freesound:pack:41", "freesound:pack:77"]  # the loose sound is skipped
    c = cards[0]
    assert c.is_pack and c.title == "808 Kicks Vol. 1" and c.author == "beatsmith"
    assert c.license == "cc0" and c.waveform_img and c.preview_url.endswith("-hq.mp3")
    assert c.extra["matching"] == 8
    assert c.page_url == "https://freesound.org/people/beatsmith/packs/41/"
    whole, _, _ = freesound.packs({}, 1, {"freesound_key": "k"})
    assert calls[-1][1]["filter"] == "pack:*"
    assert whole[0].extra["num_sounds"] == 8 and "matching" not in whole[0].extra  # no query: whole pack
    sound = freesound.parse(load("freesound_packs_grouped.json"))[0]
    assert sound.extra["pack_id"] == "41" and sound.extra["pack_title"] == "808 Kicks Vol. 1"
    with pytest.raises(SourceError, match="API key"):
        freesound.packs({}, 1, {})


def test_parse_openverse():
    rs = openverse.parse(load("openverse_snare.json"))
    assert rs and all(r.uid.startswith("openverse:") for r in rs)
    assert all(r.duration is None or r.duration < 600 for r in rs)  # ms converted to s
    assert rs[0].source_label.startswith("Openverse · ")
    assert all(r.license != "unknown" for r in rs)


def test_parse_ccmixter():
    rs = ccmixter.parse(load("ccmixter_drums.json"))
    assert rs and rs[0].page_url.startswith("https://ccmixter.org/")
    assert all("mp3" not in r.tags and "44k" not in r.tags for r in rs)
    assert any(r.bpm for r in rs)
    assert all(r.preview_url is None or r.preview_url.endswith(".mp3") for r in rs)


def test_parse_archive_and_suspects():
    rs = archive.parse(load("archive_search.json"))
    assert rs and all(r.is_pack for r in rs)
    by_id = {r.extra["identifier"]: r for r in rs}
    assert by_id["titanium-rhythms-2"].suspect  # Big Fish Audio library
    assert by_id["sony-pictures-sound-effects-library-volume-1-10"].suspect
    assert not by_id["DR660Samples"].suspect
    assert by_id["DR660Samples"].license == "by"


def test_archive_expand(monkeypatch):
    meta = load("archive_metadata.json")
    listing = (FIX / "archive_zip_listing.html").read_text()

    def fake_get(url, params=None, headers=None, as_json=True, ttl=0):
        return meta if as_json else listing

    monkeypatch.setattr(archive, "http_get", fake_get)
    parent = archive.parse(load("archive_search.json"))
    parent = next(r for r in parent if r.extra["identifier"] == "DR660Samples")
    files, archives = archive.expand(parent)
    assert archives and archives[0]["name"].endswith(".zip") and archives[0]["browsable"]
    assert len(files) == 25 and all(f.preview_url.startswith("https://archive.org/download/") for f in files)
    assert all("__MACOSX" not in f.path for f in files)
    assert files[0].instrument == "cymbal_other"  # from the "Cymbal" folder
    assert files[0].license == parent.license


# ---------------------------------------------------------------- aggregator
def test_search_isolates_failing_source(monkeypatch):
    def ok(p, page, settings):
        return [OnlineResult(uid="ok:1", source="openverse", source_label="Openverse", title="Kick 1.wav",
                             license="cc0", duration=0.5)], 1, False

    def boom(p, page, settings):
        raise SourceError("unreachable")

    monkeypatch.setattr(openverse, "search", ok)
    monkeypatch.setattr(ccmixter, "search", boom)
    res = S.search({"sources": ["openverse", "ccmixter"], "instruments": ["kick"]}, {})
    assert res["openverse"]["results"][0]["instrument"] == "kick"
    assert res["ccmixter"]["error"] == "unreachable" and res["ccmixter"]["results"] == []


def test_client_filters():
    def r(**kw):
        base = dict(uid="u", source="openverse", source_label="O", title="Kick 120bpm Am.wav",
                    license="by", duration=1.0, format="wav")
        return S.enrich(OnlineResult(**{**base, **kw}))

    assert S.passes(r(), {"instruments": ["kick"]})
    assert not S.passes(r(), {"instruments": ["snare"]})
    assert not S.passes(r(license="by-nc"), {"commercial": True})
    assert S.passes(r(license="by-nc"), {"licenses": ["nc"]})
    assert not S.passes(r(duration=5.0), {"dur_max": 2})
    assert S.passes(r(), {"bpm_min": 100, "bpm_max": 130})
    assert not S.passes(r(title="Kick.wav"), {"bpm_min": 100})  # unknown BPM is excluded
    assert S.passes(r(), {"key": "A minor"})
    assert not S.passes(r(format="mp3"), {"lossless": True})
    assert not S.passes(r(suspect=True), {})
    assert S.passes(r(suspect=True), {"include_suspect": True})
    assert not S.passes(r(is_pack=True), {"packs": "files"})


def test_store_pack_page_and_download(monkeypatch):
    def fake_get(url, params=None, headers=None, as_json=True, ttl=None):
        if url.endswith("/sounds/"):
            return dict(load("freesound_kick.json"), next=None)
        if "/users/" in url:
            return {"results": [load("freesound_pack.json"), dict(load("freesound_pack.json"), id=99, name="Other")]}
        if "/packs/" in url:
            return dict(load("freesound_pack.json"), id=int(url.rstrip("/").rsplit("/", 1)[-1]))
        return load("freesound_packs_grouped.json")

    monkeypatch.setattr(freesound, "http_get", fake_get)
    settings = {"freesound_key": "k"}
    res = S.search_source("freesound", {"q": "kick"}, 1, settings, packs=True)
    assert res["error"] is None and [r["uid"] for r in res["results"]] == ["freesound:pack:41", "freesound:pack:77"]
    assert res["results"][0]["info"]["matching"] == 8
    page = S.pack("freesound:pack:41", 1, settings)
    assert page["error"] is None and page["pack"]["title"] == "808 Kicks Vol. 1"
    assert page["pack"]["info"]["matching"] == 8 and page["pack"]["info"]["description"]
    assert len(page["files"]) == 2 and page["files"][0]["info"]["pack_title"] == "808 Kicks Vol. 1"
    assert [o["uid"] for o in page["others"]] == ["freesound:pack:99"]  # the open pack is left out
    files = S.pack_files("freesound:pack:41", settings)
    assert len(files) == 2 and S.get(files[0].uid) is files[0]
    root = "/tmp/dl"
    assert os.path.join("Freesound", "808 Kicks Vol. 1") in downloads.target_path(root, files[0], files[0].download_url)


def test_featured_without_key(monkeypatch):
    monkeypatch.setattr(archive, "search", lambda p, page, s: ([], 0, False))
    monkeypatch.setattr(openverse, "search", lambda p, page, s: ([], 0, False))
    home = S.featured({})
    assert home["freesound_packs"]["needs_key"] and home["archive_packs"]["error"] is None
    assert home["cc0_new"]["source"] == "openverse"


# ---------------------------------------------------------------- catalogue
def test_catalog():
    from clustersound.online.base import LICENSES
    from clustersound.taxonomy import CLASSES
    ids = {p["id"] for p in catalog.PROVIDERS}
    assert {k for k, p in ((p["id"], p) for p in catalog.PROVIDERS) if p["kind"] == "api"} == set(S.SOURCES)
    class_ids = {c.id for c in CLASSES}
    for c in catalog.curated():
        assert c["provider"] in ids and c["url"].startswith("https://")
        assert LICENSES[c["license"]]["commercial"], c["id"]  # the showcase only lists royalty-free packs
        assert set(c["instruments"]) <= class_ids, c["id"]
    for p in catalog.providers():
        assert p["logo"] is None or (Path(catalog.LOGO_DIR).parent.parent / p["logo"]).exists()


# ---------------------------------------------------------------- downloads
def test_download_paths_and_license(tmp_path):
    r = OnlineResult(uid="u", source="archive", source_label="Internet Archive", title="Kick: 01/hard?",
                     author="Me", license="by", license_url="https://creativecommons.org/licenses/by/4.0/",
                     page_url="https://archive.org/details/x", path="Pack/Kicks/Kick 01.wav",
                     extra={"pack_title": "My Pack"})
    p1 = downloads.target_path(str(tmp_path), r, "https://archive.org/download/x/Pack%2FKicks%2FKick%2001.wav")
    assert p1.endswith(os.path.join("Internet Archive", "My Pack", "Me - Kick 01.wav"))
    os.makedirs(os.path.dirname(p1))
    Path(p1).write_bytes(b"x")
    p2 = downloads.target_path(str(tmp_path), r, "https://archive.org/download/x/k.wav")
    assert p2 != p1 and "(2)" in p2
    text = downloads.license_text(r, "https://archive.org/download/x/k.wav")
    assert "CC BY" in text and "Attribution required" in text and "Me" in text
    assert downloads.safe_name('a/b:c*?"d') == "a b c d"


def test_download_hosts():
    assert downloads.host_allowed("https://cdn.freesound.org/previews/1/1-hq.mp3")
    assert downloads.host_allowed("https://ia800401.us.archive.org/x.zip")
    assert downloads.host_allowed("https://upload.wikimedia.org/a.ogg")
    assert not downloads.host_allowed("https://evil.example.com/archive.org/x.zip")
    assert not downloads.host_allowed("https://archive.org.evil.com/x")


# ---------------------------------------------------------------- live (opt-in)
network = pytest.mark.skipif(not os.environ.get("CLUSTERSOUND_NETWORK_TESTS"),
                             reason="set CLUSTERSOUND_NETWORK_TESTS=1 to query the real services")


@network
@pytest.mark.parametrize("source", ["openverse", "archive", "ccmixter"])
def test_live_sources(source):
    res = S.search_source(source, {"instruments": ["kick"]}, 1, {})
    assert res["error"] is None and res["fetched"] > 0


def test_showcase_source(monkeypatch):
    """Store home carousel: only surely labelled results of each category, interleaved across categories."""
    search = S

    def fake(name, p, page, settings, packs=False):
        cid = p["instruments"][0]
        rows = [{"uid": f"{cid}{i}", "author": f"{cid}-a{i}", "instrument": cid, "label_state": "sure"} for i in range(3)]
        rows.insert(0, {"uid": f"{cid}-weak", "author": "x", "instrument": cid, "label_state": "weak"})
        rows.insert(0, {"uid": f"{cid}-other", "author": "y", "instrument": "pad", "label_state": "sure"})
        return {"results": rows, "error": None}

    monkeypatch.setattr(search, "search_source", fake)
    d = search.showcase_source("openverse", {})
    cats = catalog.SHOWCASE_LIMITED["openverse"]
    assert [r["uid"] for r in d["results"]] == [f"{c}0" for c in cats] + [f"{c}1" for c in cats]
    assert search.showcase_source("freesound", {})["needs_key"]
