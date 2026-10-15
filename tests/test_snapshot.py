import os

import numpy as np
import pytest
import soundfile as sf

from clustersound import classifier
from clustersound.cache import Cache
from clustersound.library import Library

from . import synth


@pytest.fixture()
def folder(tmp_path):
    rng = np.random.default_rng(3)
    lib = tmp_path / "lib"
    for name, gen in [("Kick", synth.kick), ("Snare", synth.snare), ("HH_Closed", synth.closed_hat),
                      ("Clap", synth.clap)]:
        for i in range(6):
            p = lib / name / f"{name}_{i:02d}.wav"
            p.parent.mkdir(parents=True, exist_ok=True)
            sf.write(p, gen(rng), synth.SR)
    return tmp_path


def scan(tmp_path):
    lib = Library(Cache(tmp_path / "cache.sqlite"))
    lib.scan(str(tmp_path / "lib"))
    assert lib.progress["phase"] == "done"
    return lib


def from_snapshot(lib):
    return lib.progress["message"].endswith("from snapshot")


def test_reopen_uses_snapshot(folder, monkeypatch):
    first = scan(folder)
    assert not from_snapshot(first)
    monkeypatch.setattr(classifier, "train_head", None)  # the snapshot path must not retrain
    second = scan(folder)
    assert from_snapshot(second)
    key = lambda it: (it["path"], it["cls"], it["conf"], it["sub"], it["feats"].get("type"))
    assert [key(i) for i in second.items] == [key(i) for i in first.items]
    assert np.allclose(second.xyz, first.xyz)
    assert np.allclose(second.emb, first.emb, atol=1e-2)
    assert second.X.shape == first.X.shape
    # still usable: relabel retrains with the snapshot's scores
    monkeypatch.undo()
    second.relabel(0, "crash")
    assert second.items[0]["cls"] == "crash"


def test_changed_file_invalidates(folder):
    scan(folder)
    f = next((folder / "lib" / "Kick").iterdir())
    st = f.stat()
    os.utime(f, (st.st_atime, st.st_mtime + 10))
    assert not from_snapshot(scan(folder))
    assert from_snapshot(scan(folder))


def test_added_and_removed_files_invalidate(folder):
    scan(folder)
    extra = folder / "lib" / "Kick" / "Kick_new.wav"
    sf.write(extra, synth.kick(np.random.default_rng(9)), synth.SR)
    lib = scan(folder)
    assert not from_snapshot(lib) and any(it["path"] == str(extra) for it in lib.items)
    extra.unlink()
    assert not from_snapshot(scan(folder))


def test_relabel_updates_snapshot(folder):
    lib = scan(folder)
    target = lib.items[0]["path"]
    lib.relabel(0, "crash")
    again = scan(folder)
    assert from_snapshot(again)
    it = next(i for i in again.items if i["path"] == target)
    assert it["cls"] == "crash" and it["user"]
    # a label changed behind the snapshot's back (e.g. by another folder view) invalidates it
    again.cache.set_label(target, None)
    assert not from_snapshot(scan(folder))


def test_snapshot_only_restore(folder):
    lib = Library(Cache(folder / "cache.sqlite"))
    lib.scan(str(folder / "lib"), snapshot_only=True)
    assert lib.progress["phase"] == "stale" and not lib.items  # nothing analysed yet
    scan(folder)
    lib = Library(Cache(folder / "cache.sqlite"))
    lib.scan(str(folder / "lib"), snapshot_only=True)
    assert from_snapshot(lib) and lib.items and lib.xyz.shape == (len(lib.items), 3)


# ---------------------------------------------------------------- several folders
@pytest.fixture()
def two_folders(folder):
    rng = np.random.default_rng(5)
    other = folder / "more"
    for i in range(6):
        p = other / "Snares" / f"Snare_{i:02d}.wav"
        p.parent.mkdir(parents=True, exist_ok=True)
        sf.write(p, synth.snare(rng), synth.SR)
    return folder, [str(folder / "lib"), str(other)]


def test_union_of_folders(two_folders, monkeypatch):
    tmp, roots = two_folders
    lib = Library(Cache(tmp / "cache.sqlite"))
    lib.scan(roots)
    assert lib.progress["phase"] == "done" and lib.roots == sorted(roots)
    assert len(lib.items) == 24 + 6
    assert {it["rel"].split("/")[0] for it in lib.items} == {"lib", "more"}
    assert lib.xyz.shape == (30, 3)
    # same selection again: from the snapshot of the union
    monkeypatch.setattr(classifier, "train_head", None)
    again = Library(Cache(tmp / "cache.sqlite"))
    again.scan(list(reversed(roots)))
    assert from_snapshot(again) and len(again.items) == 30


def test_deselect_reads_the_cache(two_folders, monkeypatch):
    from clustersound import library
    tmp, roots = two_folders
    lib = Library(Cache(tmp / "cache.sqlite"))
    lib.scan(roots)

    def boom(path):
        raise AssertionError(f"re-analysed {path}")
    monkeypatch.setattr(library, "analyse_file", boom)
    lib.scan(roots[1:])  # only the second folder: never scanned alone, every file is in the cache
    assert lib.progress["phase"] == "done" and len(lib.items) == 6 and not lib.errors
    assert all(not it["rel"].startswith("more/") for it in lib.items)  # one folder: plain relative paths


def test_nested_and_missing_roots(folder):
    from clustersound.library import normalize_roots
    lib = str(folder / "lib")
    assert normalize_roots([lib, lib + "/Kick", str(folder / "nope"), lib]) == [lib]
    assert normalize_roots(lib) == [lib]


def test_empty_selection_clears(folder):
    lib = scan(folder)
    v = lib.version
    lib.scan([])
    assert not lib.items and lib.roots == [] and lib.xyz.shape == (0, 3) and lib.version > v
