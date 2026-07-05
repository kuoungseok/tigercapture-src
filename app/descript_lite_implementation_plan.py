"""Implementation backlog for Descript-lite work with a thin editor adapter.

The goal of this module is not to implement the features directly. It keeps the
work ordered and machine-checkable so new Descript-lite behavior lands in small
services, models, providers, and panels instead of making VideoEditorWindow
larger.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VIDEO_EDITOR_WINDOW_PATH = "app/video_editor_window.py"


@dataclass(frozen=True)
class ImplementationItem:
    id: str
    priority: int
    area: str
    title: str
    goal: str
    primary_modules: tuple[str, ...]
    acceptance: tuple[str, ...]
    adapter_policy: str = "No new feature logic in VideoEditorWindow; expose a small service/action API first."
    phase: str = "descript_lite"

    def touches_video_editor_window(self) -> bool:
        return VIDEO_EDITOR_WINDOW_PATH in self.primary_modules

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "priority": int(self.priority),
            "phase": self.phase,
            "area": self.area,
            "title": self.title,
            "goal": self.goal,
            "primary_modules": list(self.primary_modules),
            "acceptance": list(self.acceptance),
            "adapter_policy": self.adapter_policy,
            "touches_video_editor_window": self.touches_video_editor_window(),
        }


IMPLEMENTATION_ITEMS: tuple[ImplementationItem, ...] = (
    ImplementationItem(
        id="transcript_state_and_reflow",
        priority=1,
        area="P1 text-based timeline editing",
        title="Transcript state and post-cut reflow",
        goal="Persist editable transcript words/segments and reflow timings after reviewed ripple cuts.",
        primary_modules=("app/transcript_document.py", "app/transcript_reflow.py", "app/ai_edit_plan.py"),
        acceptance=(
            "Reviewed cut result returns a revised transcript document.",
            "Deleted ranges remove or trim affected words and segments.",
            "Undo restores both timeline and transcript sidecar state through the existing history boundary.",
        ),
    ),
    ImplementationItem(
        id="transcript_timeline_operations",
        priority=2,
        area="P1 text-based timeline editing",
        title="Transcript-to-timeline operation service",
        goal="Convert transcript delete, move, and selected-range edits into validated timeline operations.",
        primary_modules=("app/transcript_timeline_ops.py", "app/ai_text_editing.py", "app/automation_commands.py"),
        acceptance=(
            "Word/sentence deletion produces reviewed video/audio ripple-cut intents.",
            "Sentence move produces clip split/move intents without mutating editor widgets directly.",
            "Automation can dry-run the same operations for AI/local agents.",
        ),
    ),
    ImplementationItem(
        id="selection_scoped_effects",
        priority=3,
        area="P1 text-based timeline editing",
        title="Selection-scoped captions, zooms, and highlights",
        goal="Let selected transcript text target only that media range for captions, auto zoom, callouts, and emphasis.",
        primary_modules=("app/transcript_selection_actions.py", "app/ai_text_editing.py", "app/ai_edit_apply.py"),
        acceptance=(
            "Selected text maps to exact start/end media ranges.",
            "Caption, zoom, and highlight operations carry source transcript ids.",
            "Partial apply can apply only selected scoped operations.",
        ),
    ),
    ImplementationItem(
        id="word_asr_and_script_cleanup",
        priority=4,
        area="P2 transcription quality",
        title="Word-level ASR, diarization, and script cleanup providers",
        goal="Turn imported media into an immediately editable script with word timings, speakers, punctuation, paragraphs, and glossary repair.",
        primary_modules=("app/transcription_providers.py", "app/transcript_cleanup.py", "app/local_ml.py"),
        acceptance=(
            "Provider returns TranscriptWord rows for Korean/English mixed media.",
            "Speaker labels and paragraph boundaries survive JSON roundtrip.",
            "Glossary corrections are reported as reviewable transcript changes.",
        ),
    ),
    ImplementationItem(
        id="retake_and_mistake_cleanup",
        priority=5,
        area="P3 one-click cleanup",
        title="Retake, repeated-line, and false-start cleanup",
        goal="Detect repeated takes and common mistake patterns, then produce reviewed cut candidates that change the timeline when applied.",
        primary_modules=("app/retake_detection.py", "app/ai_text_editing.py", "app/ai_edit_apply.py"),
        acceptance=(
            "Repeated sentence clusters keep one best take and mark older takes for removal.",
            "False starts and restart phrases produce review cards with confidence and rationale.",
            "Cleanup preview can apply filler, silence, retake, and mistake operations independently.",
        ),
    ),
    ImplementationItem(
        id="speech_enhance_provider",
        priority=6,
        area="P4 Studio Sound-grade audio",
        title="Speech enhancement provider path",
        goal="Add a speech-enhance route with denoise, dereverb, voice isolation, loudness, and before/after QA evidence.",
        primary_modules=("app/speech_enhance.py", "app/audio_workflow.py", "tools/qa_speech_enhance.py"),
        acceptance=(
            "Provider output is optional and never hides fallback chain state.",
            "Before/after QA reports noise floor, loudness, clipping, and speech clarity metrics.",
            "Sound Editor and automation consume the same provider contract.",
        ),
    ),
    ImplementationItem(
        id="sentence_tts_replacement",
        priority=7,
        area="P5 AI voice and replacement",
        title="Sentence-level TTS replacement",
        goal="Regenerate only the edited sentence and place the generated voice clip through reviewed timeline replacement.",
        primary_modules=("app/ai_voice_replacement.py", "app/capcut_voice.py", "app/audio_workflow.py"),
        acceptance=(
            "Edited transcript sentence creates a replacement recording cue.",
            "Generated audio is staged as a reviewable replacement clip.",
            "Voice clone/custom voice remains blocked unless consent metadata exists.",
        ),
    ),
    ImplementationItem(
        id="ai_review_change_list",
        priority=8,
        area="P6 AI co-editor UX",
        title="Structured AI change list and preview model",
        goal="Show AI results as grouped changes with preview, partial apply, and undo-friendly operation ids.",
        primary_modules=("app/ai_review_model.py", "app/ai_script_edit_panel.py", "app/creator_assist_panel.py"),
        acceptance=(
            "Plans are grouped into cut, caption, zoom, audio, and render changes.",
            "Each group can preview, apply, skip, or explain its operations.",
            "Review model is panel-owned and editor-agnostic.",
        ),
    ),
    ImplementationItem(
        id="collaboration_post_descript_lite",
        priority=9,
        area="P7 collaboration and cloud",
        title="Post-Descript-lite collaboration track",
        goal="Keep share links, comments, version history, and team workspace out of the P1-P5 critical path.",
        primary_modules=("app/collaboration_review.py", "app/project_versions.py", "app/capcut_cloud_handoff.py"),
        acceptance=(
            "Full Descript replacement remains blocked until collaboration surfaces exist.",
            "Local-first Descript-lite can ship without team workspace claims.",
            "Cloud features require explicit opt-in and redaction rules.",
        ),
        phase="post_descript_lite",
    ),
)


def build_descript_lite_implementation_plan() -> dict[str, Any]:
    items = [item.to_dict() for item in IMPLEMENTATION_ITEMS]
    violations = [item for item in items if item["touches_video_editor_window"]]
    return {
        "kind": "descript_lite_implementation_plan",
        "ok": not violations,
        "video_editor_window_policy": {
            "path": VIDEO_EDITOR_WINDOW_PATH,
            "rule": "Do not add new Descript-lite feature logic here. Use services/actions/providers/panels first; keep any final editor hook thin.",
            "allowed_touch": "Only a final adapter call, signal hookup, or dependency injection when no existing action/panel bridge can carry it.",
        },
        "items": items,
        "summary": {
            "items": len(items),
            "descript_lite_items": sum(1 for item in items if item["phase"] == "descript_lite"),
            "post_descript_lite_items": sum(1 for item in items if item["phase"] == "post_descript_lite"),
            "video_editor_window_primary_touches": len(violations),
            "first_item": items[0]["id"] if items else "",
        },
        "violations": violations,
    }


__all__ = [
    "IMPLEMENTATION_ITEMS",
    "VIDEO_EDITOR_WINDOW_PATH",
    "build_descript_lite_implementation_plan",
]
