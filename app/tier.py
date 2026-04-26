"""Single source of truth for Pro / Free tier gating.

All UI gating must go through :func:`is_locked` (or :func:`is_pro`)
rather than checking license state directly. When the real license
check lands, only :func:`is_pro` changes — every existing gate then
flips automatically.

Feature ids are short stable strings (``"export.quality.high"``,
``"export.length.over_60s"``). Register them in :data:`PRO_FEATURES`.
Anything not registered is implicitly Free.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
#  License check (currently a stub — always Pro)
# ---------------------------------------------------------------------------


def is_pro() -> bool:
    """Return True when the current user has a Pro license.

    For now this always returns True so the app behaves identically to
    pre-tier builds. When the licensing module lands, replace the body
    with the real check. Do not call license code from anywhere else."""
    return True


# ---------------------------------------------------------------------------
#  Feature registry
# ---------------------------------------------------------------------------


PRO_FEATURES: set[str] = {
    # Export quality presets above the Free ceiling.
    "export.quality.high",
    "export.quality.best",
    # Video container/codec formats. Free can only output MP4
    # (H.264/AAC) — WebM (VP9) and MOV (H.264-in-MOV) are Pro.
    "export.format.webm",
    "export.format.mov",
    # Audio export formats. Free covers MP3 + WAV — the lossless,
    # vendor-specific, and less-common formats are Pro.
    "export.audio.flac",
    "export.audio.alac",
    "export.audio.aac",
    "export.audio.ogg",
    # Audio quality presets above the Free ceiling. Standard (44.1kHz
    # / 192 kbps / 16-bit) is the Free default; High and Studio are
    # the Pro tiers (48 kHz, 320 kbps, 24-bit; 96 kHz lossless).
    "export.audio_quality.high",
    "export.audio_quality.studio",
    # Typography overlays in the exported file. Free users keep the
    # full preview/editor experience but the rendered MP4/WebM/MOV
    # ships without text overlays — the editor warns them on export.
    "export.typography",
    # Color grading presets above the Free baseline. Free users keep
    # all five sliders + a few neutral preset shortcuts (Cool / Warm)
    # so they can still grade by hand; the curated "designed look"
    # presets (Cinematic / Vintage / Faded / B&W / Punch / Mute) are
    # the Pro upsell.
    "color.preset.cinematic",
    "color.preset.vintage",
    "color.preset.faded",
    "color.preset.bw",
    "color.preset.punch",
    "color.preset.mute",
}


def is_locked(feature_id: str) -> bool:
    """True when ``feature_id`` is Pro-only and the user is not Pro.
    Unknown ids are treated as Free (always unlocked)."""
    return feature_id in PRO_FEATURES and not is_pro()


def requires_pro(feature_id: str) -> bool:
    """True when ``feature_id`` is registered as Pro-gated. Independent
    of the user's license — useful for rendering the PRO badge on items
    even when the current user can use them."""
    return feature_id in PRO_FEATURES
