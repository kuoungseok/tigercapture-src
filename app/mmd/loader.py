"""Shared MMD model loading entry point."""
from __future__ import annotations

from pathlib import Path

from .aplaybox_pbx import load_aplaybox_pbx_json
from .pmd import load_pmd
from .pmx import MMDModel, PMXParseError, load_pmx


def load_mmd_model(path: str | Path) -> MMDModel:
    model_path = Path(path)
    if model_path.name.casefold().endswith(".pbx.json"):
        return load_aplaybox_pbx_json(model_path)
    suffix = model_path.suffix.casefold()
    if suffix == ".pmx":
        return load_pmx(model_path)
    if suffix == ".pmd":
        return load_pmd(model_path)
    raise PMXParseError(f"Unsupported MMD model extension: {model_path.suffix or '<none>'}")
