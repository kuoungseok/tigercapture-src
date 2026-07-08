"""Audit strict product-catalog captures before deck generation.

This tool intentionally does not copy, rename, crop, or normalize screenshots.
Older versions tried to fill missing catalog assets by reusing similar captures
from other features. That made invalid pages look complete. The current rule is
stricter: feature-specific capture scripts must write the exact screenshots and
sidecar contracts consumed by ``tools/build_full_product_catalog_decks.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools" / "build_full_product_catalog_decks.py"


def _main() -> int:
    result = subprocess.run(
        [sys.executable, str(BUILDER), "--preflight-only"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    sys.stdout.write(result.stdout)
    if result.returncode != 0:
        sys.stdout.write(
            "\nStrict capture audit failed. Recapture the named feature pages "
            "from the real TigerCapture UI and write their .capture-contract.json "
            "sidecars. Do not stage substitute screenshots here.\n"
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(_main())
