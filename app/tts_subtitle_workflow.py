"""Subtitle-to-TTS planning helpers.

The editor owns subtitle rows and audio tracks, but the shape of a TTS batch
should stay testable outside the UI. This module collects subtitle rows,
chooses a local voice model, and creates deterministic output paths.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
import hashlib
import re


TTS_DIALOGUE_TRACK_NAME = "TTS Dialogue"


def default_tts_output_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "external" / "assets" / "tts" / "generated"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _subtitle_items(panel: Any) -> list[Any]:
    if panel is None:
        return []
    subtitles = getattr(panel, "subtitles", None)
    if callable(subtitles):
        try:
            return list(subtitles() or [])
        except Exception:
            return []
    layer = getattr(panel, "layer", None)
    items = getattr(layer, "items", None)
    if callable(items):
        try:
            return list(items() or [])
        except Exception:
            return []
    return list(getattr(panel, "_subtitles", []) or [])


def subtitle_rows_from_owner(owner: Any) -> list[dict[str, Any]]:
    panel = getattr(owner, "_subtitle_panel", None)
    rows: list[dict[str, Any]] = []
    for index, sub in enumerate(_subtitle_items(panel)):
        text = str(getattr(sub, "text", "") or "").strip()
        start_ms = max(0, _int(getattr(sub, "start_ms", 0), 0))
        end_ms = max(start_ms + 1, _int(getattr(sub, "end_ms", start_ms + 1), start_ms + 1))
        if not text:
            continue
        rows.append(
            {
                "index": index,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": end_ms - start_ms,
                "text": text,
                "style": dict(getattr(sub, "style", {}) or {}),
            }
        )
    rows.sort(key=lambda row: (_int(row.get("start_ms")), _int(row.get("index"))))
    return rows


def filter_subtitle_rows(
    rows: Sequence[Mapping[str, Any]],
    indices: Sequence[int] | None = None,
) -> list[dict[str, Any]]:
    if not indices:
        return [dict(row) for row in rows]
    wanted = {_int(index, -1) for index in indices}
    return [dict(row) for row in rows if _int(row.get("index"), -2) in wanted]


def preferred_model_name(status: Mapping[str, Any], requested: str = "") -> str:
    model_names = [
        str(name)
        for name in (((status.get("root") or {}) if isinstance(status.get("root"), Mapping) else {}).get("model_names") or [])
    ]
    if requested and requested in model_names:
        return str(requested)
    for candidate in ("zoe", "ZOE"):
        for name in model_names:
            if name.casefold() == candidate.casefold():
                return name
    return model_names[0] if model_names else str(requested or "")


def _safe_slug(text: str, *, max_chars: int = 18) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(text or "")).strip("_").lower()
    if cleaned:
        return cleaned[:max_chars]
    return "line"


def subtitle_voice_output_path(
    row: Mapping[str, Any],
    *,
    output_dir: str | Path | None = None,
    batch_id: str = "",
) -> Path:
    root = Path(output_dir).expanduser() if output_dir else default_tts_output_dir()
    batch = str(batch_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
    index = max(0, _int(row.get("index"), 0))
    start = max(0, _int(row.get("start_ms"), 0))
    text_hash = hashlib.sha1(str(row.get("text") or "").encode("utf-8", errors="ignore")).hexdigest()[:8]
    slug = _safe_slug(str(row.get("text") or ""))
    return root / batch / f"tts_sub_{index:04d}_{start:08d}_{slug}_{text_hash}.wav"


def build_subtitle_tts_plan(
    owner: Any,
    *,
    model_name: str = "",
    subtitle_indices: Sequence[int] | None = None,
    output_dir: str | Path | None = None,
    track_id: int | None = None,
    track_name: str = TTS_DIALOGUE_TRACK_NAME,
) -> dict[str, Any]:
    from app.tts_setup import tts_provider_status

    status = tts_provider_status()
    all_rows = subtitle_rows_from_owner(owner)
    rows = filter_subtitle_rows(all_rows, subtitle_indices)
    selected_model = preferred_model_name(status, model_name)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    planned_rows: list[dict[str, Any]] = []
    for row in rows:
        output_path = subtitle_voice_output_path(row, output_dir=output_dir, batch_id=batch_id)
        planned_rows.append({**row, "output_path": str(output_path), "model_name": selected_model})
    guidance: dict[str, Any] | None = None
    if not bool(status.get("available")):
        from app.tts_sidecar_runtime import tts_sidecar_failure_guidance

        guidance = tts_sidecar_failure_guidance(
            "provider_not_ready",
            endpoint=str(status.get("endpoint") or ""),
            status=status,
            raw_error=str(status.get("reason") or ""),
        )
    return {
        "provider_id": status.get("provider_id", "style_bert_vits2_sidecar"),
        "ready": bool(status.get("available")),
        "endpoint": str(status.get("endpoint") or ""),
        "model_name": selected_model,
        "provider_status": status,
        "guidance": guidance or {},
        "track_id": track_id,
        "track_name": str(track_name or TTS_DIALOGUE_TRACK_NAME),
        "subtitle_count": len(rows),
        "skipped_empty_count": max(0, len(_subtitle_items(getattr(owner, "_subtitle_panel", None))) - len(all_rows)),
        "batch_id": batch_id,
        "output_dir": str(Path(output_dir).expanduser() if output_dir else default_tts_output_dir()),
        "rows": planned_rows,
    }


def synthesize_subtitle_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    endpoint: str,
    model_name: str,
    output_dir: str | Path | None = None,
    batch_id: str = "",
    language: str = "",
    style: str = "",
    style_weight: float | None = None,
    sdp_ratio: float | None = None,
    noise: float | None = None,
    noisew: float | None = None,
    length: float | None = None,
    timeout_s: float = 120.0,
) -> list[dict[str, Any]]:
    from app.tts_synthesis import synthesize_style_bert_voice

    batch = str(batch_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
    results: list[dict[str, Any]] = []
    for row in rows:
        output_path = subtitle_voice_output_path(row, output_dir=output_dir, batch_id=batch)
        result = synthesize_style_bert_voice(
            text=str(row.get("text") or ""),
            output_path=output_path,
            endpoint=endpoint,
            model_name=model_name,
            language=language,
            style=style,
            style_weight=style_weight,
            sdp_ratio=sdp_ratio,
            noise=noise,
            noisew=noisew,
            length=length,
            timeout_s=timeout_s,
        )
        duration_ms = int(result.duration_ms or 0)
        if duration_ms <= 0:
            duration_ms = max(1, _int(row.get("duration_ms"), _int(row.get("end_ms")) - _int(row.get("start_ms"))))
        results.append(
            {
                **dict(row),
                "path": str(result.path),
                "byte_count": result.byte_count,
                "generated_duration_ms": duration_ms,
                "model_name": model_name,
                "endpoint": endpoint,
            }
        )
    return results


__all__ = [
    "TTS_DIALOGUE_TRACK_NAME",
    "build_subtitle_tts_plan",
    "default_tts_output_dir",
    "filter_subtitle_rows",
    "preferred_model_name",
    "subtitle_rows_from_owner",
    "subtitle_voice_output_path",
    "synthesize_subtitle_rows",
]
