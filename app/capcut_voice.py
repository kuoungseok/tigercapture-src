"""CapCut-style captions and voice workflow contracts.

This module keeps the default path local-first.  It does not pretend that a
cloud TTS/custom voice service is configured; instead it exposes provider
slots, ready local operations, and clear unavailable-provider messaging so the
UI can feel like a real creator workflow without hiding gaps.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


@dataclass(frozen=True)
class VoiceProvider:
    id: str
    label: str
    kind: str
    configured: bool
    requires_network: bool
    local_first: bool
    supports: tuple[str, ...]
    description: str
    setup_hint: str = ""


BUILTIN_VOICE_PROVIDERS: tuple[VoiceProvider, ...] = (
    VoiceProvider(
        "local_transcript_import",
        "Transcript / SRT import",
        "caption",
        True,
        False,
        True,
        ("srt", "webvtt", "plain_text", "korean", "english"),
        "Build caption rows from imported transcript text without network access.",
    ),
    VoiceProvider(
        "caption_style_engine",
        "Caption style engine",
        "caption_style",
        True,
        False,
        True,
        ("word_pop", "karaoke", "short_safe_area", "burn_in"),
        "Applies CapCut-like caption style presets and beat metadata locally.",
    ),
    VoiceProvider(
        "voice_cleanup_chain",
        "Voice cleanup chain",
        "cleanup",
        True,
        False,
        True,
        ("enhance_voice", "reduce_noise", "dialogue_cleanup"),
        "Routes voice enhancement and cleanup presets through the local audio pipeline.",
    ),
    VoiceProvider(
        "loudness_shortform",
        "Short-form loudness",
        "loudness",
        True,
        False,
        True,
        ("integrated_lufs", "true_peak_guard", "shortform_target"),
        "Normalizes creator exports to short-form loudness defaults.",
    ),
    VoiceProvider(
        "local_stem_separation",
        "Local stem separation",
        "stem",
        True,
        False,
        True,
        ("vocal_music_split", "music_bed_ducking", "review_sidecar"),
        "Uses local separation routes when dependencies are present and keeps sidecar fallbacks.",
    ),
    VoiceProvider(
        "system_tts_slot",
        "System TTS slot",
        "tts",
        False,
        False,
        True,
        ("tts", "voiceover", "preview"),
        "Optional local TTS hook for machines that have a supported system voice backend.",
        "Install or enable a local TTS backend before generating synthetic voiceover.",
    ),
    VoiceProvider(
        "custom_voice_slot",
        "Custom voice slot",
        "custom_voice",
        False,
        True,
        False,
        ("voice_clone", "brand_voice", "provider_token"),
        "Optional provider slot for future custom voice integrations.",
        "Configure an explicit provider before using custom voice features.",
    ),
    VoiceProvider(
        "voice_translate_slot",
        "Voice translate slot",
        "translation",
        False,
        True,
        False,
        ("translate", "dub", "multilingual_review"),
        "Optional provider slot for translated dubbing workflows.",
        "Configure a provider and review language rights before translation/dubbing.",
    ),
)


def _bundle_from_input(
    bundle_or_summary: Mapping[str, Any] | None,
    media_items: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    source = _as_dict(bundle_or_summary)
    if any(key in source for key in ("project_settings_patch", "subtitle_rows", "caption_beat_plan", "render_queue_jobs")):
        return dict(source)
    try:
        from app.capcut_workflow import capcut_creator_apply_bundle

        return capcut_creator_apply_bundle(source, list(media_items or _as_list(source.get("media_items"))))
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "summary": source,
            "subtitle_rows": [],
            "caption_beat_plan": {},
            "render_queue_jobs": [],
        }


def voice_provider_contracts(
    configured_providers: Mapping[str, bool] | None = None,
    *,
    include_unconfigured: bool = True,
) -> list[dict[str, Any]]:
    """Return deterministic local-first voice provider contracts."""
    overrides = dict(configured_providers or {})
    providers: list[dict[str, Any]] = []
    for provider in BUILTIN_VOICE_PROVIDERS:
        row = asdict(provider)
        if provider.id in overrides:
            row["configured"] = bool(overrides[provider.id])
        if row["configured"] or include_unconfigured:
            row["status"] = "configured" if row["configured"] else "needs_setup"
            if not row["configured"]:
                row["warning"] = row.get("setup_hint") or "Provider is not configured."
            providers.append(row)
    try:
        from app.tts_setup import capcut_voice_tts_provider_row

        tts_row = capcut_voice_tts_provider_row()
        if tts_row["id"] in overrides:
            tts_row["configured"] = bool(overrides[tts_row["id"]])
            tts_row["status"] = "configured" if tts_row["configured"] else "needs_setup"
            tts_row["warning"] = "" if tts_row["configured"] else tts_row.get("setup_hint", "")
        if tts_row.get("configured") or include_unconfigured:
            providers.append(tts_row)
    except Exception:
        if include_unconfigured:
            providers.append(
                {
                    "id": "style_bert_vits2_sidecar",
                    "label": "Style-Bert-VITS2 local TTS",
                    "kind": "tts",
                    "configured": False,
                    "requires_network": False,
                    "local_first": True,
                    "supports": ("tts", "anime_voiceover", "character_narration"),
                    "description": "Local anime/subculture voice generation sidecar.",
                    "setup_hint": "Install or connect Style-Bert-VITS2 before generating character voiceover.",
                    "status": "needs_setup",
                    "warning": "Install or connect the local TTS sidecar first.",
                }
            )
    return providers


def capcut_voice_manifest(
    bundle_or_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
    *,
    language: str = "auto",
    configured_providers: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Build the serializable payload a UI/apply layer can review."""
    bundle = _bundle_from_input(bundle_or_summary, media_items)
    summary = _as_dict(bundle.get("summary") or bundle_or_summary)
    try:
        from app.capcut_workflow import capcut_auto_caption_plan, capcut_caption_beat_plan, capcut_voice_tool_plan

        caption_plan = capcut_auto_caption_plan(summary, language=language)
        beat_plan = _as_dict(bundle.get("caption_beat_plan")) or capcut_caption_beat_plan(summary)
        voice_plan = capcut_voice_tool_plan(summary)
    except Exception as exc:
        caption_plan = {"ok": False, "error": str(exc), "style_preset_ids": []}
        beat_plan = {"ok": False, "beats": [], "beat_count": 0}
        voice_plan = {"ok": False, "tools": [], "preset_ids": []}

    subtitle_rows = _as_list(bundle.get("subtitle_rows"))
    providers = voice_provider_contracts(configured_providers)
    configured = [row for row in providers if row.get("configured")]
    network_defaults = [row for row in configured if row.get("requires_network")]
    cleanup_presets = [
        str(row.get("preset_id"))
        for row in _as_list(voice_plan.get("tools"))
        if row.get("ready") and row.get("preset_id")
    ]
    return {
        "kind": "capcut_voice_manifest",
        "ok": True,
        "ready": bool(subtitle_rows and cleanup_presets),
        "language": language,
        "subtitle_rows": subtitle_rows,
        "subtitle_row_count": len(subtitle_rows),
        "caption_plan": caption_plan,
        "caption_beats": beat_plan,
        "voice_plan": voice_plan,
        "cleanup_preset_ids": cleanup_presets,
        "providers": providers,
        "provider_count": len(providers),
        "configured_provider_count": len(configured),
        "network_provider_count": len(network_defaults),
        "operations": [
            {"id": "apply_caption_rows", "ready": bool(subtitle_rows), "count": len(subtitle_rows)},
            {"id": "apply_caption_beats", "ready": bool(_as_list(beat_plan.get("beats"))), "count": int(beat_plan.get("beat_count", 0) or 0)},
            {"id": "apply_voice_cleanup", "ready": bool(cleanup_presets), "preset_ids": cleanup_presets},
            {"id": "review_optional_voice_providers", "ready": True, "count": len([row for row in providers if not row.get("configured")])},
        ],
    }


