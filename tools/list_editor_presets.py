"""List built-in and external editor presets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extra", action="append", type=Path, default=[])
    parser.add_argument("--kind")
    parser.add_argument("--query", default="")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    from app.preset_library import preset_library_summary, search_presets

    if args.summary:
        print(json.dumps(preset_library_summary(args.extra), ensure_ascii=False, indent=2))
        return 0

    presets = search_presets(
        args.query,
        kind=args.kind,
        tags=args.tag,
        extra_paths=args.extra,
    )
    print(json.dumps([preset.to_dict() for preset in presets], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
