"""Lightweight client for the optional local Style-Bert-VITS2 sidecar."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json


@dataclass(frozen=True)
class VoiceSynthesisResult:
    path: Path
    byte_count: int
    duration_ms: int = 0
    endpoint: str = ""
    model_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "byte_count": int(self.byte_count),
            "duration_ms": int(self.duration_ms),
            "endpoint": self.endpoint,
            "model_name": self.model_name,
        }


def _endpoint_url(endpoint: str, route: str) -> str:
    base = str(endpoint or "").strip().rstrip("/")
    if not base:
        raise ValueError("TTS endpoint is empty")
    return f"{base}/{route.strip('/')}"


def fetch_style_bert_models(endpoint: str, *, timeout_s: float = 5.0) -> dict[str, Any]:
    """Return `/models/info` from a running Style-Bert-VITS2 sidecar."""
    req = Request(_endpoint_url(endpoint, "models/info"), method="GET")
    with urlopen(req, timeout=max(0.5, float(timeout_s or 5.0))) as response:
        payload = response.read()
    try:
        return dict(json.loads(payload.decode("utf-8")))
    except Exception as exc:
        raise RuntimeError("TTS /models/info returned invalid JSON") from exc


def synthesize_style_bert_voice(
    *,
    text: str,
    output_path: str | Path,
    endpoint: str,
    model_name: str = "",
    speaker_name: str = "",
    language: str = "",
    style: str = "",
    style_weight: float | None = None,
    sdp_ratio: float | None = None,
    noise: float | None = None,
    noisew: float | None = None,
    length: float | None = None,
    timeout_s: float = 120.0,
) -> VoiceSynthesisResult:
    """Generate a wav file through the local `/voice` endpoint.

    Style-Bert-VITS2 expects most inputs as query params even for POST.
    Keep this in a tiny stdlib client so the editor process does not import
    torch or the sidecar package.
    """
    body_text = str(text or "").strip()
    if not body_text:
        raise ValueError("TTS text is empty")
    out = Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    params: dict[str, Any] = {"text": body_text}
    if model_name:
        params["model_name"] = str(model_name)
    if speaker_name:
        params["speaker_name"] = str(speaker_name)
    if language:
        params["language"] = str(language)
    if style:
        params["style"] = str(style)
    for key, value in (
        ("style_weight", style_weight),
        ("sdp_ratio", sdp_ratio),
        ("noise", noise),
        ("noisew", noisew),
        ("length", length),
    ):
        if value is not None:
            params[key] = value

    url = _endpoint_url(endpoint, "voice") + "?" + urlencode(params)
    req = Request(url, data=b"", method="POST")
    try:
        with urlopen(req, timeout=max(1.0, float(timeout_s or 120.0))) as response:
            audio = response.read()
    except Exception as exc:
        from app.tts_sidecar_runtime import format_tts_sidecar_guidance, tts_sidecar_failure_guidance

        guidance = tts_sidecar_failure_guidance(
            "server_offline",
            endpoint=endpoint,
            raw_error=str(exc),
        )
        raise RuntimeError(format_tts_sidecar_guidance(guidance)) from exc
    if not audio:
        raise RuntimeError("TTS endpoint returned empty audio")
    out.write_bytes(audio)

    duration_ms = 0
    try:
        from app.audio_tracks import probe_audio_duration_ms

        duration_ms = int(probe_audio_duration_ms(out) or 0)
    except Exception:
        duration_ms = 0
    return VoiceSynthesisResult(
        path=out.resolve(),
        byte_count=len(audio),
        duration_ms=max(0, duration_ms),
        endpoint=str(endpoint or ""),
        model_name=str(model_name or ""),
    )


__all__ = [
    "VoiceSynthesisResult",
    "fetch_style_bert_models",
    "synthesize_style_bert_voice",
]
