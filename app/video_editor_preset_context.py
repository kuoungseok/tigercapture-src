from __future__ import annotations

from pathlib import Path

from app.audio_tracks import is_audio_path, is_video_path, probe_audio_duration_ms
from app.video_editor_media_proxy import _probe_video_dimensions

def _project_summary_for_presets(self) -> dict:
        try:
            media_paths = [Path(p) for p in self._media_pool.items()]
        except Exception:
            media_paths = []
        media_items = [p.name.casefold() for p in media_paths]
        names = " ".join(media_items)
        suffixes: dict[str, int] = {}
        video_count = 0
        audio_count = 0
        actor_count = 0
        media_duration_ms = 0
        vertical_votes = 0
        horizontal_votes = 0
        try:
            from app.media_pool import _probe_duration_ms as _probe_media_duration_ms
        except Exception:
            _probe_media_duration_ms = None
        for path in media_paths:
            suffix = path.suffix.casefold()
            suffixes[suffix] = suffixes.get(suffix, 0) + 1
            if is_video_path(path):
                video_count += 1
                w, h = _probe_video_dimensions(path)
                if w > 0 and h > 0:
                    if h > w:
                        vertical_votes += 1
                    else:
                        horizontal_votes += 1
            elif is_audio_path(path):
                audio_count += 1
            elif suffix in {".json", ".atlas", ".skel", ".moc3"}:
                actor_count += 1
            try:
                if callable(_probe_media_duration_ms):
                    media_duration_ms = max(media_duration_ms, int(_probe_media_duration_ms(path) or 0))
                elif is_audio_path(path):
                    media_duration_ms = max(media_duration_ms, int(probe_audio_duration_ms(path) or 0))
            except Exception:
                pass
        max_ms = max(
            [
                int(getattr(track, "duration_ms", 0) or 0)
                + int(getattr(track, "offset_ms", 0) or 0)
                for track in getattr(self, "_tracks", [])
            ] or [0]
        )
        max_ms = max(max_ms, media_duration_ms)
        has_audio_tracks = any(getattr(track, "clips", None) for track in getattr(self, "_audio_tracks", []) or [])
        has_video_tracks = any(getattr(track, "clips", None) for track in getattr(self, "_tracks", []) or [])
        duration_s = max_ms / 1000.0 if max_ms else 60.0
        return {
            "duration_s": duration_s,
            "shortform": duration_s <= 90.0,
            "vertical": vertical_votes > horizontal_votes or "vertical" in names or "short" in names,
            "media_count": len(media_paths),
            "video_count": video_count,
            "audio_count": audio_count,
            "actor_count": actor_count,
            "suffixes": suffixes,
            "has_audio": audio_count > 0 or has_audio_tracks,
            "audio_only": (audio_count > 0 or has_audio_tracks) and not (video_count > 0 or has_video_tracks),
            "gameplay": any(word in names for word in ("game", "capture", "play", "stream")),
            "dialogue": any(word in names for word in ("voice", "dialogue", "podcast", "talk")),
            "tutorial": any(word in names for word in ("tutorial", "howto", "guide", "step")),
            "product": any(word in names for word in ("product", "demo", "review", "shop")),
            "review": "review" in names or "compare" in names,
            "broll": "broll" in names or "b-roll" in names or "cutaway" in names,
            "reaction": "reaction" in names or "meme" in names,
            "live2d": "live2d" in names,
            "spine": "spine" in names,
        }

def _template_entry_condition_ok(self, entry: dict) -> bool:
        condition = str(entry.get("condition", "always") or "always")
        if condition in {"", "always"}:
            return True
        try:
            summary = self._project_summary_for_presets()
        except Exception:
            summary = {}
        if condition == "if_video":
            return bool(summary.get("video_count") or any(getattr(t, "clips", None) for t in getattr(self, "_tracks", []) or []))
        if condition == "if_audio":
            return bool(summary.get("has_audio") or any(getattr(t, "clips", None) for t in getattr(self, "_audio_tracks", []) or []))
        if condition == "if_vertical":
            return bool(summary.get("vertical"))
        if condition == "if_shortform":
            return bool(summary.get("shortform"))
        return True

