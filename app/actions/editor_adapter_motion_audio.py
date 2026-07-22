"""Motion Designer audio-reactive, Composer, and Voice Lab action adapter."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.motion_designer.audio_analysis import AudioAnalysisCache, analysis_is_current, analyze_audio
from app.motion_designer.audio_reactive import (
    AudioReactiveBinding, bake_audio_reactive, compile_binding, layer_bindings, set_layer_bindings,
)
from app.motion_designer.commands import find_layer
from app.motion_designer.composer_bridge import import_composer_timing
from app.motion_designer.voice_bridge import import_voice_timing


AUDIO_ANALYSIS_KEY = "audio_analysis"


class MotionAudioAdapterMixin:
    """Focused action surface layered over MotionAdapterMixin's shared store."""

    def _motion_composition_for_audio(self, composition_id: str):
        composition = self._motion_store().get(str(composition_id or ""))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return composition

    def _commit_motion_audio_change(self, composition) -> None:
        composition.revision += 1
        self._motion_sync_owner()

    def motion_audio_analyze(self, *, composition_id: str, source_path: str,
                             timeline_start_ms: int = 0, trim_start_ms: int = 0,
                             duration_ms: int | None = None, source_revision: str = "",
                             hop_ms: int = 20, force: bool = False) -> dict[str, Any]:
        composition = self._motion_composition_for_audio(composition_id)
        caches = dict(composition.metadata.get(AUDIO_ANALYSIS_KEY) or {})
        for row in caches.values():
            if not isinstance(row, Mapping):
                continue
            cache = AudioAnalysisCache.from_dict(row)
            same_window = (
                cache.timeline_start_ms == max(0, int(timeline_start_ms))
                and cache.trim_start_ms == max(0, int(trim_start_ms))
                and (duration_ms is None or abs(cache.duration_ms - int(duration_ms)) <= cache.hop_ms)
            )
            if not force and same_window and analysis_is_current(cache, source_path, source_revision):
                return self._audio_analysis_result(cache, reused=True)
        cache = analyze_audio(
            source_path, timeline_start_ms=timeline_start_ms, trim_start_ms=trim_start_ms,
            duration_ms=duration_ms, source_revision=source_revision, hop_ms=hop_ms,
        )
        caches[cache.id] = cache.to_dict()
        composition.metadata[AUDIO_ANALYSIS_KEY] = caches
        self._commit_motion_audio_change(composition)
        return self._audio_analysis_result(cache, reused=False)

    @staticmethod
    def _audio_analysis_result(cache: AudioAnalysisCache, *, reused: bool) -> dict[str, Any]:
        return {
            "changed": not reused, "reused": reused, "analysis_id": cache.id,
            "source_path": cache.source_path, "source_signature": cache.source_signature,
            "duration_ms": cache.duration_ms, "hop_ms": cache.hop_ms,
            "sample_count": len(cache.samples), "beat_markers": list(cache.beat_markers),
            "estimated_bpm": cache.estimated_bpm,
        }

    def _motion_analysis(self, composition, analysis_id: str) -> AudioAnalysisCache:
        row = (composition.metadata.get(AUDIO_ANALYSIS_KEY) or {}).get(str(analysis_id or ""))
        if not isinstance(row, Mapping):
            raise ValueError(f"motion audio analysis not found: {analysis_id}")
        cache = AudioAnalysisCache.from_dict(row)
        if not analysis_is_current(cache, cache.source_path, cache.source_revision):
            raise ValueError("motion audio analysis is stale; run motion.audio.analyze again")
        return cache

    def motion_audio_reactive_bind(self, *, composition_id: str, layer_id: str,
                                   analysis_id: str, binding: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_composition_for_audio(composition_id)
        layer = find_layer(composition, layer_id)
        cache = self._motion_analysis(composition, analysis_id)
        item = AudioReactiveBinding.from_dict({**dict(binding), "analysis_id": analysis_id})
        item = compile_binding(item, cache)
        bindings = layer_bindings(layer)
        bindings.append(item)
        set_layer_bindings(layer, bindings)
        self._commit_motion_audio_change(composition)
        return {"changed": True, "binding": item.to_dict(), "binding_count": len(bindings)}

    def motion_audio_reactive_update(self, *, composition_id: str, layer_id: str,
                                     binding_id: str, changes: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_composition_for_audio(composition_id)
        layer = find_layer(composition, layer_id)
        bindings = layer_bindings(layer)
        index = next((i for i, item in enumerate(bindings) if item.id == binding_id), -1)
        if index < 0:
            raise ValueError(f"audio reactive binding not found: {binding_id}")
        item = AudioReactiveBinding.from_dict({**bindings[index].to_dict(), **dict(changes), "id": binding_id})
        cache = self._motion_analysis(composition, item.analysis_id)
        item = compile_binding(item, cache)
        bindings[index] = item
        set_layer_bindings(layer, bindings)
        self._commit_motion_audio_change(composition)
        return {"changed": True, "binding": item.to_dict(), "binding_count": len(bindings)}

    def motion_audio_reactive_bake(self, *, composition_id: str, layer_id: str,
                                   sample_fps: float | None = None) -> dict[str, Any]:
        composition = self._motion_composition_for_audio(composition_id)
        layer = find_layer(composition, layer_id)
        binding_count = len(layer_bindings(layer))
        keyframe_count = bake_audio_reactive(composition, layer, sample_fps=sample_fps)
        if not keyframe_count:
            raise ValueError("layer has no audio reactive bindings")
        self._commit_motion_audio_change(composition)
        return {"changed": True, "binding_count": binding_count, "keyframe_count": keyframe_count,
                "sample_fps": float(sample_fps or composition.fps)}

    def motion_composer_import_timing(self, *, composition_id: str, music_composition_id: str = "",
                                      music: Mapping[str, Any] | None = None,
                                      timeline_start_ms: int = 0) -> dict[str, Any]:
        composition = self._motion_composition_for_audio(composition_id)
        source: Any = music
        if source is None:
            store = self._music_store()
            source = store.get(str(music_composition_id or ""))
        if source is None:
            raise ValueError(f"music composition not found: {music_composition_id}")
        timing = import_composer_timing(composition, source, timeline_start_ms=timeline_start_ms)
        self._commit_motion_audio_change(composition)
        return {"changed": True, "timing": timing, "beat_count": len(timing["beat_markers"]),
                "note_count": len(timing["note_events"])}

    def motion_voice_import_timing(self, *, composition_id: str,
                                   rows: Sequence[Mapping[str, Any]], timeline_start_ms: int = 0,
                                   text_layer_id: str = "", actor_layer_id: str = "") -> dict[str, Any]:
        composition = self._motion_composition_for_audio(composition_id)
        text_layer = find_layer(composition, text_layer_id) if text_layer_id else None
        actor_layer = find_layer(composition, actor_layer_id) if actor_layer_id else None
        timing = import_voice_timing(
            composition, rows, timeline_start_ms=timeline_start_ms,
            text_layer=text_layer, actor_layer=actor_layer,
        )
        self._commit_motion_audio_change(composition)
        return {"changed": True, "timing": timing, "sentence_count": len(timing["sentences"]),
                "word_count": len(timing["words"]), "phoneme_count": len(timing["phonemes"])}


__all__ = ["MotionAudioAdapterMixin"]
