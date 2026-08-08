"""Generate a regenerable PG1 readiness report from a real image asset."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=1280)
    args = parser.parse_args()

    from app.motion_designer.image_decomposition import decompose_image
    from app.motion_designer.layer_readiness import assess_layer_motion_readiness

    output = args.output.resolve()
    cache_root = output.parent / "decomposition_cache"
    result = decompose_image(
        args.source.resolve(),
        width=args.width,
        height=args.height,
        cache_root=cache_root,
        max_elements=5,
        include_depth=False,
        segmentation_mode="auto",
        inpaint_mode="auto",
        reconstruct_text=False,
        force=True,
    )
    report = assess_layer_motion_readiness(result)
    payload = {
        "source": str(args.source.resolve()),
        "decomposition": result.to_dict(),
        "readiness": report,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(output),
        "status": report["status"],
        "score": report["score"],
        "issues": len(report["issues"]),
    }, ensure_ascii=False))
    return 0 if report["status"] in {"ready", "review"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
