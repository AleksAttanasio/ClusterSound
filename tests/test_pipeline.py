import os

import numpy as np
import pytest
import soundfile as sf
import soxr

from clustersound import classifier, dynamics, features, projection, taxonomy
from clustersound.cache import Cache
from clustersound.library import Library

from . import synth

SR = synth.SR


def feats_of(x):
    xf = soxr.resample(x, SR, features.FEAT_SR).astype(np.float32)
    return features.compute(xf, features.FEAT_SR)


# ---------------------------------------------------------------- taxonomy
@pytest.mark.parametrize("name,expected", [
    ("Kick_01.wav", "kick"),
    ("TR808_KickHard01.wav", "kick"),
    ("OpenHat_03.wav", "open_hat"),
    ("HH 01.wav", "closed_hat"),
    ("Closed Hihat 4.aif", "closed_hat"),
    ("808 Snare.wav", "snare"),
    ("808_Bass_C.wav", "sub808"),
    ("SD_Rim.wav", "rimshot"),
    ("CYM_Crash_02.aif", "crash"),
    ("perc_shaker_120bpm.wav", "shaker"),
    ("Vocal Chop Am.wav", "vocal"),
    ("Riser FX 2.wav", "riser"),
])
def test_keywords(name, expected):
    sc = taxonomy.keyword_scores(taxonomy.tokenize(name))
    assert max(sc, key=sc.get) == expected


def test_loop_names():
    assert taxonomy.is_loop_name(taxonomy.tokenize("drum loop 120bpm.wav"))
    assert taxonomy.is_loop_name(taxonomy.tokenize("Top_Loop_02.wav"))
    assert not taxonomy.is_loop_name(taxonomy.tokenize("Kick_01.wav"))


def test_folder_names_are_weaker_than_file_names():
    sc, _ = classifier.name_scores("Kicks/Snare_01.wav")
    assert max(sc, key=sc.get) == "snare"
    sc, _ = classifier.name_scores("Drums/Kicks/sample_01.wav")
    assert max(sc, key=sc.get) == "kick" and sc["kick"] < 1.0


def test_class_colors_unique_and_readable():
    colors = [c["color"] for c in taxonomy.ui_classes()]
    assert len(set(colors)) == len(colors)

    def lum(h):
        r, g, b = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

    bg = lum("#0f1115")
    for c in taxonomy.ui_classes():
        assert (lum(c["color"]) + 0.05) / (bg + 0.05) >= 4, c["id"]


# ---------------------------------------------------------------- features
def test_types():
    rng = np.random.default_rng(0)
    assert feats_of(synth.kick(rng))["type"] == "One-shot"
    assert feats_of(synth.closed_hat(rng))["type"] == "One-shot"
    assert feats_of(synth.pad(rng))["type"] == "Long/Texture"
    assert feats_of(synth.drum_loop(rng))["type"] == "Loop"


def test_sustained_sounds_have_one_onset():
    rng = np.random.default_rng(1)
    for g in (synth.pad, synth.sub808, synth.open_hat):
        assert feats_of(g(rng))["onset_count"] <= 2


def test_acoustic_rules_separate_basic_drums():
    rng = np.random.default_rng(2)
    for name in ("kick", "sub808", "closed_hat", "open_hat"):
        r = features.rule_logits(feats_of(synth.GENERATORS[name](rng)))
        assert taxonomy.CLASS_IDS[int(np.argmax(r))] == name, name


def test_hats_decay_differs():
    rng = np.random.default_rng(3)
    assert feats_of(synth.closed_hat(rng))["decay20"] < 0.1 < feats_of(synth.open_hat(rng))["decay20"]


# ---------------------------------------------------------------- dynamics
def test_adsr_on_synthetic_envelope():
    dt = 0.005
    t = np.arange(0, 2.0, dt)
    lin = np.interp(t, [0, 0.1, 0.3, 1.5, 1.8, 2.0], [0.001, 1, 0.5, 0.5, 0.001, 0.0001])
    a = dynamics.adsr(20 * np.log10(lin), dt)
    assert 0.05 <= a["attack_end"] - a["attack_start"] <= 0.11
    assert abs(a["sustain_db"] - 20 * np.log10(0.5)) < 1.0
    assert 0.2 <= a["decay_end"] <= 0.35
    assert 1.4 <= a["release_start"] <= 1.6


