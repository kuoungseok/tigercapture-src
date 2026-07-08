"""Write an NLE target-score gap report.

This is intentionally diagnostic. It does not raise the readiness score and it
does not clear professional NLE claims without real long-project evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
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


def run_nle_target_gap_qa(
    *,
    target_score: int = 95,
    readiness_path: str | Path | None = None,
    real_corpus_path: str | Path | None = None,
) -> dict[str, Any]:
    from app.nle_target_gap import build_nle_target_gap_board
    from tools.qa_nle_readiness import run_nle_readiness_qa

    readiness_file = Path(readiness_path or ROOT / "debugCapture" / "nle_readiness_qa.json")
    if not readiness_file.is_absolute():
        readiness_file = ROOT / readiness_file
    real_file = Path(real_corpus_path or ROOT / "debugCapture" / "nle_real_project_corpus_qa.json")
    if not real_file.is_absolute():
        real_file = ROOT / real_file
    readiness_payload = _load_json(readiness_file)
    if not isinstance(readiness_payload.get("report"), dict):
        readiness_payload = run_nle_readiness_qa()
    real_corpus_payload = _load_json(real_file)
    board = build_nle_target_gap_board(
        readiness_payload.get("report") if isinstance(readiness_payload.get("report"), dict) else {},
        target_score=target_score,
        real_corpus_report=real_corpus_payload,
    )
    return {
        "kind": "nle_target_gap",
        "ok": bool(board.get("ready")),
        "target_score": int(target_score),
        "current_score": int(board.get("current_score") or 0),
        "score_gap": int(board.get("score_gap") or 0),
        "professional_claim_blocked": bool(board.get("professional_claim_blocked")),
        "board": board,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-score", type=int, default=95)
    parser.add_argument("--readiness", type=Path, default=Path("debugCapture/nle_readiness_qa.json"))
    parser.add_argument("--real-corpus", type=Path, default=Path("debugCapture/nle_real_project_corpus_qa.json"))
    parser.add_argument("--out", type=Path, default=Path("debugCapture/nle_target_gap_qa.json"))
    args = parser.parse_args(argv)
    payload = run_nle_target_gap_qa(
        target_score=args.target_score,
        readiness_path=args.readiness,
        real_corpus_path=args.real_corpus,
    )
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"NLE target gap: current={payload['current_score']} target={payload['target_score']} "
        f"gap={payload['score_gap']} claim_blocked={payload['professional_claim_blocked']}"
    )
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
