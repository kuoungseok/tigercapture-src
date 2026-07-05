"""QA for Descript-lite P2 editable transcription contracts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_REPORT = ROOT / "debugCapture" / "descript_lite_p2_transcription_qa.json"


def build_descript_lite_p2_transcription_report() -> dict:
    from app.ai_script_edit_panel import ScriptEditPanelModel
    from app.transcript_cleanup import cleanup_transcript_document
    from app.transcription_providers import (
        build_editable_script_document,
        segments_to_word_timed_document,
        transcription_provider_readiness,
    )

    raw_segments = [
        {
            "id": "seg_001",
            "start_ms": 0,
            "end_ms": 2000,
            "text": "obs 타임 라인 export",
            "words": [
                {"text": "obs", "start_ms": 0, "end_ms": 400, "confidence": 0.91},
                {"text": "타임", "start_ms": 500, "end_ms": 900, "confidence": 0.88},
                {"text": "라인", "start_ms": 900, "end_ms": 1200, "confidence": 0.86},
                {"text": "export", "start_ms": 1300, "end_ms": 1800, "confidence": 0.92},
            ],
        },
        {"id": "seg_002", "start_ms": 3200, "end_ms": 5200, "text": "라이브 투디 shader check"},
    ]
    speaker_turns = [
        {"speaker": "speaker_1", "start_ms": 0, "end_ms": 2200},
        {"speaker": "speaker_2", "start_ms": 3000, "end_ms": 5400},
    ]
    word_doc = segments_to_word_timed_document(raw_segments, document_id="p2_doc", source_media_id="clip_p2", language="ko-en")
    editable = build_editable_script_document(
        raw_segments,
        speaker_turns=speaker_turns,
        document_id="p2_doc",
        source_media_id="clip_p2",
        language="ko-en",
    )
    cleaned = cleanup_transcript_document(word_doc)
    model = ScriptEditPanelModel(source_media_id="clip_p2", language="ko-en")
    model.set_transcript_document(word_doc)
    model_prepared = model.prepare_editable_script(speaker_turns=speaker_turns)
    readiness = transcription_provider_readiness()
    checks = {
        "word_timed_document": bool(word_doc.segments[0].words) and word_doc.segments[1].words,
        "provider_word_timestamps_preserved": word_doc.segments[0].words[0].confidence == 0.91,
        "speaker_turn_assignment": [segment.speaker for segment in editable.segments] == ["speaker_1", "speaker_2"],
        "punctuation_cleanup": all(segment.text.endswith(".") for segment in cleaned.segments),
        "mixed_language_glossary": "OBS" in editable.segments[0].text and "Live2D" in editable.segments[1].text,
        "script_edit_model_prepare": model_prepared.metadata.get("cleanup", {}).get("punctuation_restored") is True,
        "local_word_timestamp_route": bool(readiness.get("faster_whisper_installed")),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "kind": "descript_lite_p2_transcription",
        "ok": not failures,
        "score": int(round(100 * (len(checks) - len(failures)) / max(1, len(checks)))),
        "runtime_model_ready": bool(readiness.get("runtime_model_ready")),
        "checks": checks,
        "failures": failures,
        "summary": {
            "segments": len(editable.segments),
            "word_timed_segments": sum(1 for segment in editable.segments if segment.words),
            "speakers": sorted({segment.speaker for segment in editable.segments if segment.speaker}),
            "glossary_hits": len(editable.metadata.get("cleanup", {}).get("glossary_hits", [])),
        },
        "provider_readiness": readiness,
        "artifacts": {
            "word_timed": word_doc.to_dict(),
            "editable": editable.to_dict(),
            "model_prepared": model_prepared.to_dict(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Descript-lite P2 transcription QA report.")
    parser.add_argument("--out", default=str(DEFAULT_REPORT), help="Output JSON report path.")
    args = parser.parse_args()

    report = build_descript_lite_p2_transcription_report()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "score": report["score"],
                "runtime_model_ready": report["runtime_model_ready"],
                "report": str(out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