def test_details_from_file(tmp_path):
    p = tmp_path / "kick.wav"
    sf.write(p, synth.kick(np.random.default_rng(0)), SR)
    d = dynamics.details(str(p))
    assert d["peak_dbfs"] <= 0.01
    assert len(d["wave_min"]) == len(d["wave_max"]) > 100
    assert d["adsr"]["attack_ms"] < 20
    assert len(d["mel"][0]) == 64


# ---------------------------------------------------------------- projection
def test_tsne_keeps_separate_clusters_apart():
    rng = np.random.default_rng(0)
    centers = rng.normal(0, 10, (4, 20))
    X = np.vstack([c + rng.normal(0, 0.5, (40, 20)) for c in centers]).astype(np.float32)
    y = np.repeat(np.arange(4), 40)
    Y = projection.layout(X)
    assert Y.shape == (160, 3)
    # nearest neighbour of every point belongs to its own cluster
    d = ((Y[:, None] - Y[None]) ** 2).sum(-1)
    np.fill_diagonal(d, np.inf)
    assert (y[d.argmin(1)] == y).mean() > 0.97


# ---------------------------------------------------------------- head
def test_head_learns_and_saves(tmp_path):
    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(m, 1, (60, 8)) for m in (0, 4, 8)]).astype(np.float32)
    y = np.repeat([0, 3, 7], 60)
    head = classifier.train_head(X, y, np.ones(len(y), np.float32), steps=400)
    pred = np.array(head.classes)[head.proba(X).argmax(1)]
    assert (pred == y).mean() > 0.95
    head.save(str(tmp_path / "h.npz"))
    h2 = classifier.Head.load(str(tmp_path / "h.npz"))
    assert np.allclose(h2.proba(X), head.proba(X), atol=1e-2)


# ---------------------------------------------------------------- end to end
@pytest.fixture()
def library(tmp_path):
    rng = np.random.default_rng(7)
    names = {"kick": "Kick", "sub808": "808", "snare": "Snare", "closed_hat": "HH_Closed",
             "open_hat": "OpenHat", "clap": "Clap", "pad": "Pad", "riser": "Riser"}
    truth = {}
    for cls, gen in synth.GENERATORS.items():
        for i in range(8):
            if i < 5:
                p = tmp_path / "lib" / "Pack" / f"{names[cls]}s" / f"{names[cls]}_{i:02d}.wav"
            else:
                p = tmp_path / "lib" / "Unnamed" / f"smp_{cls}_{i}.wav".replace(cls, f"x{abs(hash(cls)) % 997}")
            p.parent.mkdir(parents=True, exist_ok=True)
            sf.write(p, gen(rng), SR)
            truth[str(p)] = cls
    (tmp_path / "lib" / "notes.txt").write_text("not audio")
    (tmp_path / "lib" / "._Kick_00.wav").write_bytes(b"\0" * 10)  # AppleDouble junk
    return tmp_path, truth


def test_end_to_end(library):
    tmp_path, truth = library
    lib = Library(Cache(tmp_path / "cache.sqlite"))
    lib.scan(str(tmp_path / "lib"))
    assert len(lib.items) == len(truth) and not lib.errors
    assert lib.progress["phase"] == "done"
    acc = np.mean([truth[it["path"]] == it["cls"] for it in lib.items])
    assert acc >= 0.85, acc
    assert lib.xyz.shape == (len(truth), 3)
    assert all("sub" in it for it in lib.items)

    # second scan comes from the cache, user labels win and survive
    target = lib.items[0]
    lib.relabel(target["id"], "crash")
    lib2 = Library(Cache(tmp_path / "cache.sqlite"))
    lib2.scan_analysis_only(str(tmp_path / "lib"))
    lib2.reclassify()
    it2 = next(i for i in lib2.items if i["path"] == target["path"])
    assert it2["cls"] == "crash" and it2["user"]


def test_export(library, tmp_path):
    from clustersound import export
    tmp, _ = library
    lib = Library(Cache(tmp / "cache.sqlite"))
    lib.scan_analysis_only(str(tmp / "lib"))
    lib.reclassify()
    out = tmp_path / "r.csv"
    export.write(lib.items, str(out))
    lines = out.read_text().splitlines()
    assert lines[0].startswith("path,rel,class") and len(lines) == len(lib.items) + 1
    export.write(lib.items, str(tmp_path / "r.json"))
    assert os.path.getsize(tmp_path / "r.json") > 100
