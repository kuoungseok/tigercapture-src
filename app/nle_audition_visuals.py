"""UI-ready visual models for Final Cut-style audition take comparison."""
from __future__ import annotations

from typing import Any


AUDITION_CARD_MODEL_SCHEMA = "tigerstudio.nle.audition_card_model.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _duration_text(ms: int) -> str:
    ms = max(0, _int(ms, 0))
    seconds = ms / 1000.0
    if seconds >= 60:
        return f"{int(seconds // 60)}:{int(seconds % 60):02d}.{int(ms % 1000 / 100)}"
    return f"{seconds:.1f}s"


def build_audition_card_model(compare: dict[str, Any] | None) -> dict[str, Any]:
    """Return card-sized take summaries from an audition compare payload."""

    compare = compare if isinstance(compare, dict) else {}
    active_take_id = str(compare.get("active_take_id") or "")
    takes = [row for row in list(compare.get("takes") or []) if isinstance(row, dict)]
    cards: list[dict[str, Any]] = []
    for index, take in enumerate(takes):
        take_id = str(take.get("id") or "")
        label = str(take.get("label") or take_id or f"Take {index + 1}")
        source = str(take.get("source_name") or take.get("source_path") or "")
        duration_ms = max(0, _int(take.get("take_duration_ms"), 0))
        if duration_ms <= 0:
            duration_ms = max(0, _int(take.get("source_out_ms"), 0) - _int(take.get("source_in_ms"), 0))
        delta_ms = _int(take.get("timeline_duration_delta_ms"), 0)
        if delta_ms > 0:
            delta_tone = "longer"
            delta_label = f"+{delta_ms} ms"
        elif delta_ms < 0:
            delta_tone = "shorter"
            delta_label = f"{delta_ms} ms"
        else:
            delta_tone = "match"
            delta_label = "match"
        active = bool(take.get("active") or (take_id and take_id == active_take_id))
        cards.append(
            {
                "index": index,
                "id": take_id,
                "label": label,
                "source": source,
                "duration_ms": duration_ms,
                "duration_label": _duration_text(duration_ms),
                "delta_ms": delta_ms,
                "delta_tone": delta_tone,
                "delta_label": delta_label,
                "active": active,
                "badge": "ACTIVE" if active else f"TAKE {index + 1}",
                "accent": "#FFB84A" if active else "#7772FF",
            }
        )

    return {
        "schema": AUDITION_CARD_MODEL_SCHEMA,
        "ready": bool(cards),
        "active_take_id": active_take_id,
        "card_count": len(cards),
        "cards": cards,
    }


__all__ = ["AUDITION_CARD_MODEL_SCHEMA", "build_audition_card_model"]
