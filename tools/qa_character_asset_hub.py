from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.character_asset_hub import (  # noqa: E402
    scan_character_asset_folder,
    simulate_character_asset_hub_user_flow,
    summarize_character_asset_hub,
    write_character_asset_hub_thumbnails,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Character Asset Hub folder-intake QA.")
    parser.add_argument("root", type=Path, help="Folder dropped by the user.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/character_asset_hub_qa.json"))
    parser.add_argument("--thumb-dir", type=Path, default=Path("debugCapture/character_asset_hub_thumbnails"))
    parser.add_argument("--max-depth", type=int, default=8)
    parser.add_argument("--render-probe", action="store_true")
    parser.add_argument("--simulate-user", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.simulate_user:
        payload = simulate_character_asset_hub_user_flow(args.root, max_depth=args.max_depth)
        payload["scan"] = write_character_asset_hub_thumbnails(payload.get("scan") or {}, args.thumb_dir)
    else:
        payload = scan_character_asset_folder(
            args.root,
            max_depth=args.max_depth,
            render_probe=bool(args.render_probe),
        )
        payload = write_character_asset_hub_thumbnails(payload, args.thumb_dir)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        scan_payload = payload.get("scan") if isinstance(payload.get("scan"), dict) else payload
        print(summarize_character_asset_hub(scan_payload))
        print(f"report: {args.out}")
        if args.simulate_user:
            print(f"timeline_steps: {int(payload.get('step_count', 0) or 0)}")
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
