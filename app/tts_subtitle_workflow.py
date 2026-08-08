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
TTS_TEXT_KEYS = ("tts_text", "spoken_text", "voice_text", "speech_text", "source_text")
SUBTITLE_TEXT_KEYS = ("subtitle_text", "display_text", "caption_text", "translation_text")


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


def _first_text(mapping: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        text = str(mapping.get(key) or "").strip()
        if text:
            return text
    return ""


def split_subtitle_tts_text(
    text: str,
    *,
    style: Mapping[str, Any] | None = None,
    row: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Return ``(display_text, tts_text)`` for bilingual subtitle/TTS rows."""
    base = str(text or "").strip()
    style_map = dict(style or {})
    row_map = dict(row or {})
    display = _first_text(row_map, SUBTITLE_TEXT_KEYS) or _first_text(style_map, SUBTITLE_TEXT_KEYS) or base
    tts = _first_text(row_map, TTS_TEXT_KEYS) or _first_text(style_map, TTS_TEXT_KEYS) or base or display
    return display, tts


def subtitle_rows_from_owner(owner: Any) -> list[dict[str, Any]]:
    panel = getattr(owner, "_subtitle_panel", None)
    rows: list[dict[str, Any]] = []
    for index, sub in enumerate(_subtitle_items(panel)):
        base_text = str(getattr(sub, "text", "") or "").strip()
        style = dict(getattr(sub, "style", {}) or {})
        display_text, tts_text = split_subtitle_tts_text(base_text, style=style)
        start_ms = max(0, _int(getattr(sub, "start_ms", 0), 0))
        end_ms = max(start_ms + 1, _int(getattr(sub, "end_ms", start_ms + 1), start_ms + 1))
        if not display_text and not tts_text:
            continue
        rows.append(
            {
                "index": index,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": end_ms - start_ms,
                "text": tts_text,
                "tts_text": tts_text,
                "subtitle_text": display_text,
                "display_text": display_text,
                "style": style,
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
    for candidate in ("koharune-ami", "zoe", "ZOE"):
        for name in model_names:
            if name.casefold() == candidate.casefold():
                return name
    return model_names[0] if model_names else str(requested or "")


def _model_names_from_status(status: Mapping[str, Any]) -> list[str]:
    return [
        str(name)
        for name in (((status.get("root") or {}) if isinstance(status.get("root"), Mapping) else {}).get("model_names") or [])
    ]


def _looks_japanese(text: str) -> bool:
    for ch in str(text or ""):
        code = ord(ch)
        if 0x3040 <= code <= 0x30FF or 0x31F0 <= code <= 0x31FF:
            return True
    return False


def preferred_dialogue_model_name(
    status: Mapping[str, Any],
    rows: Iterable[Mapping[str, Any]] | None = None,
    *,
    requested: str = "",
    language: str = "",
) -> str:
    """Choose a voice for dialogue text while respecting explicit user picks."""
    model_names = _model_names_from_status(status)
    wanted = str(requested or "").strip()
    if wanted and wanted in model_names:
        return wanted
    text = "\n".join(str(row.get("text") or row.get("subtitle_text") or "") for row in (rows or []) if isinstance(row, Mapping))
    wants_jp = str(language or "").strip().casefold() in {"jp", "ja", "japanese"} or _looks_japanese(text)
    # Local workspace defaults are product/user intent, not generic language
    # fallbacks. Keep explicit requests authoritative, then prefer the current
    # broadcast dialogue default before falling back to other installed JP voices.
    for candidate in ("koharune-ami", "zoe", "ZOE"):
        for name in model_names:
            if name.casefold() == candidate.casefold():
                return name
    if wants_jp:
        preferred_jp = (
            "koharune-ami",
            "jvnv-F1-jp",
            "jvnv-F2-jp",
            "amitaro",
            "jvnv-M1-jp",
            "jvnv-M2-jp",
        )
        for candidate in preferred_jp:
            for name in model_names:
                if name.casefold() == candidate.casefold():
                    return name
        for name in model_names:
            low = name.casefold()
            if "-jp" in low or "jp" == low:
                return name
    return preferred_model_name(status, wanted or "koharune-ami")


def stable_synthesis_params(
    rows: Iterable[Mapping[str, Any]],
    *,
    model_name: str = "",
    language: str = "",
    style: str = "",
    style_weight: float | None = None,
    sdp_ratio: float | None = None,
    noise: float | None = None,
    noisew: float | None = None,
    length: float | None = None,
) -> dict[str, Any]:
    """Return conservative TTS defaults for dialogue-take generation.

    Style-Bert-VITS2 voices can sound unstable when a Japanese voice is driven
    without language/noise controls.  Caller-provided values always win.
    """
    text = "\n".join(str(row.get("text") or row.get("subtitle_text") or "") for row in rows if isinstance(row, Mapping))
    model = str(model_name or "")
    inferred_jp = _looks_japanese(text) or model.casefold().endswith("-jp") or "-jp" in model.casefold()
    resolved_language = str(language or "").strip()
    if not resolved_language and inferred_jp:
        resolved_language = "JP"
    return {
        "language": resolved_language,
        "style": str(style or ""),
        "style_weight": 5.0 if style_weight is None and inferred_jp and style else style_weight,
        "sdp_ratio": 0.2 if sdp_ratio is None and inferred_jp else sdp_ratio,
        "noise": 0.45 if noise is None and inferred_jp else noise,
        "noisew": 0.6 if noisew is None and inferred_jp else noisew,
        "length": 1.08 if length is None and inferred_jp else length,
        "inferred_language": "JP" if inferred_jp else "",
    }


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
    voice_text = str(row.get("tts_text") or row.get("text") or "")
    text_hash = hashlib.sha1(voice_text.encode("utf-8", errors="ignore")).hexdigest()[:8]
    slug = _safe_slug(voice_text)
    return root / batch / f"tts_sub_{index:04d}_{start:08d}_{slug}_{text_hash}.wav"


def build_subtitle_tts_plan(
    owner: Any,
    *,
    provider_id: str = "",
    model_name: str = "",
    subtitle_indices: Sequence[int] | None = None,
    output_dir: str | Path | None = None,
    track_id: int | None = None,
    track_name: str = TTS_DIALOGUE_TRACK_NAME,
) -> dict[str, Any]:
    from app.tts_setup import tts_provider_status

    status = tts_provider_status(provider_id=provider_id) if provider_id else tts_provider_status()
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
        "requires_server": bool(status.get("requires_server", True)),
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
    provider_id: str = "style_bert_vits2_sidecar",
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
    from app.tts_gpt_sovits import GPT_SOVITS_PROVIDER_ID, synthesize_gpt_sovits_voice
    from app.tts_kokoro import KOKORO_PROVIDER_ID, synthesize_kokoro_voice
    from app.tts_setup import tts_provider_status
    from app.tts_synthesis import synthesize_style_bert_voice

    batch = str(batch_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
    source_rows = [dict(row) for row in rows]
    synthesis_params = stable_synthesis_params(
        source_rows,
        model_name=model_name,
        language=language,
        style=style,
        style_weight=style_weight,
        sdp_ratio=sdp_ratio,
        noise=noise,
        noisew=noisew,
        length=length,
    )
    results: list[dict[str, Any]] = []
    selected_provider = str(provider_id or "style_bert_vits2_sidecar")
    for row in source_rows:
        output_path = subtitle_voice_output_path(row, output_dir=output_dir, batch_id=batch)
        if selected_provider == KOKORO_PROVIDER_ID:
            speed = 1.0
            try:
                if length is not None and float(length) > 0:
                    speed = 1.0 / float(length)
            except Exception:
                speed = 1.0
            result = synthesize_kokoro_voice(
                text=str(row.get("tts_text") or row.get("text") or ""),
                output_path=output_path,
                voice=model_name or "af_heart",
                language=language or str(synthesis_params.get("language") or ""),
                speed=speed,
                timeout_s=timeout_s,
            )
        elif selected_provider == GPT_SOVITS_PROVIDER_ID:
            status = tts_provider_status(provider_id=selected_provider)
            root = status.get("root") or {}
            result = synthesize_gpt_sovits_voice(
                text=str(row.get("tts_text") or row.get("text") or ""),
                output_path=output_path,
                endpoint=endpoint,
                root=str(root.get("root") or "") if isinstance(root, Mapping) else "",
                preset_id=model_name,
                language=language or str(synthesis_params.get("language") or ""),
                timeout_s=timeout_s,
            )
        else:
            result = synthesize_style_bert_voice(
                text=str(row.get("tts_text") or row.get("text") or ""),
                output_path=output_path,
                endpoint=endpoint,
                model_name=model_name,
                language=str(synthesis_params.get("language") or ""),
                style=str(synthesis_params.get("style") or ""),
                style_weight=synthesis_params.get("style_weight"),
                sdp_ratio=synthesis_params.get("sdp_ratio"),
                noise=synthesis_params.get("noise"),
                noisew=synthesis_params.get("noisew"),
                length=synthesis_params.get("length"),
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
                "provider_id": selected_provider,
                "model_name": model_name,
                "endpoint": endpoint,
                "synthesis_params": dict(synthesis_params),
            }
        )
    return results


__all__ = [
    "TTS_DIALOGUE_TRACK_NAME",
    "build_subtitle_tts_plan",
    "default_tts_output_dir",
    "filter_subtitle_rows",
    "preferred_model_name",
    "preferred_dialogue_model_name",
    "stable_synthesis_params",
    "split_subtitle_tts_text",
    "subtitle_rows_from_owner",
    "subtitle_voice_output_path",
    "synthesize_subtitle_rows",
]
