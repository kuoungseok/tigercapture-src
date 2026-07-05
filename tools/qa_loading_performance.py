from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_loading_performance_qa(
    *,
    out_path: str | Path = "debugCapture/loading_performance_qa.json",
) -> dict:
    from app.loading_performance import loading_performance_report
    from app.preview_engine_status import preview_engine_status

    report = loading_performance_report()
    engine = preview_engine_status()
    checks = {
        "loading_log_readable": bool(report.get("ok")),
        "decoder_auto_default_on": str(engine.get("decoder_auto", "")).lower() in {"1", "true", "yes", "on"},
        "frame_server_auto_default": str(engine.get("frame_server", "")).lower() in {"auto", "1", "true", "yes", "on"},
        "frame_cache_default": int(str(engine.get("frame_cache_limit") or "0")) >= 24,
        "ar_pbr_gpu_preview_default_on": str(engine.get("ar_pbr_gpu_preview", "")).lower() not in {"0", "false", "off"},
        "spine_zero_readback_default_on": str(engine.get("spine_zero_readback", "")).lower() not in {"0", "false", "off"},
    }
    payload = {
        "ok": all(checks.values()),
        "checks": checks,
        "preview_engine": engine,
        "loading_performance": report,
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return payload


if __name__ == "__main__":
    print(json.dumps(run_loading_performance_qa(), ensure_ascii=False, indent=2, default=str))