def _preset_apply_failure_reason(self, preset) -> str:
    if preset is None:
        return "\ud504\ub9ac\uc14b \uc815\ubcf4\uac00 \ube44\uc5b4 \uc788\uc2b5\ub2c8\ub2e4."
    kind = str(getattr(preset, "kind", "") or "")
    if kind == "template":
        try:
            from app.preset_library import preset_by_id, template_sequence

            checked = 0
            blocked: list[str] = []
            for entry in template_sequence(preset):
                condition_ok = getattr(self, "_template_entry_condition_ok", None)
                if callable(condition_ok):
                    ok = condition_ok(entry)
                else:
                    ok = _template_entry_condition_ok(self, entry)
                if not ok:
                    continue
                child = preset_by_id(entry.get("preset_id", ""))
                checked += 1
                if child is None:
                    blocked.append(f"\ub204\ub77d\ub41c child preset: {entry.get('preset_id', '')}")
                    continue
                prev_mode = getattr(self, "_workflow_target_mode", None)
                self._workflow_target_mode = str(entry.get("target", "auto") or "auto")
                try:
                    reason = self._preset_apply_failure_reason(child)
                finally:
                    if prev_mode is None:
                        try:
                            delattr(self, "_workflow_target_mode")
                        except Exception:
                            pass
                    else:
                        self._workflow_target_mode = prev_mode
                if not reason:
                    return ""
                blocked.append(reason)
            if checked <= 0:
                return "\ud604\uc7ac \ud504\ub85c\uc81d\ud2b8 \uc870\uac74\uacfc \ub9de\ub294 \ud15c\ud50c\ub9bf \ub2e8\uacc4\uac00 \uc5c6\uc2b5\ub2c8\ub2e4."
            return blocked[0] if blocked else ""
        except Exception:
            return "\ud15c\ud50c\ub9bf child preset\uc744 \ud574\uc11d\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4."
    if kind in {"effect", "transition"}:
        track, clip = self._workflow_target_video_clip()
        if track is None or clip is None:
            return "\ube44\ub514\uc624 \ud074\ub9bd \ub610\ub294 \ud65c\uc131 \ube44\ub514\uc624 \ud2b8\ub799\uc744 \uba3c\uc800 \uc120\ud0dd\ud558\uc138\uc694."
    elif kind in {"title", "caption_style", "sticker", "motion"}:
        track, _clip = self._workflow_target_video_clip()
        if track is None:
            track = self._active_track()
        if track is None:
            return "\ube44\ub514\uc624 \ud2b8\ub799\uc774 \ud544\uc694\ud569\ub2c8\ub2e4."
    elif kind == "audio":
        if self._audio_workspace_candidate() is None:
            return "\uc624\ub514\uc624 \ud074\ub9bd \ub610\ub294 \uc624\ub514\uc624 \ud2b8\ub799\uc744 \uba3c\uc800 \uc120\ud0dd\ud558\uc138\uc694."
    elif kind == "color":
        target_node = getattr(self, "_node_grade_target", None)
        has_node_grade = target_node is not None and getattr(target_node, "color_grade", None) is not None
        has_active_track = self._active_track() is not None
        if not has_node_grade and not has_active_track:
            return "\uc0c9\ubcf4\uc815\uc744 \uc801\uc6a9\ud560 \ud074\ub9bd\uc774 \ud544\uc694\ud569\ub2c8\ub2e4."
    elif kind == "actor":
        payload = dict(getattr(preset, "payload", {}) or {})
        actor_kind = str(payload.get("actor_kind", "") or "")
        if actor_kind == "live2d" and not hasattr(self, "_live2d_actor_tracks"):
            return "Live2D actor timeline is not available."
        if actor_kind == "spine" and not hasattr(self, "_spine_actor_tracks"):
            return "Spine actor timeline is not available."
        if actor_kind not in {"live2d", "spine"}:
            return "Actor preset has an unknown actor_kind."
    elif not kind:
        return "\ud504\ub9ac\uc14b kind\uac00 \ube44\uc5b4 \uc788\uc2b5\ub2c8\ub2e4."
    return ""

def _preset_apply_failure_message(self, preset, fallback: str = "Select a compatible target first") -> str:
    reason = self._preset_apply_failure_reason(preset)
    return f"{fallback}: {reason}" if reason else fallback
