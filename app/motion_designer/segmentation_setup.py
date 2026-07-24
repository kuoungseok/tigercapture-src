"""Readiness and user-consented installation contracts for Motion cutout AI."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
from typing import Any


SEGMENTATION_SETUP_SCHEMA = "tigerstudio.motion.segmentation_setup.v1"
BIREFNET_PROVIDER_ID = "birefnet_matting"
SAM2_PROVIDER_ID = "sam2_assisted"
BIREFNET_MODEL_ID = "ZhengPeng7/BiRefNet-matting"
SAM2_MODEL_ID = "facebook/sam2.1-hiera-small"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def segmentation_model_root() -> Path:
    configured = str(os.environ.get("TIGERSTUDIO_SEGMENTATION_MODEL_ROOT") or "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else _repo_root() / "external" / "assets" / "motion_ai" / "models"
    )


def segmentation_runtime_root() -> Path:
    configured = str(os.environ.get("TIGERSTUDIO_SEGMENTATION_RUNTIME_ROOT") or "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else _repo_root() / "external" / "tools" / "motion_ai" / "python_packages"
    )


def activate_segmentation_runtime() -> Path:
    root = segmentation_runtime_root()
    if root.is_dir() and str(root) not in sys.path:
        # Append so the editor's pinned core packages such as numpy and torch win.
        sys.path.append(str(root))
        importlib.invalidate_caches()
    return root


def provider_model_path(provider_id: str) -> Path:
    name = "BiRefNet-matting" if provider_id == BIREFNET_PROVIDER_ID else "sam2.1-hiera-small"
    return segmentation_model_root() / name


def _model_files_ready(path: Path) -> bool:
    return (
        path.joinpath("config.json").is_file()
        and any(path.glob("*.safetensors"))
    )


def segmentation_provider_status(provider_id: str) -> dict[str, Any]:
    provider_id = str(provider_id or BIREFNET_PROVIDER_ID)
    if provider_id not in {BIREFNET_PROVIDER_ID, SAM2_PROVIDER_ID}:
        raise ValueError(f"unsupported segmentation provider: {provider_id}")
    path = provider_model_path(provider_id)
    runtime_root = activate_segmentation_runtime()
    required_modules = (
        ("transformers", "timm", "kornia", "einops")
        if provider_id == BIREFNET_PROVIDER_ID
        else ("transformers",)
    )
    missing_modules = [
        module
        for module in required_modules
        if importlib.util.find_spec(module) is None
    ]
    package_ready = not missing_modules
    model_ready = _model_files_ready(path)
    available = bool(package_ready and model_ready)
    label = "BiRefNet Matting" if provider_id == BIREFNET_PROVIDER_ID else "SAM 2 Assisted"
    purpose = (
        "Automatic soft-alpha cutout"
        if provider_id == BIREFNET_PROVIDER_ID
        else "Point and box guided object masks"
    )
    return {
        "schema": SEGMENTATION_SETUP_SCHEMA,
        "provider_id": provider_id,
        "label": label,
        "purpose": purpose,
        "available": available,
        "installed": available,
        "setup_needed": not available,
        "package_ready": package_ready,
        "missing_modules": missing_modules,
        "model_ready": model_ready,
        "model_path": str(path),
        "runtime_path": str(runtime_root),
        "model_id": BIREFNET_MODEL_ID if provider_id == BIREFNET_PROVIDER_ID else SAM2_MODEL_ID,
        "reason": (
            f"{label} is ready."
            if available
            else (
                "Required runtime modules are missing: " + ", ".join(missing_modules)
                if not package_ready
                else f"Model files are missing from {path}."
            )
        ),
        "license": "MIT" if provider_id == BIREFNET_PROVIDER_ID else "Apache-2.0",
        "requires_network": not available,
    }


def segmentation_setup_status() -> dict[str, Any]:
    providers = [
        segmentation_provider_status(BIREFNET_PROVIDER_ID),
        segmentation_provider_status(SAM2_PROVIDER_ID),
    ]
    return {
        "schema": SEGMENTATION_SETUP_SCHEMA,
        "available": all(bool(row["available"]) for row in providers),
        "automatic_cutout_ready": bool(providers[0]["available"]),
        "assisted_segmentation_ready": bool(providers[1]["available"]),
        "providers": providers,
        "recommended_provider": BIREFNET_PROVIDER_ID,
        "legacy_fallback": "local_basic",
    }


def segmentation_install_plan(
    providers: tuple[str, ...] = (BIREFNET_PROVIDER_ID, SAM2_PROVIDER_ID),
) -> dict[str, Any]:
    selected = [
        provider
        for provider in providers
        if provider in {BIREFNET_PROVIDER_ID, SAM2_PROVIDER_ID}
    ]
    if not selected:
        selected = [BIREFNET_PROVIDER_ID, SAM2_PROVIDER_ID]
    installer = _repo_root() / "tools" / "install_motion_segmentation.py"
    command = [
        sys.executable,
        str(installer),
        "--model-root",
        str(segmentation_model_root()),
        "--runtime-root",
        str(segmentation_runtime_root()),
        "--providers",
        ",".join(selected),
    ]
    return {
        "schema": SEGMENTATION_SETUP_SCHEMA,
        "title": "Install Motion AI cutout models",
        "providers": selected,
        "target_root": str(segmentation_model_root()),
        "runtime_root": str(segmentation_runtime_root()),
        "requires_network": True,
        "requires_user_consent": True,
        "estimated_download": "About 1.3 GB plus the local vision runtime",
        "command": command,
        "license_notice": (
            "BiRefNet code is MIT licensed. SAM 2 code and checkpoints are "
            "Apache-2.0 licensed. Third-party notices are retained."
        ),
        "steps": [
            "Install the pinned Transformers and Hugging Face runtime.",
            "Download BiRefNet-matting into the durable Motion AI model folder.",
            "Download SAM 2.1 Hiera Small into the same model folder.",
            "Verify configs and safetensors without running project mutations.",
        ],
    }


__all__ = [
    "BIREFNET_MODEL_ID",
    "BIREFNET_PROVIDER_ID",
    "SAM2_MODEL_ID",
    "SAM2_PROVIDER_ID",
    "SEGMENTATION_SETUP_SCHEMA",
    "provider_model_path",
    "segmentation_install_plan",
    "segmentation_model_root",
    "segmentation_runtime_root",
    "activate_segmentation_runtime",
    "segmentation_provider_status",
    "segmentation_setup_status",
]
