"""User-invoked installer for Motion AI cutout models."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


MODELS = {
    "birefnet_matting": ("ZhengPeng7/BiRefNet-matting", "BiRefNet-matting"),
    "sam2_assisted": ("facebook/sam2.1-hiera-small", "sam2.1-hiera-small"),
}


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        raise RuntimeError(f"command failed with exit code {completed.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--providers", default="birefnet_matting,sam2_assisted")
    args = parser.parse_args()

    selected = [item.strip() for item in args.providers.split(",") if item.strip()]
    unknown = [item for item in selected if item not in MODELS]
    if unknown:
        raise SystemExit(f"Unsupported providers: {', '.join(unknown)}")
    model_root = Path(args.model_root).expanduser().resolve()
    model_root.mkdir(parents=True, exist_ok=True)
    runtime_root = Path(args.runtime_root).expanduser().resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)

    _run([
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        str(runtime_root),
        "--upgrade",
        "transformers>=5.0.0,<6",
        "huggingface_hub>=0.28,<2",
        "safetensors>=0.4",
        "timm>=1.0,<2",
        "kornia>=0.8,<1",
        "einops>=0.8,<1",
        "scipy>=1.14",
        "scikit-image>=0.25",
        "accelerate>=1.2,<2",
        "numpy>=2.1",
    ])
    if str(runtime_root) not in sys.path:
        sys.path.append(str(runtime_root))
    from huggingface_hub import snapshot_download

    installed: list[dict[str, str]] = []
    for provider in selected:
        model_id, folder = MODELS[provider]
        target = model_root / folder
        snapshot_download(
            repo_id=model_id,
            local_dir=str(target),
            local_dir_use_symlinks=False,
        )
        if not target.joinpath("config.json").is_file() or not any(target.glob("*.safetensors")):
            raise RuntimeError(f"{provider} model verification failed at {target}")
        installed.append({"provider": provider, "model_id": model_id, "path": str(target)})
    print(json.dumps({"ok": True, "installed": installed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
