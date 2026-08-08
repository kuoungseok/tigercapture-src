"""Optional Marigold IID lighting backend for Texture Lab.

The heavy Diffusers stack and model checkpoint are deliberately lazy-loaded.
Normal editor startup and the fast heuristic de-light path must not import or
download AI dependencies.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np
from PIL import Image


MARIGOLD_IID_CHECKPOINT = "prs-eth/marigold-iid-lighting-v1-1"
MARIGOLD_IID_LOCAL_DIR = (
    Path(__file__).resolve().parents[2]
    / "external"
    / "models"
    / "marigold-iid-lighting-v1-1"
)
MARIGOLD_IID_DEPENDENCIES: tuple[str, ...] = (
    "diffusers>=0.33.0,<1",
    "transformers>=4.41,<6",
    "accelerate>=0.30,<2",
    "safetensors>=0.4,<1",
    "huggingface_hub>=0.25,<2",
)


class MarigoldIidUnavailableError(RuntimeError):
    """Raised when the explicitly requested Marigold IID backend is unavailable."""


_PIPELINE_CACHE: dict[tuple[str, str, str], Any] = {}


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _display_command(program: str, args: list[str]) -> str:
    def quote(value: str) -> str:
        if not value or any(char.isspace() for char in value):
            return '"' + value.replace('"', '\\"') + '"'
        return value

    return " ".join(quote(part) for part in [program, *args])


def marigold_iid_install_plan(python_executable: str | None = None) -> dict[str, Any]:
    """Return an explicit, durable dependency/checkpoint installation contract."""
    program = str(python_executable or sys.executable or ".\\.venv\\Scripts\\python.exe")
    model_dir = MARIGOLD_IID_LOCAL_DIR
    dependency_args = ["-m", "pip", "install", *MARIGOLD_IID_DEPENDENCIES]
    download_script = (
        "from huggingface_hub import snapshot_download; "
        f"snapshot_download(repo_id={MARIGOLD_IID_CHECKPOINT!r}, "
        f"local_dir={str(model_dir)!r}, "
        "allow_patterns=['*.json','*.txt','*.model','*.fp16.safetensors','*.md'])"
    )
    download_args = ["-c", download_script]
    verify_script = (
        "import json, pathlib, torch, diffusers; "
        f"p=pathlib.Path({str(model_dir)!r}); "
        "ok=hasattr(diffusers, 'MarigoldIntrinsicsPipeline') and "
        "(p/'model_index.json').is_file() and torch.cuda.is_available(); "
        "print(json.dumps({'ok':bool(ok),'diffusers':diffusers.__version__,"
        "'cuda_available':bool(torch.cuda.is_available()),'checkpoint':str(p)}, ensure_ascii=False)); "
        "raise SystemExit(0 if ok else 3)"
    )
    verify_args = ["-c", verify_script]
    return {
        "schema_id": "tigerstudio.ar_pbr.marigold_iid.install_plan.v1",
        "backend": "marigold_iid_lighting",
        "checkpoint_id": MARIGOLD_IID_CHECKPOINT,
        "checkpoint_dir": str(model_dir),
        "download_variant": "fp16_safetensors_only",
        "estimated_checkpoint_download": "approximately 2.6 GB; excludes fp32 and pickle .bin duplicates",
        "license": "OpenRAIL++ model license; Diffusers/Marigold code uses its own package licenses",
        "dependency_program": program,
        "dependency_args": dependency_args,
        "dependency_command": _display_command(program, dependency_args),
        "download_program": program,
        "download_args": download_args,
        "download_command": _display_command(program, download_args),
        "verify_program": program,
        "verify_args": verify_args,
        "verify_command": _display_command(program, verify_args),
    }


def marigold_iid_status() -> dict[str, Any]:
    """Probe availability without importing Diffusers or touching the network."""
    dependencies = {
        name: _module_available(name)
        for name in ("torch", "diffusers", "transformers", "accelerate", "safetensors", "huggingface_hub")
    }
    cuda_available = False
    device = ""
    if dependencies["torch"]:
        try:
            import torch  # type: ignore

            cuda_available = bool(torch.cuda.is_available())
            if cuda_available:
                device = str(torch.cuda.get_device_name(0))
        except Exception as exc:
            device = f"torch probe failed: {type(exc).__name__}"
    checkpoint_ready = (MARIGOLD_IID_LOCAL_DIR / "model_index.json").is_file()
    pipeline_api = False
    if dependencies["diffusers"]:
        try:
            import diffusers  # type: ignore

            pipeline_api = hasattr(diffusers, "MarigoldIntrinsicsPipeline")
        except Exception:
            pipeline_api = False
    ready = bool(all(dependencies.values()) and cuda_available and checkpoint_ready and pipeline_api)
    if ready:
        reason = "ready"
    elif not all(dependencies.values()):
        reason = "python_dependencies_missing"
    elif not pipeline_api:
        reason = "diffusers_marigold_intrinsics_api_missing"
    elif not cuda_available:
        reason = "cuda_unavailable"
    else:
        reason = "checkpoint_missing"
    return {
        "schema_id": "tigerstudio.ar_pbr.marigold_iid.status.v1",
        "available": ready,
        "reason": reason,
        "device": device,
        "cuda_available": cuda_available,
        "dependencies": dependencies,
        "pipeline_api": pipeline_api,
        "checkpoint_id": MARIGOLD_IID_CHECKPOINT,
        "checkpoint_dir": str(MARIGOLD_IID_LOCAL_DIR),
        "checkpoint_ready": checkpoint_ready,
        "install_plan": marigold_iid_install_plan(),
    }


def _pipeline(checkpoint: str, *, allow_download: bool) -> tuple[Any, Any, str]:
    try:
        import torch  # type: ignore
        import diffusers  # type: ignore
    except Exception as exc:
        raise MarigoldIidUnavailableError(
            "Marigold IID dependencies are missing. Use the Texture Lab AI Setup action/button."
        ) from exc
    if not hasattr(diffusers, "MarigoldIntrinsicsPipeline"):
        raise MarigoldIidUnavailableError(
            "Installed Diffusers does not provide MarigoldIntrinsicsPipeline; upgrade the AI IID dependencies."
        )
    if not torch.cuda.is_available():
        raise MarigoldIidUnavailableError("Marigold IID High Quality mode requires a CUDA GPU.")

    local = Path(checkpoint).expanduser()
    source = str(local) if local.is_dir() else str(checkpoint)
    if checkpoint == MARIGOLD_IID_CHECKPOINT and MARIGOLD_IID_LOCAL_DIR.is_dir():
        source = str(MARIGOLD_IID_LOCAL_DIR)
    dtype = torch.float16
    key = (source, "cuda", "float16")
    cached = _PIPELINE_CACHE.get(key)
    if cached is not None:
        return cached, torch, source
    try:
        pipe = diffusers.MarigoldIntrinsicsPipeline.from_pretrained(
            source,
            variant="fp16",
            torch_dtype=dtype,
            local_files_only=not bool(allow_download),
        ).to("cuda")
    except Exception as exc:
        raise MarigoldIidUnavailableError(
            "Marigold IID checkpoint is not available locally. Use AI Setup to download the official checkpoint."
        ) from exc
    pipe.set_progress_bar_config(disable=True)
    _PIPELINE_CACHE[key] = pipe
    return pipe, torch, source


def _pil_to_float_rgb(image: Image.Image, size: tuple[int, int]) -> np.ndarray:
    rgb = image.convert("RGB")
    if rgb.size != size:
        rgb = rgb.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(rgb, dtype=np.float32) / 255.0


def run_marigold_iid_lighting(
    image: Image.Image,
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the official Diffusers Marigold IID Lighting pipeline.

    Output conversion intentionally uses ``visualize_intrinsics`` with the
    checkpoint's ``target_properties``. This is the official API that applies
    the checkpoint-specific prediction-space interpretation.
    """
    checkpoint = str(settings.get("iid_checkpoint") or MARIGOLD_IID_CHECKPOINT)
    pipe, torch, source = _pipeline(
        checkpoint,
        allow_download=bool(settings.get("iid_allow_download", False)),
    )
    steps = max(1, min(20, int(settings.get("iid_denoise_steps", 4))))
    ensemble = max(1, min(10, int(settings.get("iid_ensemble_size", 1))))
    processing_resolution = max(0, min(2048, int(settings.get("iid_processing_resolution", 768))))
    seed = int(settings.get("iid_seed", 0))
    generator = torch.Generator(device="cuda").manual_seed(seed)
    with torch.inference_mode():
        output = pipe(
            image.convert("RGB"),
            num_inference_steps=steps,
            ensemble_size=ensemble,
            processing_resolution=processing_resolution,
            match_input_resolution=True,
            output_type="np",
            generator=generator,
        )
    visualized = pipe.image_processor.visualize_intrinsics(
        output.prediction,
        pipe.target_properties,
    )
    if not visualized or not isinstance(visualized[0], dict):
        raise RuntimeError("Marigold IID returned no visualized intrinsic maps")
    maps = visualized[0]
    missing = [name for name in ("albedo", "shading", "residual") if name not in maps]
    if missing:
        raise RuntimeError(f"Marigold IID Lighting output is missing: {', '.join(missing)}")
    size = image.size
    return {
        "albedo": _pil_to_float_rgb(maps["albedo"], size),
        "shading": _pil_to_float_rgb(maps["shading"], size),
        "residual": _pil_to_float_rgb(maps["residual"], size),
        "metadata": {
            "backend": "marigold_iid_lighting",
            "checkpoint": checkpoint,
            "checkpoint_source": source,
            "denoise_steps": steps,
            "ensemble_size": ensemble,
            "processing_resolution": processing_resolution,
            "seed": seed,
            "target_properties": json.loads(json.dumps(pipe.target_properties, default=str)),
            "equation": "I = A * S + R",
            "conversion": "official_diffusers_visualize_intrinsics",
        },
    }
