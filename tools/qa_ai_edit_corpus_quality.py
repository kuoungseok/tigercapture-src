"""Build AI Script Edit corpus quality report."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build AI Script Edit corpus quality report.")
    parser.add_argument("--manifest", default="", help="Optional qa_corpus/ai_editing_corpus/manifest.json path.")
    parser.add_argument("--out", default="debugCapture/ai_edit_corpus_quality_qa.json")
    parser.add_argument(
        "--use-provider",
        action="store_true",
        help="Call the currently selected configured AI provider. Default only scores deterministic baseline plans.",
    )
    parser.add_argument(
        "--provider",
        default="",
        help="Temporarily select a provider for this QA run, for example qwen_local, claude_mcp, local_llm, or rule_based.",
    )
    parser.add_argument(
        "--auto-start-qwen",
        action="store_true",
        help="Start the configured Qwen local server if its OpenAI-compatible endpoint is not responding.",
    )
    parser.add_argument(
        "--qwen-start-timeout",
        type=int,
        default=25,
        help="Seconds to wait for --auto-start-qwen before continuing with the provider QA.",
    )
    parser.add_argument(
        "--provider-timeout",
        type=int,
        default=0,
        help="Optional per-case provider timeout in seconds. Omit or pass 0 to use the provider default.",
    )
    parser.add_argument(
        "--provider-retries",
        type=int,
        default=0,
        help="Retry failed provider cases this many extra times before falling back.",
    )
    args = parser.parse_args()

    env = dict(os.environ)
    if args.provider:
        env["TIGERCAPTURE_AI_PROVIDER"] = str(args.provider).strip()
    qwen_auto_start: dict | None = None
    if args.auto_start_qwen:
        env["TIGERCAPTURE_AI_PROVIDER"] = "qwen_local"
        from app.ai_qwen_server import ensure_qwen_server

        qwen_auto_start = ensure_qwen_server(env=env, wait_seconds=max(1, int(args.qwen_start_timeout or 1))).to_dict()

    from app.ai_edit_corpus_quality import build_ai_edit_corpus_quality_report

    report = build_ai_edit_corpus_quality_report(
        manifest_path=args.manifest or None,
        use_provider=bool(args.use_provider),
        env=env,
        provider_timeout_seconds=int(args.provider_timeout or 0) or None,
        provider_retries=max(0, int(args.provider_retries or 0)),
    )
    if qwen_auto_start is not None:
        report.setdefault("provider", {})["qwen_auto_start"] = qwen_auto_start
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
