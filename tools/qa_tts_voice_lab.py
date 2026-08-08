from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.tts_setup import tts_setup_view_model  # noqa: E402
from app.tts_sidecar_runtime import ensure_tts_sidecar_running, format_tts_sidecar_guidance  # noqa: E402


def build_voice_lab_qa_report(*, auto_start: bool = False, wait_timeout_s: float = 8.0) -> dict:
    """Return a local Voice Lab sidecar QA report without importing the TTS engine."""
    view = tts_setup_view_model()
    server = ensure_tts_sidecar_running(
        auto_start=bool(auto_start),
        wait_timeout_s=max(0.5, float(wait_timeout_s or 8.0)),
    )
    guidance = server.get("guidance") if isinstance(server.get("guidance"), dict) else {}
    ready = bool(view.get("ready")) and bool(server.get("ready"))
    user_message = str(server.get("message") or "").strip()
    if not ready or guidance:
        user_message = format_tts_sidecar_guidance(guidance, fallback=user_message)
    failures: list[str] = []
    if not bool(view.get("ready")):
        failures.append("provider_setup_needed")
    if not bool(server.get("ready")):
        failures.append("server_not_ready")
    if server.get("guidance") and not str(server.get("message") or "").strip():
        failures.append("missing_user_guidance")
    return {
        "schema": "tigercapture.qa.voice_lab_sidecar.v1",
        "ok": ready,
        "ready": ready,
        "failures": failures,
        "view": view,
        "server": server,
        "user_message": user_message,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Voice Lab sidecar preflight QA.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/voice_lab_sidecar_qa.json"))
    parser.add_argument("--auto-start", action="store_true", help="Allow QA to launch the configured sidecar server.")
    parser.add_argument("--wait-timeout", type=float, default=8.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_voice_lab_qa_report(auto_start=args.auto_start, wait_timeout_s=args.wait_timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        state = "ready" if report["ready"] else "not ready"
        failures = ", ".join(report.get("failures") or []) or "none"
        print(f"Voice Lab sidecar: {state}")
        print(f"failures: {failures}")
        message = str(report.get("user_message") or "").strip()
        if message:
            print(message)
        print(f"report: {args.out}")
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
