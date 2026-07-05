from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _manifest_candidates(manifest: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key in ("actors", "models", "entries", "items"):
        raw = manifest.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or item.get("type") or "").lower()
            path = str(item.get("path") or item.get("model_path") or item.get("skel_path") or "")
            if kind in {"live2d", "spine"} and path:
                rows.append({"kind": kind, "path": path})
    return rows


def _status_candidates(status: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key in ("results", "entries", "models"):
        raw = status.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or item.get("type") or "").lower()
            path = str(item.get("path") or item.get("source") or item.get("model_path") or item.get("skel_path") or "")
            if kind in {"live2d", "spine"} and path:
                rows.append({"kind": kind, "path": path})
    return rows


def run_actor_overnight_qa(
    *,
    render: bool = False,
    limit: int = 20,
    timeout_ms: int = 25_000,
    manifest_path: Path = ROOT / "qa_corpus" / "actor_corpus_manifest.json",
    status_path: Path = ROOT / "debugCapture" / "actor_corpus_status.json",
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    status = _load_json(status_path)
    candidates = _manifest_candidates(manifest) + _status_candidates(status)
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for row in candidates:
        key = (row["kind"], row["path"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    if limit > 0:
        deduped = deduped[:limit]

    probe_results: list[dict[str, Any]] = []
    if render:
        from app.actor_process_probe import run_isolated_actor_probe

        for row in deduped:
            probe_results.append(
                run_isolated_actor_probe(
                    row["kind"],
                    row["path"],
                    width=320,
                    height=320,
                    timeout_ms=timeout_ms,
                )
            )

    failures = [
        row for row in probe_results
        if str(row.get("status") or "") not in {"pass"}
    ]
    checks = {
        "manifest_exists": manifest_path.exists(),
        "status_report_exists": status_path.exists(),
        "candidate_plan_ready": len(deduped) > 0,
        "render_probe_passed": not render or not failures,
    }
    return {
        "ok": all(checks.values()),
        "summary": {
            "planned_candidates": len(deduped),
            "rendered": len(probe_results),
            "failures": len(failures),
            "render": bool(render),
        },
        "checks": checks,
        "candidates": deduped,
        "probe_results": probe_results,
        "failures": failures,
        "manifest_path": str(manifest_path),
        "status_path": str(status_path),
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Plan or run overnight Live2D/Spine isolated render QA.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/actor_overnight_qa.json"))
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--timeout-ms", type=int, default=25_000)
    parser.add_argument("--manifest", type=Path, default=ROOT / "qa_corpus" / "actor_corpus_manifest.json")
    parser.add_argument("--status", type=Path, default=ROOT / "debugCapture" / "actor_corpus_status.json")
    args = parser.parse_args()
    report = run_actor_overnight_qa(
        render=args.render,
        limit=args.limit,
        timeout_ms=args.timeout_ms,
        manifest_path=args.manifest,
        status_path=args.status,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {args.out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
