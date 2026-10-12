"""The enhancement models: what they need, where their weights live, and the one-time download.

Nothing here imports torch: status() only looks for the packages, so the app can tell the user what to install.
"""
import importlib.util
import os
from dataclasses import dataclass

from ..paths import data_dir

INSTALL_HINT = 'pip install -e ".[enhance]"'


@dataclass(frozen=True)
class Model:
    key: str
    label: str        # menu entry
    detail: str       # one line on what it does
    repo: str         # Hugging Face repo with the weights
    filename: str
    sr: int           # the rate the model works at
    mb: int           # download size
    ram: str          # rough peak memory of the worker, for the menu
    speed: str        # rough time for a 30 s sample on Apple Silicon
    license: str
    modules: tuple[str, ...] = ("torch",)


MODELS = {m.key: m for m in [
    Model("apollo", "Apollo · veloce",
          "Ripara l'audio compresso (MP3, streaming) e ricostruisce le alte frequenze tagliate. Pensato per la musica.",
          "JusperLee/Apollo", "pytorch_model.bin", 44100, 66, "~1–2 GB", "da pochi secondi a ~1 minuto",
          "CC BY-SA 4.0"),
]}
DEFAULT = "apollo"


def model_dir(key: str) -> str:
    return os.path.join(str(data_dir()), "models", key)


def weights_path(key: str) -> str:
    return os.path.join(model_dir(key), MODELS[key].filename)


def _marker(key: str) -> str:
    return os.path.join(model_dir(key), ".ready")


def get(key: str | None) -> Model:
    m = MODELS.get(key or DEFAULT)
    if not m:
        raise ValueError(f"modello sconosciuto: {key}")
    return m


def installed(key: str = DEFAULT) -> bool:
    return all(importlib.util.find_spec(mod) is not None for mod in get(key).modules)


def ready(key: str) -> bool:
    return os.path.isfile(_marker(key)) and os.path.isfile(weights_path(key))


def status() -> dict:
    return {"install_hint": INSTALL_HINT, "default": DEFAULT, "models": [
        {"key": m.key, "label": m.label, "detail": m.detail, "mb": m.mb, "ram": m.ram, "speed": m.speed,
         "license": m.license, "sr": m.sr, "installed": installed(m.key), "model_ready": installed(m.key) and ready(m.key)}
        for m in MODELS.values()]}


def download_model(key: str) -> None:
    """The only step that uses the network: fetches the weights into model_dir (once)."""
    from huggingface_hub import hf_hub_download
    m = get(key)
    os.makedirs(model_dir(key), exist_ok=True)
    hf_hub_download(m.repo, m.filename, local_dir=model_dir(key))
    if not os.path.isfile(weights_path(key)):
        raise RuntimeError("pesi non trovati dopo il download")
    with open(_marker(key), "w") as f:
        f.write(f"{m.repo}/{m.filename}\n")
