"""Subprocess helper for the optional Kokoro external runtime."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


def _audio_to_numpy(audio):
    try:
        if hasattr(audio, "detach"):
            audio = audio.detach()
        if hasattr(audio, "cpu"):
            audio = audio.cpu()
        if hasattr(audio, "numpy"):
            return audio.numpy()
    except Exception:
        pass
    return audio


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthesize one WAV with Kokoro")
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--voice", default="af_heart")
    parser.add_argument("--language", default="a")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--text", required=True)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    target_packages = root / "python"
    if target_packages.exists():
        sys.path.insert(0, str(target_packages))
    cache = root / "hf_cache"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache))

    from kokoro import KPipeline
    import soundfile as sf

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    pipeline = KPipeline(lang_code=str(args.language or "a"))
    chunks = []
    for _graphemes, _phonemes, audio in pipeline(
        str(args.text or ""),
        voice=str(args.voice or "af_heart"),
        speed=max(0.25, min(4.0, float(args.speed or 1.0))),
        split_pattern=r"\n+",
    ):
        chunks.append(_audio_to_numpy(audio))
    if not chunks:
        raise RuntimeError("Kokoro returned no audio chunks")
    if len(chunks) == 1:
        merged = chunks[0]
    else:
        import numpy as np

        merged = np.concatenate(chunks)
    sf.write(str(output), merged, 24000)
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
