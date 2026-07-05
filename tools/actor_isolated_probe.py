from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write(payload: dict, out: str = "") -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if out:
        target = Path(out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print(text)


def run_probe(kind: str, path: str, *, width: int = 256, height: int = 256, pos_ms: int = 0) -> dict:
    started = time.perf_counter()
    kind = str(kind or "").lower()
    source = Path(path)
    result: dict = {
        "kind": kind,
        "path": str(source),
        "width": int(width),
        "height": int(height),
        "pos_ms": int(pos_ms),
        "status": "fail",
    }
    try:
        from app.actor_compat_repair import repair_actor_model_path

        repaired = repair_actor_model_path(kind, str(source))
        result["repair"] = repaired
        load_path = repaired.get("path") or str(source)
        if kind == "live2d":
            from tools.test_live2d_resources import run_one

            payload = run_one(
                Path(load_path),
                width,
                height,
                timeout=30,
                sweep_ms=[max(0, int(pos_ms)), 250, 500, 1000],
            )
            result.update(payload)
            result["status"] = "pass" if payload.get("status") == "pass" else str(payload.get("status") or "fail")
            return result
        elif kind == "spine":
            from tools.test_spine_resources import _test_one

            payload = _test_one(Path(load_path), width, height)
            result.update(payload)
            result["status"] = "pass" if payload.get("status") == "pass" else str(payload.get("status") or "fail")
            return result
        else:
            result.update({"status": "fail", "error": f"unknown actor kind: {kind}"})
            return result

        return result
    except Exception as exc:
        result.update({"status": "crash", "error": f"{type(exc).__name__}: {exc}"})
        return result
    finally:
        result["elapsed_ms"] = int((time.perf_counter() - started) * 1000)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Run one actor render probe in an isolated process.")
    parser.add_argument("kind", choices=["live2d", "spine"])
    parser.add_argument("path")
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--height", type=int, default=256)
    parser.add_argument("--pos-ms", type=int, default=0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    payload = run_probe(args.kind, args.path, width=args.width, height=args.height, pos_ms=args.pos_ms)
    _write(payload, args.out)
    return 0 if payload.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
