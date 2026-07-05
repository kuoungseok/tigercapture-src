from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent / "ReviewAutomationWorkspace"


CACHE_DIRS = (
    WORKSPACE / "tmp" / "catalog_deck_build",
    WORKSPACE / "tmp" / "catalog_ppt_build",
    WORKSPACE / "tmp" / "catalog_rendered_slides",
    WORKSPACE / "tmp" / "review_catalog_build",
    WORKSPACE / "tmp" / "ppt_render_verify",
)


OUTPUT_ASSET_PATTERNS = (
    "*_assets",
    "*_slide_pngs",
    "*_rendered",
)


def _safe_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def clean_review_catalog_cache(*, apply: bool = False) -> list[str]:
    removed: list[str] = []
    for target in CACHE_DIRS:
        if not _safe_under(target, WORKSPACE):
            raise RuntimeError(f"refusing to clean outside workspace: {target}")
        if target.exists():
            removed.append(str(target))
            if apply:
                shutil.rmtree(target)

    outputs = WORKSPACE / "outputs"
    if outputs.exists():
        for pattern in OUTPUT_ASSET_PATTERNS:
            for target in outputs.glob(pattern):
                if target.is_dir() and _safe_under(target, outputs):
                    removed.append(str(target))
                    if apply:
                        shutil.rmtree(target)

    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely clear transient review catalog PPT caches.")
    parser.add_argument("--apply", action="store_true", help="Actually delete cache directories. Default is dry-run.")
    args = parser.parse_args()
    removed = clean_review_catalog_cache(apply=args.apply)
    mode = "removed" if args.apply else "would_remove"
    for path in removed:
        print(f"{mode}: {path}")
    if not removed:
        print("no review catalog cache directories found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
