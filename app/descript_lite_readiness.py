"""Descript-lite readiness gates for TigerCapture.

This report is narrower than general AI edit quality. It answers a product
question: can TigerCapture honestly claim a Descript-lite workflow yet, and what
must happen next to defend higher pricing?
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Any


DESCRIPT_LITE_PRIORITY_ORDER = (
    "text_based_timeline_editing",
    "transcription_quality",
    "one_click_cleanup",
    "studio_sound_audio",
    "ai_voice_replacement",
    "ai_coeditor_ux",
    "collaboration_cloud",
)


@dataclass(frozen=True)
class ReadinessCheck:
    id: str
    label: str
    ready: bool
    evidence: str
    action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "ready": bool(self.ready),
            "evidence": self.evidence,
            "action": self.action,
        }


@dataclass(frozen=True)
class ReadinessArea:
    id: str
    order: int
    label: str
    checks: tuple[ReadinessCheck, ...]
    claim_threshold: int = 90
    must_have_for_descript_lite: bool = False
    must_have_for_price_defense: bool = False

    def score(self) -> int:
        if not self.checks:
            return 0
        return int(round(sum(1 for check in self.checks if check.ready) / len(self.checks) * 100))

    def blockers(self) -> tuple[str, ...]:
        return tuple(check.id for check in self.checks if not check.ready)

    def next_actions(self) -> tuple[str, ...]:
        out: list[str] = []
        seen: set[str] = set()
        for check in self.checks:
            if check.ready or not check.action:
                continue
            key = check.action.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(check.action)
        return tuple(out)

    def to_dict(self) -> dict[str, Any]:
        score = self.score()
        claim_ready = score >= int(self.claim_threshold) and not self.blockers()
        return {
            "id": self.id,
            "order": int(self.order),
            "label": self.label,
            "score": score,
            "state": "claim_ready" if claim_ready else "attention" if score >= 50 else "blocked",
            "claim_ready": bool(claim_ready),
            "claim_threshold": int(self.claim_threshold),
            "must_have_for_descript_lite": bool(self.must_have_for_descript_lite),
            "must_have_for_price_defense": bool(self.must_have_for_price_defense),
            "checks": [check.to_dict() for check in self.checks],
            "blockers": list(self.blockers()),
            "next_actions": list(self.next_actions()),
        }


def _has_symbol(module_name: str, symbol: str) -> bool:
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return False
    return hasattr(module, symbol)


def _allowed_operation(operation_type: str) -> bool:
    try:
        from app.ai_edit_plan import ALLOWED_OPERATION_TYPES
    except Exception:
        return False
    return str(operation_type) in ALLOWED_OPERATION_TYPES


def _file_contains(root: Path, path: str, needles: Iterable[str]) -> bool:
    file_path = root / path
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return all(needle in text for needle in needles)


def _report_bool(root: Path, path: str, key: str) -> bool:
    file_path = root / path
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(payload.get(key))


def _area_text_based_timeline(root: Path) -> ReadinessArea:
    return ReadinessArea(
        id="text_based_timeline_editing",
        order=1,
        label="1. Text-based editing becomes real timeline editing",
        must_have_for_descript_lite=True,
        must_have_for_price_defense=True,
        checks=(
            ReadinessCheck(
                "transcript_word_model",
                "Transcript model can carry word-level timings",
                _has_symbol("app.ai_edit_plan", "TranscriptWord"),
                "TranscriptWord exists in app.ai_edit_plan.",
            ),
            ReadinessCheck(
                "text_selection_to_time_range",
                "Text selection maps to media time",
                _has_symbol("app.ai_text_editing", "text_range_to_time_range"),
                "text_range_to_time_range maps segment character ranges to media ranges.",
            ),
            ReadinessCheck(
                "selection_delete_ripple_plan",
                "Deleting transcript text creates a ripple-cut plan",
                _has_symbol("app.ai_text_editing", "plan_text_range_cut") and _allowed_operation("ripple_cut_text_range"),
                "plan_text_range_cut emits allowed ripple_cut_text_range operations.",
            ),
            ReadinessCheck(
                "reviewed_video_audio_ripple_cut",
                "Reviewed cuts materialize to video and audio ripple cuts",
                _has_symbol("app.ai_edit_apply", "apply_ai_script_cut_intents_to_tracks"),
                "apply_ai_script_cut_intents_to_tracks mutates video/audio tracks after review.",
            ),
            ReadinessCheck(
                "automation_reviewed_cuts",
                "Automation/AI can request reviewed cut materialization",
                _file_contains(root, "app/automation_commands.py", ("apply_reviewed_cuts", "Materialize reviewed AI cut ranges")),
                "Automation registry exposes destructive reviewed cuts behind requires_review.",
            ),
            ReadinessCheck(
                "sentence_move_to_clip_move",
                "Moving script sentences moves linked timeline clips",
                _has_symbol("app.transcript_timeline_ops", "build_sentence_move_clip_move_intents"),
                "transcript_timeline_ops builds timeline.split + clip.move_linked intents outside VideoEditorWindow.",
                "Wire these intents into the panel/action adapter and timeline preview.",
            ),
            ReadinessCheck(
                "selection_caption_zoom_highlight",
                "Selected text can target only that range for captions/zoom/highlight",
                _has_symbol("app.transcript_selection_actions", "build_selection_scoped_edit_plan"),
                "transcript_selection_actions creates scoped create_subtitles, add_auto_zoom, and add_callout plans.",
                "Expose selection-scoped actions in the panel-owned transcript editor.",
            ),
            ReadinessCheck(
                "transcript_auto_reorder",
                "Transcript reorders automatically after destructive edits",
                _has_symbol("app.transcript_reflow", "reflow_transcript_after_cuts"),
                "transcript_reflow returns revised TranscriptDocument timings after reviewed cut ranges.",
                "Persist the revised transcript document from the panel/action adapter after materialized cuts.",
            ),
            ReadinessCheck(
                "undo_redo_cut_apply",
                "Text-driven destructive edits are one undoable timeline operation",
                _file_contains(
                    root,
                    "app/video_editor_ai_workflow.py",
                    ("def _apply_ai_script_edit_cuts", "_register_change(\"AI Script Edit ripple cuts\")"),
                )
                and _file_contains(
                    root,
                    "app/video_editor_history_workflow.py",
                    ("capture_editor_snapshot", "self._history.push"),
                ),
                "Focused AI workflow materializes reviewed cuts and records one editor history snapshot.",
            ),
            ReadinessCheck(
                "panel_owned_transcript_editor",
                "Panel-owned transcript editor surface",
                _has_symbol("app.transcript_edit_surface", "TranscriptEditSurface")
                and _file_contains(
                    root,
                    "app/ai_script_edit_panel.py",
                    ("select_transcript_range", "generate_selection_scoped_plan", "build_sentence_move_preview", "apply_transcript_reflow"),
                ),
                "ScriptEditPanelModel owns transcript selection, scoped edit plans, sentence move preview, and transcript reflow without VideoEditorWindow feature logic.",
                "Add richer visible word/sentence controls and diff affordances in the panel, keeping the same model API.",
            ),
        ),
    )


def _area_transcription(root: Path) -> ReadinessArea:
    return ReadinessArea(
        id="transcription_quality",
        order=2,
        label="2. Transcription quality and editable script generation",
        must_have_for_descript_lite=True,
        must_have_for_price_defense=True,
        checks=(
            ReadinessCheck("srt_vtt_import", "SRT/VTT import", _has_symbol("app.ai_text_editing", "parse_transcript_text"), "SRT/VTT import helpers exist."),
            ReadinessCheck("word_timestamp_model", "Word-level timestamp data model", _has_symbol("app.ai_edit_plan", "TranscriptWord"), "Transcript words are part of the model."),
            ReadinessCheck("speaker_field_model", "Speaker field in transcript segments", _file_contains(root, "app/ai_edit_plan.py", ("speaker:", "words:")), "TranscriptSegment stores speaker and words."),
            ReadinessCheck("local_media_transcription_entry", "Media import can request local speech recognition", _file_contains(root, "app/ai_script_edit_panel.py", ("import_transcript_from_media_path", "Local speech recognition")), "Script Edit exposes local speech recognition entry points."),
            ReadinessCheck("whisperx_word_engine", "Whisper/WhisperX-grade word-level engine route", _file_contains(root, "app/local_ml.py", ("word_timestamps=True", "'words': words")) and _has_symbol("app.transcription_providers", "segments_to_word_timed_document"), "Local faster-whisper route requests word timestamps and the provider contract builds TranscriptWord rows.", "Add local model/runtime evidence before claiming automatic media-to-editable-script quality."),
            ReadinessCheck("speaker_diarization_engine", "Speaker diarization provider contract", _has_symbol("app.transcription_providers", "assign_speaker_labels"), "Speaker turns can be imported/assigned to transcript segments; optional pyannote/speechbrain slots are reported.", "Wire a real local diarization runtime or import sidecar before stronger speaker-separation claims."),
            ReadinessCheck("punctuation_paragraph_cleanup", "Punctuation and paragraph cleanup", _has_symbol("app.transcript_cleanup", "cleanup_transcript_document"), "Transcript cleanup restores sentence punctuation and paragraph metadata.", "Tune punctuation restoration against real Korean/English creator transcripts."),
            ReadinessCheck("mixed_language_glossary", "Korean/English game/broadcast glossary correction", _file_contains(root, "app/transcript_cleanup.py", ("DEFAULT_GLOSSARY", "OBS", "Live2D")), "Editable glossary correction covers mixed Korean/English creator terms.", "Make the glossary user-editable in the panel/settings UI."),
            ReadinessCheck("runtime_transcription_model_evidence", "Local ASR runtime/model evidence", _report_bool(root, "debugCapture/descript_lite_p2_transcription_qa.json", "runtime_model_ready"), "The current environment must prove a local word-timestamp ASR model is available.", "Run tools/configure_local_whisper_model.py --model-path <folder>, use an existing local Hugging Face cache model, or ship an approved local model bundle, then rerun tools/qa_descript_lite_p2_transcription.py."),
        ),
    )


def _area_one_click_cleanup(root: Path) -> ReadinessArea:
    return ReadinessArea(
        id="one_click_cleanup",
        order=3,
        label="3. One-click cleanup that changes the result",
        must_have_for_descript_lite=True,
        must_have_for_price_defense=True,
        checks=(
            ReadinessCheck("filler_word_plan", "Filler word removal plan", _has_symbol("app.ai_text_editing", "plan_remove_filler_words"), "Korean/English starter filler detector emits delete ranges."),
            ReadinessCheck("silence_plan", "Silence removal plan", _has_symbol("app.ai_text_editing", "plan_remove_silences"), "Silence intervals can produce delete ranges."),
            ReadinessCheck("clean_tutorial_recipe", "Clean tutorial one-click recipe", _has_symbol("app.ai_text_editing", "clean_tutorial"), "clean_tutorial combines cleanup, captions, chapters, and zoom staging."),
            ReadinessCheck("cleanup_materializes_cuts", "Cleanup plans can materialize reviewed ripple cuts", _has_symbol("app.ai_edit_apply", "apply_ai_script_cut_intents_to_tracks"), "Reviewed delete ranges can change the timeline."),
            ReadinessCheck("retake_detection", "Remove retakes / repeated takes", _has_symbol("app.retake_detection", "detect_retake_candidates"), "Retake clustering and best-take selection produce reviewed cut candidates.", "Add audio-confidence and ASR-aware scoring after word-level transcription lands."),
            ReadinessCheck("mistake_repeat_detection", "Repeated/mistake segment detection", _has_symbol("app.retake_detection", "detect_mistake_candidates"), "Restart phrases and repeated adjacent phrases produce reviewed cut candidates.", "Tune phrase dictionaries with real Korean/English creator corpus."),
            ReadinessCheck("immediate_review_preview", "Preview and partial apply before mutation", _file_contains(root, "app/ai_script_edit_panel.py", ("apply_selected_requested", "apply_cuts_requested", "selected_operation_ids")), "Script Edit exposes review and partial apply controls."),
        ),
    )


def _area_studio_sound(root: Path) -> ReadinessArea:
    return ReadinessArea(
        id="studio_sound_audio",
        order=4,
        label="4. Studio Sound-grade audio",
        must_have_for_price_defense=True,
        checks=(
            ReadinessCheck("noise_reduction", "Noise reduction controls", _file_contains(root, "app/audio_workflow.py", ("noise_reduction", "dialogue_cleanup_effects")), "dialogue_cleanup_effects exposes noise reduction."),
            ReadinessCheck("dereverb", "Reverb/room tone reduction", _file_contains(root, "app/audio_workflow.py", ("de_reverb", "dialogue_cleanup_effects")), "dialogue cleanup has de_reverb payloads."),
            ReadinessCheck("loudness", "Automatic loudness targets", _has_symbol("app.audio_workflow", "loudness_target"), "Podcast/shortform/broadcast loudness targets exist."),
            ReadinessCheck("eq_comp_deesser", "EQ/compressor/de-esser presets", _file_contains(root, "app/audio_workflow.py", ("eq", "compressor", "deesser")), "Audio workflow and Sound Editor expose EQ/dynamics/de-esser chains."),
            ReadinessCheck("speech_enhance_contract", "Speech enhance / voice isolation contract", _has_symbol("app.speech_enhance", "build_speech_enhance_plan") and _file_contains(root, "app/audio_workflow.py", ("voice_isolation", "dialogue_cleanup")), "Speech enhance plans and voice-isolation graph contracts exist."),
            ReadinessCheck("regenerative_studio_sound", "Regenerative Studio Sound-quality enhancement", _report_bool(root, "debugCapture/speech_enhance_qa.json", "studio_sound_contract_ready"), "Speech enhance QA must prove before/after improvement and a failure-safe local fallback.", "Run tools/qa_speech_enhance.py and review before/after evidence before making stronger Studio Sound-style claims."),
        ),
    )


def _area_ai_voice(root: Path) -> ReadinessArea:
    return ReadinessArea(
        id="ai_voice_replacement",
        order=5,
        label="5. AI voice and replacement recording",
        must_have_for_price_defense=True,
        checks=(
            ReadinessCheck("tts_provider_slots", "TTS provider slots", _file_contains(root, "app/capcut_voice.py", ("system_tts_slot", "System TTS slot", "\"tts\"")), "CapCut voice workflow exposes TTS slots."),
            ReadinessCheck("adr_cues", "ADR/replacement recording cues", _has_symbol("app.audio_workflow", "ADRCue"), "ADRCue models replacement recording ranges."),
            ReadinessCheck("sentence_regenerate", "Regenerate only an edited sentence", _has_symbol("app.ai_voice_replacement", "build_sentence_voice_replacement_plan") and _allowed_operation("replace_audio_range") and _report_bool(root, "debugCapture/ai_voice_replacement_qa.json", "ai_voice_replacement_contract_ready"), "Edited transcript sentences can become reviewed replace_audio_range plans with ADR fallback.", "Run tools/qa_ai_voice_replacement.py and wire the reviewed operation to the timeline/audio adapter."),
            ReadinessCheck("voice_clone_consent", "Voice clone consent/legal UI", _has_symbol("app.ai_voice_replacement", "voice_clone_consent_contract") and _report_bool(root, "debugCapture/ai_voice_replacement_qa.json", "ai_voice_replacement_contract_ready"), "Custom voice generation is blocked unless explicit consent metadata is present.", "Surface the consent contract in UI before enabling custom voice providers."),
            ReadinessCheck("translation_dubbing", "Translation dubbing workflow", _file_contains(root, "app/capcut_voice.py", ("translation", "dub")), "Translation/dub provider slots exist but are not claim-ready."),
        ),
    )


def _area_ai_coeditor(root: Path) -> ReadinessArea:
    return ReadinessArea(
        id="ai_coeditor_ux",
        order=6,
        label="6. AI co-editor UX with safe review",
        checks=(
            ReadinessCheck("natural_language_plans", "Natural-language edit prompts", _has_symbol("app.ai_script_edit_panel", "ScriptEditPanelModel"), "Script Edit routes prompts to deterministic/provider plans."),
            ReadinessCheck("provider_direct_generation", "Configured LLM/agent direct generation", _file_contains(root, "debugCapture/ai_edit_corpus_quality_qa.json", ("\"effective\": \"claude_mcp\"", "\"corpus_direct_successes\": 20")), "Latest QA shows Claude direct provider success on the corpus."),
            ReadinessCheck("review_cards", "Review cards and warnings", _file_contains(root, "app/ai_edit_plan.py", ("review_cards", "requires_review")), "EditPlan contract includes review cards and requires_review."),
            ReadinessCheck("partial_apply", "Partial operation apply", _file_contains(root, "app/ai_script_edit_panel.py", ("apply_selected_requested", "selected_operation_ids")), "Script Edit can apply selected operations."),
            ReadinessCheck("no_direct_mutation", "AI cannot mutate timeline directly", _file_contains(root, "app/ai_edit_plan.py", ("FORBIDDEN_EXECUTION_KEYS", "project_mutation")), "Plan validation rejects executable/project mutation fields."),
        ),
    )


def _area_collaboration(root: Path) -> ReadinessArea:
    return ReadinessArea(
        id="collaboration_cloud",
        order=7,
        label="7. Collaboration and cloud workflow",
        checks=(
            ReadinessCheck("local_collab_handoff", "Local collaboration handoff package", _file_contains(root, "app/capcut_collaboration.py", ("collab", "handoff")), "Local collab handoff contract exists."),
            ReadinessCheck("cloud_handoff_contract", "Cloud/share handoff contract", _file_contains(root, "app/capcut_cloud_handoff.py", ("cloud", "handoff")), "Cloud/share handoff package contract exists."),
            ReadinessCheck("share_link_service", "Project share links", False, "No hosted project share-link service exists.", "Design explicit opt-in share links with privacy/redaction rules."),
            ReadinessCheck("comments_review", "Comments and review threads", False, "No timeline comment/review thread product surface is complete.", "Add timeline comments, review status, and local/offline roundtrip package QA."),
            ReadinessCheck("version_history", "Version history", False, "Crash/autosave exists elsewhere, but product version history is not complete.", "Add named versions and compare/restore UX."),
            ReadinessCheck("team_workspace", "Team workspace", False, "No team workspace/account model is in scope yet.", "Keep this post-Descript-lite unless paid collaboration becomes a target."),
        ),
    )


def _build_areas(root: Path) -> tuple[ReadinessArea, ...]:
    return (
        _area_text_based_timeline(root),
        _area_transcription(root),
        _area_one_click_cleanup(root),
        _area_studio_sound(root),
        _area_ai_voice(root),
        _area_ai_coeditor(root),
        _area_collaboration(root),
    )


def build_descript_lite_readiness_report(root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root)
    areas = [area.to_dict() for area in _build_areas(root_path)]
    area_by_id = {str(row["id"]): row for row in areas}
    descript_lite_required = [
        area_by_id["text_based_timeline_editing"],
        area_by_id["transcription_quality"],
        area_by_id["one_click_cleanup"],
    ]
    price_defense_required = [
        *descript_lite_required,
        area_by_id["studio_sound_audio"],
        area_by_id["ai_voice_replacement"],
    ]
    descript_lite_ready = all(bool(row.get("claim_ready")) for row in descript_lite_required)
    price_defense_ready = all(bool(row.get("claim_ready")) for row in price_defense_required)
    next_actions: list[str] = []
    for row in areas:
        if row.get("claim_ready"):
            continue
        for action in list(row.get("next_actions") or [])[:2]:
            next_actions.append(f"{row['label']}: {action}")
        if next_actions:
            break
    priority_scores = {str(row["id"]): int(row.get("score", 0) or 0) for row in areas}
    overall_score = int(round(sum(priority_scores.values()) / max(1, len(priority_scores))))
    return {
        "kind": "descript_lite_readiness",
        "ok": True,
        "priority_order": list(DESCRIPT_LITE_PRIORITY_ORDER),
        "descript_lite_claim_ready": bool(descript_lite_ready),
        "price_149_plus_defense_ready": bool(price_defense_ready),
        "score": overall_score,
        "areas": areas,
        "summary": {
            "areas": len(areas),
            "claim_ready": sum(1 for row in areas if row.get("claim_ready")),
            "descript_lite_required_ready": sum(1 for row in descript_lite_required if row.get("claim_ready")),
            "price_defense_required_ready": sum(1 for row in price_defense_required if row.get("claim_ready")),
            "lowest_priority_blocker": next((row["id"] for row in areas if not row.get("claim_ready")), ""),
        },
        "next_actions": next_actions,
        "positioning": {
            "safe_now": "AI Script Edit MVP with reviewed apply, transcript-driven cuts, cleanup, and local corpus evidence.",
            "descript_lite_gate": "Do not claim Descript-lite until priorities 1-3 are claim_ready.",
            "price_defense_gate": "Do not use $149+ Descript-style value defense until priorities 1-5 are claim_ready.",
        },
    }


__all__ = [
    "DESCRIPT_LITE_PRIORITY_ORDER",
    "build_descript_lite_readiness_report",
]