def capcut_voice_workflow_model(
    bundle_or_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
    *,
    language: str = "auto",
    configured_providers: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Build the product-facing caption/voice panel model."""
    bundle = _bundle_from_input(bundle_or_summary, media_items)
    summary = _as_dict(bundle.get("summary") or bundle_or_summary)
    manifest = capcut_voice_manifest(
        bundle,
        language=language,
        configured_providers=configured_providers,
    )
    providers = _as_list(manifest.get("providers"))
    configured = [row for row in providers if _as_dict(row).get("configured")]
    optional = [row for row in providers if not _as_dict(row).get("configured")]
    subtitle_rows = _as_list(manifest.get("subtitle_rows"))
    beats = _as_list(_as_dict(manifest.get("caption_beats")).get("beats"))
    voice_plan = _as_dict(manifest.get("voice_plan"))
    cleanup_tools = [row for row in _as_list(voice_plan.get("tools")) if _as_dict(row).get("ready")]
    tts_slots = [row for row in providers if _as_dict(row).get("kind") in {"tts", "custom_voice", "translation"}]
    no_cloud_default = all(not _as_dict(row).get("requires_network") for row in configured)
    optional_messages = all(bool(_as_dict(row).get("warning")) for row in optional)
    checks = {
        "caption_rows_ready": bool(subtitle_rows),
        "caption_beats_ready": bool(beats),
        "voice_cleanup_ready": any(_as_dict(row).get("id") == "enhance_voice" for row in cleanup_tools),
        "noise_reduction_ready": any(_as_dict(row).get("id") == "reduce_noise" for row in cleanup_tools),
        "stem_separation_ready": any(_as_dict(row).get("id") == "stem_separation" for row in cleanup_tools),
        "provider_contracts_present": len(providers) >= 8,
        "configured_local_providers": len([row for row in configured if _as_dict(row).get("local_first")]) >= 5,
        "optional_provider_messages_present": optional_messages,
        "no_cloud_required_by_default": no_cloud_default,
    }
    score = round(100 * sum(1 for value in checks.values() if value) / max(1, len(checks)), 2)
    cards = [
        {
            "id": "caption_import",
            "kind": "caption",
            "label": "Captions",
            "ready": checks["caption_rows_ready"],
            "accent": "#6EA8FF",
            "summary": f"{len(subtitle_rows)} caption row(s), language={language}",
            "rows": subtitle_rows[:8],
        },
        {
            "id": "caption_beats",
            "kind": "caption_beats",
            "label": "Caption beats",
            "ready": checks["caption_beats_ready"],
            "accent": "#FFDD55",
            "summary": f"{len(beats)} beat(s), style={_as_dict(manifest.get('caption_beats')).get('default_style_id', '')}",
            "rows": beats[:8],
        },
        {
            "id": "voice_cleanup",
            "kind": "audio",
            "label": "Voice cleanup",
            "ready": checks["voice_cleanup_ready"] and checks["noise_reduction_ready"],
            "accent": "#5BE7C4",
            "summary": f"{len(cleanup_tools)} local voice tool(s)",
            "rows": cleanup_tools,
        },
        {
            "id": "tts_custom_voice",
            "kind": "provider",
            "label": "TTS / custom voice",
            "ready": any(_as_dict(row).get("configured") for row in tts_slots),
            "accent": "#B46CFF",
            "summary": "Optional providers are explicit; none are used silently.",
            "rows": tts_slots,
        },
        {
            "id": "local_first_safety",
            "kind": "safety",
            "label": "Local-first safety",
            "ready": checks["no_cloud_required_by_default"] and checks["optional_provider_messages_present"],
            "accent": "#FF6F61",
            "summary": "Cloud voice features stay off until a provider is configured.",
            "rows": [
                {"id": "no_cloud_default", "ready": no_cloud_default},
                {"id": "optional_messages", "ready": optional_messages, "count": len(optional)},
            ],
        },
    ]
    actions = [
        {"id": "apply_caption_voice_workflow", "label": "Apply captions + voice cleanup", "enabled": checks["caption_rows_ready"] and checks["voice_cleanup_ready"]},
        {"id": "open_caption_editor", "label": "Open caption editor", "enabled": bool(subtitle_rows or summary.get("has_audio"))},
        {"id": "configure_voice_provider", "label": "Configure optional voice provider", "enabled": bool(optional), "count": len(optional)},
        {"id": "preview_voice_mix", "label": "Preview voice mix", "enabled": bool(cleanup_tools)},
    ]
    ready_card_count = sum(1 for card in cards if card.get("ready"))
    enabled_action_count = sum(1 for action in actions if action.get("enabled"))
    return {
        "kind": "capcut_voice_workflow",
        "ok": all(checks.values()),
        "ready": score >= 85 and checks["caption_rows_ready"] and checks["voice_cleanup_ready"],
        "score": score,
        "checks": checks,
        "cards": cards,
        "card_count": len(cards),
        "ready_card_count": ready_card_count,
        "actions": actions,
        "provider_count": len(providers),
        "configured_provider_count": len(configured),
        "manifest": manifest,
        "summary": {
            "subtitle_rows": len(subtitle_rows),
            "caption_beats": len(beats),
            "voice_cleanup_tools": len(cleanup_tools),
            "ready_card_count": ready_card_count,
            "enabled_action_count": enabled_action_count,
            "manifest_operations": len(_as_list(manifest.get("operations"))),
            "provider_count": len(providers),
            "configured_provider_count": len(configured),
            "optional_provider_count": len(optional),
            "tts_slot_count": len(tts_slots),
            "cloud_required": not no_cloud_default,
        },
    }
