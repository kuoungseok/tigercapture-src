"""Configure the local faster-whisper model path used by TigerCapture."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_REPORT = ROOT / "debugCapture" / "transcription_settings_configure_qa.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Save or inspect the local faster-whisper model path.")
    parser.add_argument("--model-path", default="", help="Existing faster-whisper model folder or file to save.")
    parser.add_argument("--model-dir", default="", help="Existing local model root containing whisper/<size> folders.")
    parser.add_argument("--clear", action="store_true", help="Clear saved local transcription model settings.")
    parser.add_argument("--allow-missing", action="store_true", help="Save the path even if it does not exist yet.")
    parser.add_argument("--out", default=str(DEFAULT_REPORT), help="Output JSON report path.")
    args = parser.parse_args()

    from app.transcription_runtime_setup import build_transcription_runtime_setup_report
    from app.transcription_settings import (
        clear_local_transcription_settings,
        local_transcription_settings_state,
        save_local_model_dir,
        save_local_whisper_model_path,
    )

    configure_result: dict
    if args.clear:
        configure_result = clear_local_transcription_settings()
    elif args.model_path:
        configure_result = save_local_whisper_model_path(args.model_path, require_exists=not args.allow_missing)
    elif args.model_dir:
        configure_result = save_local_model_dir(args.model_dir, require_exists=not args.allow_missing)
    else:
        configure_result = {"ok": True, "settings": local_transcription_settings_state(), "reason": "inspect_only"}

    runtime_report = build_transcription_runtime_setup_report(ROOT)
    payload = {
        "kind": "transcription_settings_configure",
        "ok": bool(configure_result.get("ok")) and bool(runtime_report.get("ok")),
        "configure_result": configure_result,
        "runtime_report": runtime_report,
    }
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(payload.get("ok")),
                "runtime_model_ready": bool(runtime_report.get("runtime_model_ready")),
                "settings_path": str((runtime_report.get("settings") or {}).get("settings_path", "")),
                "report": str(out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
