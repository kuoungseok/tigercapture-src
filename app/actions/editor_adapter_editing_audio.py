"""Domain slice of editing action adapter methods."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from pathlib import Path
from typing import Any

from app.actions.editor_adapter_scalars import _bool, _float, _int



class EditingAudioAdapterMixin:
    """Focused action adapter methods split from EditingAdapterMixin."""

    def split_audio_clip(self, *, track_id: int, clip_id: int, at_ms: int) -> dict[str, Any]:
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            project_ms = max(0, _int(at_ms))
            start = _int(getattr(clip, "offset_ms", 0))
            end = start + _int(getattr(clip, "effective_length_ms", 0))
            if project_ms <= start or project_ms >= end:
                raise ValueError("split point must be strictly inside the audio clip")
            source_ms = _int(getattr(clip, "trim_start_ms", 0)) + (project_ms - start)
            right = copy.deepcopy(clip)
            right.id = self._next_audio_clip_id()
            right.offset_ms = project_ms
            right.trim_start_ms = source_ms
            right.trim_end_ms = _int(getattr(clip, "effective_trim_end_ms", 0))
            clip.trim_end_ms = source_ms
            track.clips.append(right)
            track.clips.sort(key=lambda row: _int(getattr(row, "offset_ms", 0)))
            self._update_audio_track(track)
            self._after_timeline_mutation("Action split audio clip")
            return {
                "track_id": _int(track_id),
                "at_ms": project_ms,
                "left_clip_id": _int(clip_id),
                "right_clip_id": _int(getattr(right, "id", 0)),
                "clip_count_after": len(getattr(track, "clips", []) or []),
            }

    def trim_audio_clip(
            self,
            *,
            track_id: int,
            clip_id: int,
            trim_start_ms: int | None = None,
            trim_end_ms: int | None = None,
        ) -> dict[str, Any]:
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            old = {
                "offset_ms": _int(getattr(clip, "offset_ms", 0)),
                "trim_start_ms": _int(getattr(clip, "trim_start_ms", 0)),
                "trim_end_ms": _int(getattr(clip, "effective_trim_end_ms", 0)),
            }
            max_out = max(1, _int(getattr(clip, "duration_ms", 0)) or old["trim_end_ms"])
            new_start = old["trim_start_ms"] if trim_start_ms is None else max(0, _int(trim_start_ms))
            new_end = old["trim_end_ms"] if trim_end_ms is None else max(1, _int(trim_end_ms))
            new_start = max(0, min(new_start, max_out - 1))
            new_end = max(new_start + 1, min(new_end, max_out))
            delta = new_start - old["trim_start_ms"]
            clip.trim_start_ms = new_start
            clip.trim_end_ms = new_end
            clip.offset_ms = max(0, old["offset_ms"] + delta)
            track.clips.sort(key=lambda row: _int(getattr(row, "offset_ms", 0)))
            self._update_audio_track(track)
            self._after_timeline_mutation("Action trim audio clip")
            return {
                "track_id": _int(track_id),
                "clip_id": _int(clip_id),
                "old": old,
                "new": {
                    "offset_ms": _int(getattr(clip, "offset_ms", 0)),
                    "trim_start_ms": _int(getattr(clip, "trim_start_ms", 0)),
                    "trim_end_ms": _int(getattr(clip, "effective_trim_end_ms", 0)),
                },
            }

    def delete_audio_clip(self, *, track_id: int, clip_id: int) -> dict[str, Any]:
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            before = len(getattr(track, "clips", []) or [])
            track.clips = [row for row in getattr(track, "clips", []) or [] if row is not clip]
            self._update_audio_track(track)
            self._after_timeline_mutation("Action delete audio clip")
            return {"track_id": _int(track_id), "clip_id": _int(clip_id), "clip_count_before": before, "clip_count_after": len(track.clips)}

    def set_audio_clip_gain(self, *, track_id: int, clip_id: int, gain: float) -> dict[str, Any]:
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            value = max(0.0, min(4.0, _float(gain, 1.0)))
            old = _float(getattr(clip, "gain", 1.0), 1.0)
            clip.gain = value
            self._update_audio_track(track)
            self._after_timeline_mutation("Action set audio clip gain")
            return {"track_id": _int(track_id), "clip_id": _int(clip_id), "old_gain": old, "gain": value}

    def set_audio_track_mix(self, *, track_id: int, volume: float | None = None, pan: float | None = None) -> dict[str, Any]:
            params: dict[str, Any] = {}
            if volume is not None:
                params["volume"] = volume
            if pan is not None:
                params["pan"] = pan
            return self.set_track_state(kind="audio", track_id=track_id, **params)

    def set_audio_track_volume(self, *, track_id: int, volume: float) -> dict[str, Any]:
            return self.set_track_state(kind="audio", track_id=track_id, volume=volume)

    def set_audio_track_pan(self, *, track_id: int, pan: float) -> dict[str, Any]:
            return self.set_track_state(kind="audio", track_id=track_id, pan=pan)

    def set_audio_track_mute(self, *, track_id: int, muted: bool = True) -> dict[str, Any]:
            return self.set_track_mute(kind="audio", track_id=track_id, muted=muted)

    def set_audio_track_solo(self, *, track_id: int, solo: bool = True) -> dict[str, Any]:
            return self.set_track_state(kind="audio", track_id=track_id, solo=solo)

    def _normalize_audio_track_type(self, value: Any) -> str:
            text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
            aliases = {
                "dialog": "dialogue",
                "voice": "dialogue",
                "vox": "dialogue",
                "music_stem": "music",
                "bgm": "music",
                "fx": "sfx",
                "sound_fx": "sfx",
                "amb": "ambience",
                "ambient": "ambience",
                "atmo": "ambience",
            }
            text = aliases.get(text, text)
            return text if text in {"dialogue", "music", "sfx", "ambience"} else text[:24]

    def _normalize_insert_slots(self, slots: Any) -> list[dict[str, Any]]:
            from app.audio_tracks import default_track_insert_slots

            defaults = {str(row["id"]): dict(row) for row in default_track_insert_slots()}
            rows: list[dict[str, Any]] = []
            for row in list(slots or []):
                if not isinstance(row, Mapping):
                    continue
                sid = str(row.get("id") or row.get("slot") or "").strip().lower()
                if not sid:
                    continue
                base = dict(defaults.get(sid, {"id": sid, "label": sid.upper(), "enabled": False, "bypassed": False}))
                base["enabled"] = _bool(row.get("enabled"), bool(base.get("enabled")))
                base["bypassed"] = _bool(row.get("bypassed"), bool(base.get("bypassed")))
                base["label"] = str(row.get("label") or base.get("label") or sid.upper())[:6]
                rows.append(base)
            seen = {str(row.get("id")) for row in rows}
            for sid, row in defaults.items():
                if sid not in seen:
                    rows.append(dict(row))
            return rows

    def _normalize_sends(self, sends: Any) -> dict[str, float]:
            from app.audio_tracks import default_track_sends

            values = default_track_sends()
            if isinstance(sends, Mapping):
                for key, value in sends.items():
                    sid = str(key or "").strip().lower()
                    if not sid:
                        continue
                    values[sid] = max(0.0, min(1.0, _float(value, 0.0)))
            return values

    def set_audio_track_type(self, *, track_id: int, track_type: str) -> dict[str, Any]:
            value = self._normalize_audio_track_type(track_type)
            return self.set_track_state(kind="audio", track_id=track_id, track_type=value)

    def set_audio_track_insert(
            self,
            *,
            track_id: int,
            slot: str,
            enabled: bool | None = None,
            bypassed: bool | None = None,
        ) -> dict[str, Any]:
            track = self._audio_track(track_id)
            slots = self._normalize_insert_slots(getattr(track, "insert_slots", None))
            target = str(slot or "").strip().lower()
            if target in {"dynamics", "dynamic"}:
                target = "dyn"
            if target not in {str(row.get("id")) for row in slots}:
                slots.append({"id": target, "label": target.upper()[:6], "enabled": False, "bypassed": False})
            old = copy.deepcopy(slots)
            for row in slots:
                if str(row.get("id")) != target:
                    continue
                if enabled is not None:
                    row["enabled"] = _bool(enabled)
                if bypassed is not None:
                    row["bypassed"] = _bool(bypassed)
                if enabled is None and bypassed is None:
                    row["enabled"] = not bool(row.get("enabled"))
            track.insert_slots = slots
            self._update_audio_track(track)
            self._after_timeline_mutation("Action set audio track insert")
            return {"track_id": _int(track_id), "slot": target, "old": old, "new": slots}

    def set_audio_track_send_level(self, *, track_id: int, send_id: str, level: float) -> dict[str, Any]:
            track = self._audio_track(track_id)
            sends = self._normalize_sends(getattr(track, "sends", None))
            sid = str(send_id or "").strip().lower()
            if sid in {"rev", "verb"}:
                sid = "reverb"
            if sid in {"dly"}:
                sid = "delay"
            old = dict(sends)
            sends[sid] = max(0.0, min(1.0, _float(level, 0.0)))
            track.sends = sends
            self._update_audio_track(track)
            self._after_timeline_mutation("Action set audio send level")
            return {"track_id": _int(track_id), "send_id": sid, "old": old, "new": dict(sends)}

    def route_audio_track_to_bus(self, *, track_id: int, bus_id: str) -> dict[str, Any]:
            return self.set_track_state(kind="audio", track_id=track_id, bus_id=str(bus_id or "master").strip() or "master")

    def _audio_track_meter_row(self, track: Any, index: int, *, solo_active: bool) -> dict[str, Any]:
            volume = max(0.0, min(1.5, _float(getattr(track, "volume", 1.0), 1.0)))
            pan = max(-1.0, min(1.0, _float(getattr(track, "pan", 0.0), 0.0)))
            audible = not bool(getattr(track, "muted", False)) and (not solo_active or bool(getattr(track, "solo", False)))
            level = 0.0 if not audible else min(1.0, max(0.03, volume * 0.62))
            left = min(1.0, level * (1.0 - max(0.0, pan) * 0.35))
            right = min(1.0, level * (1.0 + min(0.0, pan) * 0.35))
            peak = min(1.0, max(left, right) + (0.12 if volume > 0.82 else 0.06))
            clipped = bool(volume >= 1.18 and audible)
            return {
                "track_id": _int(getattr(track, "id", index + 1), index + 1),
                "level_l": round(left, 4),
                "level_r": round(right, 4),
                "peak_hold": round(peak, 4),
                "clip_led": clipped,
                "audible": audible,
            }

    def audio_track_meter_state(self, *, track_id: int | None = None) -> dict[str, Any]:
            owner = self._require_owner()
            tracks = list(getattr(owner, "_audio_tracks", []) or [])
            solo_active = any(bool(getattr(track, "solo", False)) for track in tracks)
            rows = [
                self._audio_track_meter_row(track, index, solo_active=solo_active)
                for index, track in enumerate(tracks)
                if track_id is None or _int(getattr(track, "id", -1), -1) == _int(track_id)
            ]
            return {
                "schema": "tigerstudio.audio.meter.v1",
                "track_count": len(rows),
                "tracks": rows,
            }

    def audio_automation_state(self, *, track_id: int | None = None) -> dict[str, Any]:
            owner = self._require_owner()
            tracks = list(getattr(owner, "_audio_tracks", []) or [])
            rows: list[dict[str, Any]] = []
            for index, track in enumerate(tracks):
                tid = _int(getattr(track, "id", index + 1), index + 1)
                if track_id is not None and tid != _int(track_id):
                    continue
                lanes = dict(getattr(track, "automation_lanes", {}) or {})
                if getattr(track, "automation_points", None):
                    lanes.setdefault("volume", list(getattr(track, "automation_points", []) or []))
                rows.append(
                    {
                        "track_id": tid,
                        "read": bool(getattr(track, "automation_read", True)),
                        "write": bool(getattr(track, "automation_write", False)),
                        "lanes": lanes,
                        "point_count": sum(len(list(points or [])) for points in lanes.values()),
                    }
                )
            return {"schema": "tigerstudio.audio.automation.v1", "tracks": rows, "track_count": len(rows)}

    def write_audio_automation(
            self,
            *,
            track_id: int,
            parameter: str = "volume",
            time_ms: int | None = None,
            value: float | None = None,
            read: bool | None = None,
            write: bool | None = None,
        ) -> dict[str, Any]:
            track = self._audio_track(track_id)
            old = {
                "automation_read": bool(getattr(track, "automation_read", True)),
                "automation_write": bool(getattr(track, "automation_write", False)),
                "automation_points": copy.deepcopy(list(getattr(track, "automation_points", []) or [])),
                "automation_lanes": copy.deepcopy(dict(getattr(track, "automation_lanes", {}) or {})),
            }
            if read is not None:
                track.automation_read = _bool(read, True)
            if write is not None:
                track.automation_write = _bool(write, False)
            else:
                track.automation_write = True
            parameter_id = str(parameter or "volume").strip().lower()
            if value is not None:
                extent = max(1, _int(getattr(track, "extent_ms", lambda: 1)()))
                norm = max(0.0, min(1.0, _float(time_ms, 0.0) / float(extent)))
                point = [round(norm, 6), _float(value, 1.0)]
                lanes = dict(getattr(track, "automation_lanes", {}) or {})
                lane = list(lanes.get(parameter_id, []) or [])
                lane.append(point)
                lane.sort(key=lambda row: _float(row[0], 0.0))
                lanes[parameter_id] = lane
                track.automation_lanes = lanes
                if parameter_id == "volume":
                    track.automation_points = lane
            self._update_audio_track(track)
            self._after_timeline_mutation("Action write audio automation")
            return {"track_id": _int(track_id), "parameter": parameter_id, "old": old, "new": self.audio_automation_state(track_id=track_id)["tracks"][0]}

    def clear_audio_automation(self, *, track_id: int, parameter: str | None = None) -> dict[str, Any]:
            track = self._audio_track(track_id)
            old = self.audio_automation_state(track_id=track_id)
            parameter_id = str(parameter or "").strip().lower()
            if parameter_id:
                lanes = dict(getattr(track, "automation_lanes", {}) or {})
                lanes.pop(parameter_id, None)
                track.automation_lanes = lanes
                if parameter_id == "volume":
                    track.automation_points = []
            else:
                track.automation_lanes = {}
                track.automation_points = []
                track.automation_write = False
            self._update_audio_track(track)
            self._after_timeline_mutation("Action clear audio automation")
            return {"track_id": _int(track_id), "parameter": parameter_id or "all", "old": old, "new": self.audio_automation_state(track_id=track_id)}

    def _audio_mixer_snapshot_rows(self) -> list[dict[str, Any]]:
            rows: list[dict[str, Any]] = []
            for index, track in enumerate(list(getattr(self._require_owner(), "_audio_tracks", []) or [])):
                rows.append(
                    {
                        "track_id": _int(getattr(track, "id", index + 1), index + 1),
                        "volume": _float(getattr(track, "volume", 1.0), 1.0),
                        "pan": _float(getattr(track, "pan", 0.0), 0.0),
                        "muted": bool(getattr(track, "muted", False)),
                        "solo": bool(getattr(track, "solo", False)),
                        "bus_id": str(getattr(track, "bus_id", "master") or "master"),
                        "track_type": str(getattr(track, "track_type", "") or ""),
                        "insert_slots": copy.deepcopy(list(getattr(track, "insert_slots", []) or [])),
                        "sends": copy.deepcopy(dict(getattr(track, "sends", {}) or {})),
                        "automation_read": bool(getattr(track, "automation_read", True)),
                        "automation_write": bool(getattr(track, "automation_write", False)),
                    }
                )
            return rows

    def _audio_mixer_snapshots(self) -> list[dict[str, Any]]:
            owner = self._require_owner()
            snapshots = getattr(owner, "_audio_mixer_snapshots", None)
            if not isinstance(snapshots, list):
                snapshots = []
                owner._audio_mixer_snapshots = snapshots
            return snapshots

    def save_audio_mixer_snapshot(self, *, snapshot_id: str | None = None, name: str | None = None) -> dict[str, Any]:
            snapshots = self._audio_mixer_snapshots()
            sid = str(snapshot_id or "").strip() or f"mix_{len(snapshots) + 1}"
            row = {
                "id": sid,
                "name": str(name or sid),
                "schema": "tigerstudio.audio.mixer.snapshot.v1",
                "tracks": self._audio_mixer_snapshot_rows(),
            }
            before = len(snapshots)
            snapshots[:] = [snap for snap in snapshots if str(snap.get("id")) != sid]
            snapshots.append(row)
            self._after_timeline_mutation("Action save audio mixer snapshot")
            return {"snapshot": row, "snapshot_count_before": before, "snapshot_count": len(snapshots)}

    def _find_audio_mixer_snapshot(self, snapshot_id: str) -> dict[str, Any]:
            sid = str(snapshot_id or "").strip()
            for row in self._audio_mixer_snapshots():
                if str(row.get("id")) == sid:
                    return row
            raise ValueError(f"audio mixer snapshot not found: {sid}")

    def apply_audio_mixer_snapshot(self, *, snapshot_id: str) -> dict[str, Any]:
            snapshot = self._find_audio_mixer_snapshot(snapshot_id)
            tracks_by_id = {
                _int(getattr(track, "id", -1), -1): track
                for track in list(getattr(self._require_owner(), "_audio_tracks", []) or [])
            }
            applied: list[int] = []
            for row in list(snapshot.get("tracks") or []):
                track = tracks_by_id.get(_int(row.get("track_id"), -1))
                if track is None:
                    continue
                for key in ("volume", "pan", "muted", "solo", "bus_id", "track_type", "insert_slots", "sends", "automation_read", "automation_write"):
                    if key in row:
                        setattr(track, key, copy.deepcopy(row[key]))
                self._update_audio_track(track)
                applied.append(_int(getattr(track, "id", 0)))
            self._after_timeline_mutation("Action apply audio mixer snapshot")
            return {"snapshot_id": str(snapshot_id), "applied_track_ids": applied, "applied_count": len(applied)}

    def compare_audio_mixer_snapshot(self, *, snapshot_id: str) -> dict[str, Any]:
            snapshot = self._find_audio_mixer_snapshot(snapshot_id)
            current = {row["track_id"]: row for row in self._audio_mixer_snapshot_rows()}
            deltas: list[dict[str, Any]] = []
            for row in list(snapshot.get("tracks") or []):
                tid = _int(row.get("track_id"), -1)
                now = current.get(tid)
                if now is None:
                    deltas.append({"track_id": tid, "status": "missing_current"})
                    continue
                changes: dict[str, dict[str, Any]] = {}
                for key in ("volume", "pan", "muted", "solo", "bus_id", "track_type", "insert_slots", "sends", "automation_read", "automation_write"):
                    if now.get(key) != row.get(key):
                        changes[key] = {"snapshot": row.get(key), "current": now.get(key)}
                if changes:
                    deltas.append({"track_id": tid, "changes": changes})
            return {"snapshot_id": str(snapshot_id), "delta_count": len(deltas), "deltas": deltas}

    def audio_mixer_state(self) -> dict[str, Any]:
            owner = self._require_owner()
            tracks = list(getattr(owner, "_audio_tracks", []) or [])
            panel = getattr(owner, "_audio_mixer_panel", None)
            payload = getattr(panel, "mixer_state_payload", None)
            if callable(payload):
                try:
                    row = dict(payload(tracks) or {})
                    row["snapshot_count"] = len(list(getattr(owner, "_audio_mixer_snapshots", []) or []))
                    return row
                except Exception:
                    pass
            solo_active = any(bool(getattr(track, "solo", False)) for track in tracks)
            rows: list[dict[str, Any]] = []
            for index, track in enumerate(tracks):
                meter = self._audio_track_meter_row(track, index, solo_active=solo_active)
                rows.append(
                    {
                        "id": _int(getattr(track, "id", index + 1), index + 1),
                        "index": index,
                        "label": str(getattr(track, "display_name", "") or getattr(track, "label", "") or f"Audio {index + 1}"),
                        "volume": _float(getattr(track, "volume", 1.0), 1.0),
                        "pan": _float(getattr(track, "pan", 0.0), 0.0),
                        "muted": bool(getattr(track, "muted", False)),
                        "solo": bool(getattr(track, "solo", False)),
                        "audible": not bool(getattr(track, "muted", False)) and (not solo_active or bool(getattr(track, "solo", False))),
                        "bus_id": str(getattr(track, "bus_id", "master") or "master"),
                        "track_type": str(getattr(track, "track_type", "") or ""),
                        "insert_slots": self._normalize_insert_slots(getattr(track, "insert_slots", None)),
                        "sends": self._normalize_sends(getattr(track, "sends", None)),
                        "automation": {
                            "read": bool(getattr(track, "automation_read", True)),
                            "write": bool(getattr(track, "automation_write", False)),
                            "point_count": len(list(getattr(track, "automation_points", []) or [])),
                        },
                        "meter": meter,
                        "clip_count": len(list(getattr(track, "clips", []) or [])),
                        "loaded": bool(getattr(track, "is_loaded", False)),
                    }
                )
            return {
                "schema": "tigerstudio.audio.mixer.v1",
                "track_count": len(rows),
                "solo_active": solo_active,
                "snapshot_count": len(list(getattr(owner, "_audio_mixer_snapshots", []) or [])),
                "tracks": rows,
            }

    def sound_editor_jog_shuttle_state(self, *, track_id: int, clip_id: int) -> dict[str, Any]:
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            return self._sound_editor_jog_state(track, clip)

    def set_sound_editor_jog_shuttle(
            self,
            *,
            track_id: int,
            clip_id: int,
            position_ms: int | None = None,
            normalized_position: float | None = None,
            step_ms: int | None = None,
            playing: bool | None = None,
            focus_workbench: bool = True,
        ) -> dict[str, Any]:
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            duration = self._sound_editor_duration_ms(clip)
            old_position = self._sound_editor_position_ms(clip, duration)
            old_playing = bool(getattr(clip, "_se_jog_playing", False))
            next_position = old_position
            if step_ms is not None:
                next_position += _int(step_ms)
            if normalized_position is not None:
                ratio = max(0.0, min(1.0, _float(normalized_position, 0.0)))
                next_position = int(round(ratio * duration))
            if position_ms is not None:
                next_position = _int(position_ms)
            next_position = max(0, min(duration, next_position))

            setattr(clip, "_se_jog_ms", next_position)
            next_playing = old_playing if playing is None else _bool(playing, old_playing)
            setattr(clip, "_se_jog_playing", next_playing)

            ui_updated = self._focus_workbench_sound_editor(
                track,
                clip,
                focus_workbench=_bool(focus_workbench, True),
                position_ms=next_position,
                playing=next_playing,
            )
            state = self._sound_editor_jog_state(track, clip)
            state.update(
                {
                    "old_position_ms": old_position,
                    "old_playing": old_playing,
                    "ui_updated": ui_updated,
                    "changed": old_position != next_position or old_playing != next_playing,
                }
            )
            return state

    def sound_editor_advanced_lab_state(self, *, track_id: int, clip_id: int) -> dict[str, Any]:
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            return self._sound_editor_advanced_lab_state(track, clip)

    def set_sound_editor_advanced_lab(
            self,
            *,
            track_id: int,
            clip_id: int,
            expanded: bool,
            focus_workbench: bool = True,
        ) -> dict[str, Any]:
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            old_expanded = bool(getattr(clip, "_se_advanced_lab_expanded", False))
            next_expanded = _bool(expanded, False)
            legacy_count_before = self._advanced_sound_lab_count()
            setattr(clip, "_se_advanced_lab_expanded", next_expanded)
            ui_updated = self._focus_workbench_sound_editor(
                track,
                clip,
                focus_workbench=_bool(focus_workbench, True),
                advanced_expanded=next_expanded,
            )
            legacy_count_after = self._advanced_sound_lab_count()
            state = self._sound_editor_advanced_lab_state(track, clip)
            state.update(
                {
                    "old_expanded": old_expanded,
                    "ui_updated": ui_updated,
                    "legacy_lab_count_before": legacy_count_before,
                    "legacy_lab_count_after": legacy_count_after,
                    "opened_legacy_window": legacy_count_after > legacy_count_before,
                    "changed": old_expanded != next_expanded,
                }
            )
            return state

    def apply_sound_editor_effects(
            self,
            *,
            track_id: int,
            clip_id: int,
            basic: Mapping[str, Any] | None = None,
            effects: Mapping[str, Any] | None = None,
            merge: bool = True,
            focus_workbench: bool = True,
        ) -> dict[str, Any]:
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            self._ensure_sound_editor_effects(clip, merge=bool(merge))
            if isinstance(basic, Mapping):
                self._apply_sound_editor_basic_values(track, clip, basic)
            if isinstance(effects, Mapping):
                self._merge_sound_editor_effects(clip.effects, effects)
            self._update_audio_track(track)
            ui_updated = self._focus_workbench_sound_editor(
                track,
                clip,
                focus_workbench=_bool(focus_workbench, True),
            )
            self._after_timeline_mutation("Action apply sound editor effects")
            return {
                "track_id": _int(track_id),
                "clip_id": _int(clip_id),
                "basic": self._sound_editor_basic_state(track, clip),
                "effects": copy.deepcopy(getattr(clip, "effects", {}) or {}),
                "ui_updated": ui_updated,
            }

    def apply_sound_editor_ai_preset(
            self,
            *,
            track_id: int,
            clip_id: int,
            preset: str,
            focus_workbench: bool = True,
        ) -> dict[str, Any]:
            presets = {
                "Suno v3": {"air": 5.0, "clarity": 60.0, "warmth": 40.0, "width": 130.0, "punch": 50.0, "excite": 70.0},
                "Suno v4": {"air": 3.0, "clarity": 50.0, "warmth": 30.0, "width": 120.0, "punch": 40.0, "excite": 50.0},
                "Udio": {"air": 4.0, "clarity": 45.0, "warmth": 35.0, "width": 110.0, "punch": 55.0, "excite": 60.0},
                "ACE-Step": {"air": 6.0, "clarity": 55.0, "warmth": 50.0, "width": 140.0, "punch": 45.0, "excite": 75.0},
                "Generic AI": {"air": 4.0, "clarity": 50.0, "warmth": 40.0, "width": 120.0, "punch": 50.0, "excite": 60.0},
                "Custom": {"air": 0.0, "clarity": 0.0, "warmth": 0.0, "width": 100.0, "punch": 0.0, "excite": 0.0},
            }
            name = str(preset or "").strip()
            if name not in presets:
                raise ValueError(f"unknown AI preset: {name}")
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            self._ensure_sound_editor_effects(clip)
            ai = clip.effects.setdefault("ai_master", {})
            ai.update(presets[name])
            ai["preset"] = name
            ai["enabled"] = name != "Custom"
            self._update_audio_track(track)
            ui_updated = self._focus_workbench_sound_editor(
                track,
                clip,
                focus_workbench=_bool(focus_workbench, True),
            )
            self._after_timeline_mutation("Action apply sound editor AI preset")
            return {
                "track_id": _int(track_id),
                "clip_id": _int(clip_id),
                "preset": name,
                "ai_master": copy.deepcopy(ai),
                "ui_updated": ui_updated,
            }

    def audio_loudness_report(
            self,
            *,
            track_id: int,
            clip_id: int,
            target_lufs: float | None = None,
            true_peak_limit_db: float | None = None,
            tolerance_lufs: float = 1.0,
        ) -> dict[str, Any]:
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            loudness = ((getattr(clip, "effects", {}) or {}).get("loudness") or {}) if isinstance(getattr(clip, "effects", None), dict) else {}
            target = _float(target_lufs, _float(loudness.get("target_i", -14.0), -14.0))
            peak_limit = _float(true_peak_limit_db, _float(loudness.get("true_peak", -1.0), -1.0))
            waveform = getattr(clip, "waveform", None)
            try:
                import numpy as np

                arr = np.asarray(waveform, dtype=np.float32)
                if arr.size <= 0:
                    raise ValueError("waveform unavailable")
                if arr.ndim == 2 and arr.shape[0] <= 8:
                    arr = arr.T
                from app.audio_accuracy import audio_signal_diagnostics

                report = audio_signal_diagnostics(
                    arr,
                    target_lufs=target,
                    true_peak_limit_db=peak_limit,
                    tolerance_lufs=_float(tolerance_lufs, 1.0),
                )
                available = True
            except Exception:
                report = {
                    "ok": False,
                    "integrated_lufs": None,
                    "target_lufs": target,
                    "true_peak_dbfs": None,
                    "true_peak_limit_db": peak_limit,
                    "stereo_correlation": None,
                    "warnings": ["waveform unavailable"],
                }
                available = False
            report.update(
                {
                    "schema": "tigerstudio.audio.loudness_report.v1",
                    "track_id": _int(getattr(track, "id", track_id)),
                    "clip_id": _int(getattr(clip, "id", clip_id)),
                    "available": available,
                    "source": "waveform_cache",
                }
            )
            return report

    def export_audio_clip(
            self,
            *,
            track_id: int,
            clip_id: int,
            out_path: str | None = None,
            format: str = "mp3",
            quality_id: str | None = None,
        ) -> dict[str, Any]:
            _track, clip = self._audio_track_and_clip(track_id, clip_id)
            from app.audio_tracks import (
                CLIP_EXPORT_FORMATS,
                DEFAULT_AUDIO_QUALITY_ID,
                build_single_clip_filter,
                get_audio_quality_preset,
            )

            fmt_key = str(format or "").strip().lower() or "mp3"
            if out_path:
                suffix = Path(out_path).suffix.lower()
                for key, spec in CLIP_EXPORT_FORMATS.items():
                    if suffix and suffix == str(spec.get("ext", "")).lower():
                        fmt_key = key
                        break
            if fmt_key not in CLIP_EXPORT_FORMATS:
                raise ValueError(f"unknown audio export format: {fmt_key}")
            filter_graph, output_ms = build_single_clip_filter(clip)
            result = {
                "track_id": _int(track_id),
                "clip_id": _int(clip_id),
                "format": fmt_key,
                "quality_id": str(quality_id or DEFAULT_AUDIO_QUALITY_ID),
                "output_ms": output_ms,
                "filter_graph": filter_graph,
                "exported": False,
            }
            if not out_path:
                return result
            if getattr(clip, "source_path", None) is None:
                raise ValueError("audio clip has no source file")
            if output_ms <= 0:
                raise ValueError("nothing to export")

            import subprocess
            from imageio_ffmpeg import get_ffmpeg_exe
            from app.subprocess_utils import hidden_subprocess_kwargs

            fmt = CLIP_EXPORT_FORMATS[fmt_key]
            output = Path(out_path)
            expected_ext = str(fmt.get("ext", ".mp3"))
            if output.suffix.lower() != expected_ext.lower():
                output = output.with_suffix(expected_ext)
            output.parent.mkdir(parents=True, exist_ok=True)
            quality = get_audio_quality_preset(str(quality_id or DEFAULT_AUDIO_QUALITY_ID))
            cmd = [
                get_ffmpeg_exe(),
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-i", str(getattr(clip, "source_path")),
                "-filter_complex", filter_graph,
                "-map", "[out]",
                "-vn",
                *fmt["codec"](quality),
                str(output),
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                **hidden_subprocess_kwargs(),
            )
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "")[-1500:] or f"ffmpeg exited {proc.returncode}")
            result.update({"exported": True, "out_path": str(output)})
            return result

    def separate_audio_stems(
            self,
            *,
            track_id: int,
            clip_id: int,
            output_root: str | None = None,
            prefer_demucs: bool = True,
            add_to_timeline: bool = True,
        ) -> dict[str, Any]:
            track, clip = self._audio_track_and_clip(track_id, clip_id)
            source = getattr(clip, "source_path", None)
            if source is None:
                raise ValueError("audio clip has no source file")
            from app.audio_separation import planned_separation_method, separate_audio_stems as _separate_audio_stems

            method_hint = planned_separation_method(prefer_demucs=_bool(prefer_demucs, True))
            result = _separate_audio_stems(
                source,
                Path(output_root) if output_root else None,
                prefer_demucs=_bool(prefer_demucs, True),
            )
            added = []
            if _bool(add_to_timeline, True):
                added = self._add_separated_stems_to_timeline(track, clip, result.vocals_path, result.instrumental_path)
                if added:
                    self._after_timeline_mutation("Action separate audio stems")
            return {
                "track_id": _int(track_id),
                "clip_id": _int(clip_id),
                "method_hint": method_hint,
                "method": result.method,
                "note": result.note,
                "vocals_path": str(result.vocals_path),
                "instrumental_path": str(result.instrumental_path),
                "added_tracks": added,
            }

    def _ensure_sound_editor_effects(self, clip: Any, *, merge: bool = True) -> None:
            from app.audio_tracks import default_effects_state

            defaults = default_effects_state()
            if not isinstance(getattr(clip, "effects", None), dict) or not merge:
                clip.effects = copy.deepcopy(defaults)
                return
            for key, value in defaults.items():
                existing = clip.effects.setdefault(key, copy.deepcopy(value))
                if isinstance(existing, dict) and isinstance(value, dict):
                    self._merge_missing_sound_defaults(existing, value)

    def _merge_missing_sound_defaults(self, target: dict[str, Any], defaults: Mapping[str, Any]) -> None:
            for key, value in defaults.items():
                if key not in target:
                    target[key] = copy.deepcopy(value)
                elif isinstance(target.get(key), dict) and isinstance(value, Mapping):
                    self._merge_missing_sound_defaults(target[key], value)

    def _merge_sound_editor_effects(self, target: dict[str, Any], payload: Mapping[str, Any]) -> None:
            from app.audio_tracks import default_effects_state

            defaults = default_effects_state()
            for key, value in payload.items():
                if isinstance(value, Mapping):
                    section = target.setdefault(str(key), copy.deepcopy(defaults.get(str(key), {})))
                    if isinstance(section, dict):
                        self._merge_sound_editor_effects(section, value)
                    else:
                        target[str(key)] = copy.deepcopy(dict(value))
                else:
                    target[str(key)] = copy.deepcopy(value)

    def _apply_sound_editor_basic_values(self, track: Any, clip: Any, basic: Mapping[str, Any]) -> None:
            if "gain" in basic:
                clip.gain = max(0.0, min(4.0, _float(basic.get("gain"), 1.0)))
            elif "gain_db" in basic or "volume_db" in basic:
                db = _float(basic.get("gain_db", basic.get("volume_db")), 0.0)
                clip.gain = max(0.0, min(4.0, 10.0 ** (db / 20.0)))
            if "track_volume_db" in basic:
                track.volume = max(0.0, min(4.0, 10.0 ** (_float(basic.get("track_volume_db"), 0.0) / 20.0)))
            if "fade_in_ms" in basic or "fade_in_s" in basic:
                clip.fade_in_ms = max(0, _int(basic.get("fade_in_ms", _float(basic.get("fade_in_s"), 0.0) * 1000.0)))
            if "fade_out_ms" in basic or "fade_out_s" in basic:
                clip.fade_out_ms = max(0, _int(basic.get("fade_out_ms", _float(basic.get("fade_out_s"), 0.0) * 1000.0)))
            if "speed" in basic:
                setattr(clip, "_se_speed", max(0.1, min(4.0, _float(basic.get("speed"), 1.0))))
            if "pitch" in basic or "pitch_st" in basic:
                setattr(clip, "_se_pitch", max(-24.0, min(24.0, _float(basic.get("pitch", basic.get("pitch_st")), 0.0))))
            if "reverse" in basic:
                setattr(clip, "_se_reverse", _bool(basic.get("reverse"), False))
            if "pan" in basic or "pan_percent" in basic:
                raw_pan = _float(basic.get("pan", basic.get("pan_percent")), 0.0)
                pan = raw_pan / 100.0 if abs(raw_pan) > 1.0 else raw_pan
                pan = max(-1.0, min(1.0, pan))
                setattr(clip, "_se_pan", pan)
                try:
                    setattr(track, "pan", pan)
                except Exception:
                    pass
            if "muted" in basic:
                muted = _bool(basic.get("muted"), False)
                setattr(clip, "_se_muted", muted)
                if muted:
                    setattr(clip, "_se_pre_mute_gain", _float(getattr(clip, "gain", 1.0), 1.0))
                    clip.gain = 0.0
                elif _float(getattr(clip, "gain", 1.0), 1.0) <= 0.001:
                    clip.gain = max(0.01, _float(getattr(clip, "_se_pre_mute_gain", 1.0), 1.0))

    def _sound_editor_basic_state(self, track: Any, clip: Any) -> dict[str, Any]:
            return {
                "gain": _float(getattr(clip, "gain", 1.0), 1.0),
                "track_volume": _float(getattr(track, "volume", 1.0), 1.0),
                "pan": _float(getattr(clip, "_se_pan", getattr(track, "pan", 0.0)), 0.0),
                "fade_in_ms": _int(getattr(clip, "fade_in_ms", 0)),
                "fade_out_ms": _int(getattr(clip, "fade_out_ms", 0)),
                "speed": _float(getattr(clip, "_se_speed", 1.0), 1.0),
                "pitch": _float(getattr(clip, "_se_pitch", 0.0), 0.0),
                "reverse": bool(getattr(clip, "_se_reverse", False)),
                "muted": bool(getattr(clip, "_se_muted", False)) or _float(getattr(clip, "gain", 1.0), 1.0) <= 0.001,
            }

    def _add_separated_stems_to_timeline(
            self,
            source_track: Any,
            source_clip: Any,
            vocals_path: Path,
            instrumental_path: Path,
        ) -> list[dict[str, Any]]:
            owner = self._require_owner()
            from app.audio_tracks import AudioClip, AudioTrack, probe_audio_duration_ms

            tracks = list(getattr(owner, "_audio_tracks", []) or [])
            added: list[dict[str, Any]] = []
            next_clip_id = max(
                (
                    _int(getattr(clip, "id", 0))
                    for track in tracks
                    for clip in getattr(track, "clips", []) or []
                ),
                default=0,
            ) + 1
            for path, label in ((instrumental_path, "Instrumental Stem"), (vocals_path, "Vocal Stem")):
                duration = _int(probe_audio_duration_ms(Path(path)), 0)
                if duration <= 0:
                    duration = max(1, _int(getattr(source_clip, "effective_length_ms", 0) or getattr(source_clip, "duration_ms", 0) or 1))
                track = AudioTrack(id=self._next_track_id(tracks), label=label)
                clip = AudioClip(
                    id=next_clip_id,
                    source_path=Path(path),
                    duration_ms=duration,
                    offset_ms=_int(getattr(source_clip, "offset_ms", 0)),
                    trim_start_ms=0,
                    trim_end_ms=duration,
                    fade_in_ms=_int(getattr(source_clip, "fade_in_ms", 0)),
                    fade_out_ms=_int(getattr(source_clip, "fade_out_ms", 0)),
                    fades=copy.deepcopy(getattr(source_clip, "fades", [])),
                    cuts=copy.deepcopy(getattr(source_clip, "cuts", [])),
                    gain=_float(getattr(source_clip, "gain", 1.0), 1.0),
                )
                next_clip_id += 1
                track.clips.append(clip)
                tracks.append(track)
                added.append({"track_id": _int(track.id), "clip_id": _int(clip.id), "label": label, "path": str(path)})
                insert = getattr(owner, "_insert_audio_track_widget", None)
                if callable(insert):
                    try:
                        insert(track)
                    except Exception:
                        pass
                mixer = getattr(owner, "_audio_mixer", None)
                add_track = getattr(mixer, "add_track", None)
                if callable(add_track):
                    try:
                        add_track(track)
                    except Exception:
                        pass
                waveform = getattr(owner, "_start_waveform_extraction", None)
                if callable(waveform):
                    try:
                        waveform(clip)
                    except Exception:
                        pass
            setattr(owner, "_audio_tracks", tracks)
            self._update_audio_track(source_track)
            return added

    def _sound_editor_duration_ms(self, clip: Any) -> int:
            return max(1, _int(getattr(clip, "effective_length_ms", 0) or getattr(clip, "duration_ms", 0) or 1))

    def _sound_editor_position_ms(self, clip: Any, duration_ms: int | None = None) -> int:
            duration = self._sound_editor_duration_ms(clip) if duration_ms is None else max(1, _int(duration_ms, 1))
            return max(0, min(duration, _int(getattr(clip, "_se_jog_ms", 0), 0)))

    def _sound_editor_level(self, clip: Any) -> float:
            waveform = getattr(clip, "waveform", None)
            try:
                if waveform is not None and int(getattr(waveform, "size", 0) or 0) > 0:
                    return max(0.05, min(1.0, float(abs(waveform).max())))
            except Exception:
                pass
            return max(0.05, min(1.0, _float(getattr(clip, "gain", 1.0), 1.0) / 1.5))

    def _workbench_sound_editor_panel(self) -> Any | None:
            wb = getattr(self._require_owner(), "_workbench_panel", None)
            return getattr(wb, "_sound_editor_panel", None) if wb is not None else None

    def _focus_workbench_sound_editor(
            self,
            track: Any,
            clip: Any,
            *,
            focus_workbench: bool,
            position_ms: int | None = None,
            playing: bool | None = None,
            advanced_expanded: bool | None = None,
        ) -> bool:
            if not focus_workbench:
                return False
            owner = self._require_owner()
            updated = False
            try:
                setattr(owner, "_active_audio_track_id", _int(getattr(track, "id", 0)))
                setattr(owner, "_selected_audio_clip_id", _int(getattr(clip, "id", 0)))
            except Exception:
                pass

            wb = getattr(owner, "_workbench_panel", None)
            if wb is not None:
                set_audio_clip = getattr(wb, "set_audio_clip", None)
                if callable(set_audio_clip):
                    try:
                        set_audio_clip(track, clip)
                        updated = True
                    except Exception:
                        pass
                set_tab = getattr(wb, "_set_inspector_tab", None)
                if callable(set_tab):
                    try:
                        set_tab("audio")
                        updated = True
                    except Exception:
                        pass
                panel = getattr(wb, "_sound_editor_panel", None)
                updated = self._apply_sound_editor_panel_state(
                    panel,
                    clip,
                    position_ms=position_ms,
                    playing=playing,
                    advanced_expanded=advanced_expanded,
                ) or updated

            refresh_audio = getattr(owner, "_refresh_audio_workspace_panel", None)
            if callable(refresh_audio):
                try:
                    refresh_audio()
                    updated = True
                except Exception:
                    pass
            self._process_capture_events()
            return updated

    def _apply_sound_editor_panel_state(
            self,
            panel: Any | None,
            clip: Any,
            *,
            position_ms: int | None = None,
            playing: bool | None = None,
            advanced_expanded: bool | None = None,
        ) -> bool:
            if panel is None:
                return False
            updated = False
            jog = getattr(panel, "_jog_shuttle", None)
            if jog is not None:
                set_clip = getattr(jog, "set_clip", None)
                if callable(set_clip):
                    try:
                        set_clip(clip)
                        updated = True
                    except Exception:
                        pass
                if position_ms is not None:
                    set_position = getattr(jog, "_set_position_ms", None)
                    if callable(set_position):
                        try:
                            set_position(_int(position_ms), emit=False)
                        except TypeError:
                            try:
                                set_position(_int(position_ms))
                                updated = True
                            except Exception:
                                pass
                        except Exception:
                            pass
                        else:
                            updated = True
                if playing is not None:
                    set_playing = getattr(jog, "_set_playing", None)
                    if callable(set_playing):
                        try:
                            set_playing(bool(playing))
                            updated = True
                        except Exception:
                            pass
            if advanced_expanded is not None:
                set_advanced = getattr(panel, "_set_advanced_lab_expanded", None)
                if callable(set_advanced):
                    try:
                        set_advanced(bool(advanced_expanded))
                        updated = True
                    except Exception:
                        pass
            return updated

    def _sound_editor_jog_state(self, track: Any, clip: Any) -> dict[str, Any]:
            duration = self._sound_editor_duration_ms(clip)
            position = self._sound_editor_position_ms(clip, duration)
            ui = self._sound_editor_ui_state(clip)
            return {
                "schema": "tigerstudio.sound_editor.jog_shuttle.v1",
                "track_id": _int(getattr(track, "id", 0)),
                "clip_id": _int(getattr(clip, "id", 0)),
                "position_ms": position,
                "duration_ms": duration,
                "normalized_position": round(position / max(1, duration), 6),
                "playing": bool(getattr(clip, "_se_jog_playing", False)),
                "level": round(self._sound_editor_level(clip), 6),
                "waveform_available": bool(getattr(getattr(clip, "waveform", None), "size", 0)),
                "reference_design": "05",
                "graph_style": "workbench_sound_graph",
                "workbench": ui,
            }

    def _sound_editor_advanced_lab_state(self, track: Any, clip: Any) -> dict[str, Any]:
            ui = self._sound_editor_ui_state(clip)
            expanded = bool(getattr(clip, "_se_advanced_lab_expanded", False))
            if bool(ui.get("panel_matches_clip")):
                expanded = bool(ui.get("advanced_expanded", expanded))
            return {
                "schema": "tigerstudio.sound_editor.advanced_lab.v1",
                "track_id": _int(getattr(track, "id", 0)),
                "clip_id": _int(getattr(clip, "id", 0)),
                "expanded": expanded,
                "inline": True,
                "legacy_lab_count": self._advanced_sound_lab_count(),
                "workbench": ui,
            }

    def _sound_editor_ui_state(self, clip: Any) -> dict[str, Any]:
            panel = self._workbench_sound_editor_panel()
            if panel is None:
                return {
                    "available": False,
                    "panel_matches_clip": False,
                    "visible": False,
                    "jog_shuttle_visible": False,
                    "advanced_expanded": bool(getattr(clip, "_se_advanced_lab_expanded", False)),
                }
            panel_clip = getattr(panel, "_clip", None)
            matches = panel_clip is clip
            is_visible = getattr(panel, "isVisible", None)
            jog = getattr(panel, "_jog_shuttle", None)
            jog_visible = getattr(jog, "isVisible", None)
            return {
                "available": True,
                "panel_matches_clip": matches,
                "visible": bool(is_visible()) if callable(is_visible) else True,
                "jog_shuttle_visible": bool(jog_visible()) if callable(jog_visible) else jog is not None,
                "advanced_expanded": bool(getattr(panel, "_advanced_expanded", getattr(clip, "_se_advanced_lab_expanded", False))),
            }

    def _advanced_sound_lab_count(self) -> int:
            try:
                return len(getattr(self._require_owner(), "_advanced_sound_labs", []) or [])
            except Exception:
                return 0
