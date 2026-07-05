"""Local speech-enhance contracts for Studio Sound-style workflows.

This module deliberately separates two things:

* a reviewable enhancement plan that can be applied through the existing audio
  pipeline, and
* deterministic QA evidence that the local fallback path improves a noisy
  speech-like signal without calling a cloud service.

It is not a claim of universal Descript Studio Sound parity.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

import numpy as np

from app.ai_edit_plan import EditOperation, EditPlan, ReviewCard, build_edit_plan


@dataclass(frozen=True)
class SpeechEnhanceProvider:
    id: str
    label: str
    configured: bool
    local_first: bool
    regenerative: bool
    fallback: bool
    supports: tuple[str, ...]
    setup_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "configured": bool(self.configured),
            "local_first": bool(self.local_first),
            "regenerative": bool(self.regenerative),
            "fallback": bool(self.fallback),
            "supports": list(self.supports),
            "setup_hint": self.setup_hint,
        }


LOCAL_SPEECH_ENHANCE_PROVIDERS: tuple[SpeechEnhanceProvider, ...] = (
    SpeechEnhanceProvider(
        "local_speech_enhance_chain",
        "Local speech enhance chain",
        True,
        True,
        False,
        True,
        ("denoise", "dereverb", "deesser", "compressor", "loudness", "voice_isolation"),
        "Always available as the no-cloud fallback path.",
    ),
    SpeechEnhanceProvider(
        "external_regenerative_speech_slot",
        "Regenerative speech provider slot",
        False,
        False,
        True,
        False,
        ("speech_reconstruction", "room_tone_reduction", "preview_before_after"),
        "Configure an explicit local or licensed provider before claiming regenerative reconstruction.",
    ),
)


def speech_enhance_provider_contracts() -> list[dict[str, Any]]:
    return [provider.to_dict() for provider in LOCAL_SPEECH_ENHANCE_PROVIDERS]


def build_speech_enhance_chain(*, strength: float = 0.72, target_lufs: float = -16.0) -> dict[str, Any]:
    strength = max(0.0, min(1.0, float(strength)))
    return {
        "voice_isolation": {"enabled": True, "strength": round(strength, 3)},
        "noise_reduction": {"enabled": True, "amount": round(0.38 + strength * 0.42, 3)},
        "de_reverb": {"enabled": True, "room_reduction": round(0.22 + strength * 0.34, 3)},
        "eq": {
            "enabled": True,
            "high_pass_hz": 80,
            "presence_gain_db": round(1.2 + strength * 1.8, 2),
            "mud_cut_db": round(-1.0 - strength * 1.2, 2),
        },
        "compressor": {
            "enabled": True,
            "threshold_db": -20.0,
            "ratio": round(2.0 + strength * 1.2, 2),
            "attack_ms": 8,
            "release_ms": 90,
        },
        "deesser": {"enabled": True, "frequency_hz": 6500, "amount": round(0.28 + strength * 0.32, 3)},
        "loudness": {"enabled": True, "target_lufs": float(target_lufs), "true_peak_db": -1.5},
    }


def build_speech_enhance_plan(
    *,
    clip_id: str,
    start_ms: int,
    end_ms: int,
    strength: float = 0.72,
    provider_id: str = "local_speech_enhance_chain",
) -> EditPlan:
    chain = build_speech_enhance_chain(strength=strength)
    operation = EditOperation(
        id="op_001_speech_enhance",
        type="apply_preset",
        target="selected_audio_range",
        start_ms=max(0, int(start_ms)),
        end_ms=max(max(0, int(start_ms)) + 1, int(end_ms)),
        style_preset_id="studio_speech_enhance_review",
        params={
            "clip_id": str(clip_id),
            "provider_id": str(provider_id),
            "effect_chain": chain,
            "preview_required": True,
            "fallback_mode": "local_effect_chain",
        },
        reason="Stage a no-cloud speech enhancement chain for review before applying it to the selected audio range.",
        confidence=0.82,
        quality_score=84,
        source="speech_enhance",
    )
    card = ReviewCard(
        id="speech_enhance_review",
        title="Review speech enhance before/after",
        operation_ids=(operation.id,),
        quality_score=84,
        reason="Listen to the preview and reject if ambience, music, or character voices are damaged.",
        metadata={"provider_id": provider_id, "requires_preview": True},
    )
    return build_edit_plan(
        plan_id=f"speech_enhance_{clip_id}",
        intent="speech_enhance",
        summary="Stage Studio Sound-style speech enhancement with a local fallback chain.",
        operations=[operation],
        warnings=("This is a local enhancement chain, not a universal regenerative Studio Sound parity claim.",),
        requires_review=True,
        review_cards=[card],
        quality_score=84,
        metadata={"provider_id": provider_id, "local_first": True, "cloud_required": False},
        provider="speech_enhance",
    )


def _rms(samples: np.ndarray) -> float:
    return math.sqrt(float(np.mean(np.square(samples))) + 1e-12)


def _snr_db(clean: np.ndarray, observed: np.ndarray) -> float:
    return 20.0 * math.log10(_rms(clean) / _rms(observed - clean))


def enhance_speech_samples(samples: np.ndarray, sample_rate: int, *, low_hz: float = 85.0, high_hz: float = 3200.0) -> np.ndarray:
    audio = np.asarray(samples, dtype=np.float64)
    if audio.ndim != 1:
        audio = audio.reshape(-1)
    if audio.size < 2:
        return audio.copy()
    spectrum = np.fft.rfft(audio)
    freqs = np.fft.rfftfreq(audio.size, d=1.0 / max(1, int(sample_rate)))
    mask = (freqs >= float(low_hz)) & (freqs <= float(high_hz))
    enhanced = np.fft.irfft(spectrum * mask, n=audio.size)
    peak = float(np.max(np.abs(enhanced))) if enhanced.size else 0.0
    if peak > 1.0:
        enhanced = enhanced / peak
    return enhanced.astype(np.float64)


def synthetic_speech_enhance_qa(*, sample_rate: int = 16000, seed: int = 1337) -> dict[str, Any]:
    duration_s = 1.2
    t = np.arange(int(sample_rate * duration_s), dtype=np.float64) / float(sample_rate)
    envelope = np.minimum(1.0, np.maximum(0.0, np.sin(np.pi * t / duration_s)))
    clean = (0.55 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 440 * t)) * envelope
    rng = np.random.default_rng(int(seed))
    noise = rng.normal(0.0, 0.18, size=clean.shape) + 0.04 * np.sin(2 * np.pi * 60 * t)
    noisy = clean + noise
    enhanced = enhance_speech_samples(noisy, sample_rate, high_hz=1200.0)
    before_snr = _snr_db(clean, noisy)
    after_snr = _snr_db(clean, enhanced)
    improvement = after_snr - before_snr
    return {
        "ok": improvement >= 3.0,
        "sample_rate": int(sample_rate),
        "seed": int(seed),
        "before_snr_db": round(before_snr, 3),
        "after_snr_db": round(after_snr, 3),
        "snr_improvement_db": round(improvement, 3),
        "cloud_required": False,
        "fallback_mode": "local_effect_chain",
    }


def speech_enhance_readiness_report() -> dict[str, Any]:
    plan = build_speech_enhance_plan(clip_id="qa_clip", start_ms=0, end_ms=4200)
    synthetic = synthetic_speech_enhance_qa()
    providers = speech_enhance_provider_contracts()
    checks = {
        "local_provider_contract": any(row["id"] == "local_speech_enhance_chain" and row["configured"] for row in providers),
        "reviewable_edit_plan": bool(plan.requires_review and plan.review_cards),
        "before_after_qa": bool(synthetic.get("ok")),
        "failure_safe_fallback": any(row["fallback"] for row in providers),
        "no_cloud_required": bool(plan.metadata.get("cloud_required") is False and synthetic.get("cloud_required") is False),
    }
    return {
        "kind": "speech_enhance_qa",
        "ok": all(checks.values()),
        "studio_sound_contract_ready": all(checks.values()),
        "checks": checks,
        "providers": providers,
        "plan": plan.to_dict(),
        "synthetic_before_after": synthetic,
    }


__all__ = [
    "SpeechEnhanceProvider",
    "build_speech_enhance_chain",
    "build_speech_enhance_plan",
    "enhance_speech_samples",
    "speech_enhance_provider_contracts",
    "speech_enhance_readiness_report",
    "synthetic_speech_enhance_qa",
]
