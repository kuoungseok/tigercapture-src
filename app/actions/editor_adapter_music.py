"""Music Lab action adapter methods for AI-assisted composition."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from pathlib import Path
from typing import Any

from app.actions.editor_adapter_scalars import _bool, _float, _int
from app.music_composer import (
    MUSIC_SCHEMA,
    TICKS_PER_BEAT,
    MidiClip,
    MidiNote,
    MusicComposition,
    MusicSection,
    MusicTrack,
    chord_notes,
    compose_music,
    composition_from_dict,
    export_midi,
    ms_to_tick,
    music_render_backend_status,
    regenerate_section,
    render_preview,
    summary,
    _normalize_sample_library_policy,
    _sample_production_bus_for_role,
)


def _safe_id(value: Any, fallback: str) -> str:
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    text = "".join(ch for ch in text if ch.isalnum() or ch == "_").strip("_")
    return text or fallback


def _grid_ticks(grid: str) -> int:
    text = str(grid or "1/8").strip().lower()
    aliases = {"bar": TICKS_PER_BEAT * 4, "beat": TICKS_PER_BEAT, "1": TICKS_PER_BEAT * 4}
    if text in aliases:
        return aliases[text]
    if "/" in text:
        try:
            _num, den = text.split("/", 1)
            return max(1, int(round(TICKS_PER_BEAT * 4 / max(1, int(den)))))
        except Exception:
            return TICKS_PER_BEAT // 2
    try:
        return max(1, int(round(float(text))))
    except Exception:
        return TICKS_PER_BEAT // 2


def _music_backend_for_provider(backend: str, ai_provider: str = "") -> str:
    requested = str(backend or "auto").strip()
    provider = str(ai_provider or "").strip().lower()
    if provider and provider != "auto" and requested.lower() in {"", "auto"}:
        return "production"
    if requested.lower() in {"", "auto"}:
        try:
            preferred = str(music_render_backend_status().get("preferred_backend") or "")
            if preferred == "sample_production":
                return "sample_production"
        except Exception:
            pass
    return requested or "auto"


def _music_provider_forces_mix(ai_provider: str = "") -> bool:
    provider = str(ai_provider or "").strip().lower()
    return bool(provider and provider != "auto")


def _music_render_role_aliases(role: Any) -> set[str]:
    text = str(role or "").strip().lower()
    if not text:
        return set()
    aliases = {text}
    bus = str(_sample_production_bus_for_role(text) or "").strip().lower()
    if bus:
        aliases.add(bus)
    if text in {"drum", "drums", "perc", "percussion"}:
        aliases.add("percussion")
    elif text in {"bass", "sub", "sub_bass", "low"}:
        aliases.add("low")
    elif text in {"chord", "chords", "pad", "pads", "arp"}:
        aliases.add("pads")
    elif text in {"lead", "melody", "counter", "counter_melody", "guitar"}:
        aliases.add("lead")
    elif text in {"strings", "orchestra", "orchestral"}:
        aliases.add("orchestra")
    return aliases


class MusicAdapterMixin:
    """Expose deterministic Music Lab generation and MIDI editing to actions."""

    def _music_store(self) -> dict[str, MusicComposition]:
        owner = self._require_owner()
        store = getattr(owner, "_music_compositions", None)
        if not isinstance(store, dict):
            store = {}
            setattr(owner, "_music_compositions", store)
        for key, value in list(store.items()):
            if isinstance(value, Mapping):
                store[str(key)] = composition_from_dict(dict(value))
        return store

    def _music_composition(self, composition_id: str) -> MusicComposition:
        cid = str(composition_id or "").strip()
        if not cid:
            raise ValueError("composition_id is required")
        composition = self._music_store().get(cid)
        if composition is None:
            raise ValueError(f"music composition not found: {cid}")
        return composition

    def _latest_music_composition(self) -> MusicComposition:
        store = self._music_store()
        if not store:
            raise ValueError("no music compositions available")
        return list(store.values())[-1]

    def _store_music_composition(self, composition: MusicComposition) -> None:
        self._music_store()[composition.id] = composition

    def _music_track(self, composition: MusicComposition, track_id: str) -> MusicTrack:
        target = str(track_id or "").strip()
        for track in composition.tracks:
            if track.id == target:
                return track
        raise ValueError(f"music track not found: {target}")

    def _midi_clip(self, composition: MusicComposition, track_id: str, clip_id: str) -> tuple[MusicTrack, MidiClip]:
        track = self._music_track(composition, track_id)
        target = str(clip_id or "").strip()
        for clip in track.clips:
            if clip.id == target:
                return track, clip
        raise ValueError(f"midi clip not found: {target}")

    def _section(
        self,
        composition: MusicComposition,
        *,
        section_name: str = "",
        index: int | None = None,
    ) -> MusicSection:
        if index is not None:
            idx = _int(index, -1)
            if 0 <= idx < len(composition.sections):
                return composition.sections[idx]
        wanted = str(section_name or "").strip().lower()
        if wanted:
            for section in composition.sections:
                if section.name.lower() == wanted:
                    return section
        raise ValueError("section not found")

    def music_compose(
        self,
        *,
        prompt: str = "",
        duration_ms: int = 30000,
        genre: str = "",
        mood: str = "",
        bpm: int | None = None,
        key: str = "",
        include_fx: bool = True,
    ) -> dict[str, Any]:
        composition = compose_music(
            prompt=prompt,
            duration_ms=_int(duration_ms, 30000),
            genre=genre,
            mood=mood,
            bpm=bpm,
            key=key,
            include_fx=_bool(include_fx, True),
        )
        self._store_music_composition(composition)
        return {"schema": MUSIC_SCHEMA, "summary": summary(composition), "composition": composition.to_dict()}

    def music_arrange_create(self, **params: Any) -> dict[str, Any]:
        return self.music_compose(**params)

    def music_state(self, *, composition_id: str | None = None) -> dict[str, Any]:
        if composition_id:
            composition = self._music_composition(composition_id)
            return {"schema": MUSIC_SCHEMA, "summary": summary(composition), "composition": composition.to_dict()}
        rows = [summary(composition) for composition in self._music_store().values()]
        rows.sort(key=lambda row: str(row.get("id") or ""))
        return {"schema": MUSIC_SCHEMA, "composition_count": len(rows), "compositions": rows}

    def music_render_preview(
        self,
        *,
        composition_id: str | None = None,
        output_dir: str | None = None,
        backend: str = "auto",
        ai_provider: str = "",
        soundfont_path: str | None = None,
        drum_kit_path: str | None = None,
        sample_library_policy: str | None = None,
        render_stems: bool = True,
    ) -> dict[str, Any]:
        composition = self._music_composition(composition_id) if composition_id else self._latest_music_composition()
        effective_backend = _music_backend_for_provider(backend, ai_provider)
        effective_render_stems = _bool(render_stems, True) and not _music_provider_forces_mix(ai_provider)
        rendered = render_preview(
            composition,
            output_dir=output_dir or None,
            backend=effective_backend,
            ai_provider=ai_provider or "",
            soundfont_path=soundfont_path or None,
            drum_kit_path=drum_kit_path or None,
            sample_library_policy=sample_library_policy or None,
            render_stems=effective_render_stems,
        )
        self._store_music_composition(composition)
        return {"schema": MUSIC_SCHEMA, "summary": summary(composition), **rendered}

    def music_render_backends(self) -> dict[str, Any]:
        return {"schema": MUSIC_SCHEMA, **music_render_backend_status()}

    def music_export_midi(
        self,
        *,
        composition_id: str | None = None,
        output_path: str | None = None,
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        composition = self._music_composition(composition_id) if composition_id else self._latest_music_composition()
        exported = export_midi(
            composition,
            output_path=output_path or None,
            output_dir=output_dir or None,
        )
        self._store_music_composition(composition)
        return {"schema": MUSIC_SCHEMA, "summary": summary(composition), **exported}

    def _ensure_music_rendered(
        self,
        composition: MusicComposition,
        output_dir: str | None = None,
        *,
        backend: str = "auto",
        ai_provider: str = "",
        soundfont_path: str | None = None,
        drum_kit_path: str | None = None,
        sample_library_policy: str | None = None,
        require_stems: bool = True,
    ) -> None:
        effective_backend = _music_backend_for_provider(backend, ai_provider)
        requested = str(effective_backend or "auto").strip().lower()
        current_backend = ""
        current_render_meta: dict[str, Any] = {}
        if isinstance(getattr(composition, "render_backend", None), dict):
            current_render_meta = dict(composition.render_backend)
            current_backend = str(current_render_meta.get("backend") or "")
        explicit_backend = requested not in {"", "auto"}
        if requested in {"local", "local_synth"}:
            requested_backend = "local_synth"
        elif requested in {"soundfont", "fluidsynth", "fluidsynth_soundfont"}:
            requested_backend = "fluidsynth_soundfont"
        elif requested in {"studio_edm", "edm_studio", "edm", "draft_synth"}:
            requested_backend = "studio_edm"
        elif requested in {"sample_production", "sample", "cinematic_local", "local_production", "production_sample"}:
            requested_backend = "sample_production"
        elif requested in {"production", "production_external", "external_music", "external_ai"}:
            requested_backend = "production_external"
        elif requested in {"", "auto"}:
            preferred = str(music_render_backend_status().get("preferred_backend") or "")
            if preferred == "production_external" and not _bool(require_stems, True):
                requested_backend = "production_external"
            elif preferred == "fluidsynth_soundfont":
                requested_backend = "fluidsynth_soundfont"
            else:
                requested_backend = current_backend
        else:
            requested_backend = current_backend
        rendered_stems_ok = bool(composition.rendered_stems) and all(Path(path).exists() for path in composition.rendered_stems.values())
        preview_ok = bool(composition.preview_mix_path) and Path(composition.preview_mix_path).exists()
        if (rendered_stems_ok if _bool(require_stems, True) else preview_ok):
            preview_ok = not composition.preview_mix_path or Path(composition.preview_mix_path).exists()
            backend_ok = not explicit_backend or not requested_backend or current_backend == requested_backend
            sample_policy_ok = True
            if requested_backend == "sample_production":
                requested_policy = _normalize_sample_library_policy(sample_library_policy)
                current_policy = _normalize_sample_library_policy(str(current_render_meta.get("sample_library_policy") or ""))
                sample_policy_ok = current_policy == requested_policy
                if soundfont_path:
                    sample_policy_ok = sample_policy_ok and str(current_render_meta.get("requested_soundfont_path") or "") == str(soundfont_path)
                if drum_kit_path:
                    sample_policy_ok = sample_policy_ok and str(current_render_meta.get("requested_drum_kit_path") or "") == str(drum_kit_path)
            if preview_ok and backend_ok and sample_policy_ok:
                return
        render_preview(
            composition,
            output_dir=output_dir or None,
            backend=effective_backend,
            ai_provider=ai_provider or "",
            soundfont_path=soundfont_path or None,
            drum_kit_path=drum_kit_path or None,
            sample_library_policy=sample_library_policy or None,
            render_stems=_bool(require_stems, True),
        )
        self._store_music_composition(composition)

    def music_render_to_timeline(
        self,
        *,
        composition_id: str | None = None,
        output_dir: str | None = None,
        at_ms: int = 0,
        roles: Sequence[str] | None = None,
        create_mix: bool = False,
        update_existing: bool = False,
        backend: str = "auto",
        ai_provider: str = "",
        soundfont_path: str | None = None,
        drum_kit_path: str | None = None,
        sample_library_policy: str | None = None,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        composition = self._music_composition(composition_id) if composition_id else self._latest_music_composition()
        effective_create_mix = _bool(create_mix, False) or _music_provider_forces_mix(ai_provider)
        self._ensure_music_rendered(
            composition,
            output_dir=output_dir,
            backend=_music_backend_for_provider(backend, ai_provider),
            ai_provider=ai_provider or "",
            soundfont_path=soundfont_path or None,
            drum_kit_path=drum_kit_path or None,
            sample_library_policy=sample_library_policy or None,
            require_stems=not effective_create_mix,
        )
        from app.audio_tracks import AudioClip, AudioTrack

        wanted_roles: set[str] = set()
        for role in list(roles or []):
            wanted_roles.update(_music_render_role_aliases(role))
        rendered_items: list[tuple[str, Path, float, float]] = []
        if effective_create_mix:
            rendered_items.append(("mix", Path(composition.preview_mix_path), 0.86, 0.0))
        else:
            tracks_by_role = {track.role: track for track in composition.tracks}
            for role, path in composition.rendered_stems.items():
                if wanted_roles and role not in wanted_roles:
                    continue
                track = tracks_by_role.get(role)
                rendered_items.append(
                    (
                        role,
                        Path(path),
                        _float(getattr(track, "volume", 0.75), 0.75) if track else 0.75,
                        _float(getattr(track, "pan", 0.0), 0.0) if track else 0.0,
                    )
                )
        if not rendered_items:
            raise ValueError("no rendered music stems matched the requested roles")

        tracks = list(getattr(owner, "_audio_tracks", []) or [])
        added: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []
        next_clip_id = self._next_audio_clip_id()
        for role, path, volume, pan in rendered_items:
            if not path.exists():
                raise FileNotFoundError(str(path))
            label = "Music Mix" if role == "mix" else f"Music {role.title()}"
            duration_ms = max(1, _int(composition.duration_ms, 1))
            existing = None
            if _bool(update_existing, False):
                for candidate in tracks:
                    cid = str(getattr(candidate, "music_composition_id", "") or "")
                    candidate_role = str(getattr(candidate, "music_role", "") or "").strip().lower()
                    if cid == composition.id and candidate_role == role:
                        existing = candidate
                        break
            if existing is not None:
                track = existing
                old_clip = (list(getattr(track, "clips", []) or []) or [None])[0]
                clip_id = _int(getattr(old_clip, "id", 0), 0) if old_clip is not None else 0
                if clip_id <= 0:
                    clip_id = next_clip_id
                    next_clip_id += 1
                clip = AudioClip(
                    id=clip_id,
                    source_path=path,
                    duration_ms=duration_ms,
                    offset_ms=max(0, _int(at_ms, 0)),
                    trim_start_ms=0,
                    trim_end_ms=duration_ms,
                    gain=1.0,
                )
                track.volume = max(0.0, min(1.5, volume))
                track.pan = max(-1.0, min(1.0, pan))
                track.clips = [clip]
                track.label = label
                track.bus_id = "music"
                track.track_type = "music"
                setattr(track, "music_composition_id", composition.id)
                setattr(track, "music_role", role)
                setattr(clip, "music_composition_id", composition.id)
                setattr(clip, "music_role", role)
                self._sync_audio_track_ui(track, created=False, clip=clip)
                updated.append(
                    {
                        "track_id": _int(track.id),
                        "clip_id": _int(clip.id),
                        "role": role,
                        "label": label,
                        "path": str(path),
                        "offset_ms": _int(clip.offset_ms),
                    }
                )
            else:
                track_id = self._next_track_id(tracks)
                clip = AudioClip(
                    id=next_clip_id,
                    source_path=path,
                    duration_ms=duration_ms,
                    offset_ms=max(0, _int(at_ms, 0)),
                    trim_start_ms=0,
                    trim_end_ms=duration_ms,
                    gain=1.0,
                )
                next_clip_id += 1
                track = AudioTrack(
                    id=track_id,
                    volume=max(0.0, min(1.5, volume)),
                    pan=max(-1.0, min(1.0, pan)),
                    clips=[clip],
                    label=label,
                    bus_id="music",
                    track_type="music",
                )
                setattr(track, "music_composition_id", composition.id)
                setattr(track, "music_role", role)
                setattr(clip, "music_composition_id", composition.id)
                setattr(clip, "music_role", role)
                tracks.append(track)
                setattr(owner, "_audio_tracks", tracks)
                self._advance_owner_next_track_id(track_id)
                self._sync_audio_track_ui(track, created=True, clip=clip)
                added.append(
                    {
                        "track_id": _int(track.id),
                        "clip_id": _int(clip.id),
                        "role": role,
                        "label": label,
                        "path": str(path),
                        "offset_ms": _int(clip.offset_ms),
                    }
                )
        self._after_timeline_mutation("Action render music to timeline")
        return {
            "schema": MUSIC_SCHEMA,
            "composition_id": composition.id,
            "added": added,
            "added_count": len(added),
            "updated": updated,
            "updated_count": len(updated),
        }

    def music_compose_to_timeline(
        self,
        *,
        prompt: str = "",
        duration_ms: int = 30000,
        genre: str = "",
        mood: str = "",
        bpm: int | None = None,
        key: str = "",
        include_fx: bool = True,
        output_dir: str | None = None,
        at_ms: int = 0,
        roles: Sequence[str] | None = None,
        create_mix: bool = False,
        auto_balance: bool = True,
        update_existing: bool = True,
        backend: str = "auto",
        ai_provider: str = "",
        soundfont_path: str | None = None,
        drum_kit_path: str | None = None,
        sample_library_policy: str | None = None,
    ) -> dict[str, Any]:
        composition_result = self.music_compose(
            prompt=prompt,
            duration_ms=duration_ms,
            genre=genre,
            mood=mood,
            bpm=bpm,
            key=key,
            include_fx=include_fx,
        )
        composition_id = str(composition_result["summary"]["id"])
        effective_create_mix = _bool(create_mix, False) or _music_provider_forces_mix(ai_provider)
        preview = self.music_render_preview(
            composition_id=composition_id,
            output_dir=output_dir,
            backend=_music_backend_for_provider(backend, ai_provider),
            ai_provider=ai_provider or "",
            soundfont_path=soundfont_path or None,
            drum_kit_path=drum_kit_path or None,
            sample_library_policy=sample_library_policy or None,
            render_stems=not effective_create_mix,
        )
        timeline = self.music_render_to_timeline(
            composition_id=composition_id,
            output_dir=output_dir,
            at_ms=at_ms,
            roles=roles,
            create_mix=effective_create_mix,
            update_existing=update_existing,
            backend=_music_backend_for_provider(backend, ai_provider),
            ai_provider=ai_provider or "",
            soundfont_path=soundfont_path or None,
            drum_kit_path=drum_kit_path or None,
            sample_library_policy=sample_library_policy or None,
        )
        balance = (
            self.music_mixer_auto_balance(composition_id=composition_id)
            if _bool(auto_balance, True)
            else {"changed": [], "changed_count": 0}
        )
        composition = self._music_composition(composition_id)
        return {
            "schema": MUSIC_SCHEMA,
            "composition_id": composition_id,
            "summary": summary(composition),
            "composition": composition.to_dict(),
            "preview": preview,
            "timeline": timeline,
            "mixer": balance,
        }

    def music_mixer_auto_balance(
        self,
        *,
        composition_id: str | None = None,
        track_ids: Sequence[int] | None = None,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        wanted_ids = {_int(track_id, -1) for track_id in list(track_ids or [])}
        role_levels = {
            "drums": (0.70, 0.0),
            "bass": (0.62, -0.04),
            "chords": (0.50, 0.08),
            "melody": (0.46, 0.14),
            "fx": (0.32, 0.0),
            "mix": (0.82, 0.0),
        }
        changed: list[dict[str, Any]] = []
        for track in list(getattr(owner, "_audio_tracks", []) or []):
            tid = _int(getattr(track, "id", -1), -1)
            role = str(getattr(track, "music_role", "") or "").strip().lower()
            cid = str(getattr(track, "music_composition_id", "") or "")
            if wanted_ids and tid not in wanted_ids:
                continue
            if composition_id and cid != str(composition_id):
                continue
            if not role and not str(getattr(track, "label", "") or "").lower().startswith("music"):
                continue
            volume, pan = role_levels.get(role, (0.58, 0.0))
            track.volume = volume
            track.pan = pan
            track.bus_id = "music"
            track.track_type = "music"
            self._update_audio_track(track)
            changed.append({"track_id": tid, "role": role or "music", "volume": volume, "pan": pan})
        self._after_timeline_mutation("Action auto balance music mixer")
        return {"schema": MUSIC_SCHEMA, "changed": changed, "changed_count": len(changed)}

    def music_apply_master_fx(
        self,
        *,
        composition_id: str | None = None,
        role: str = "mix",
        effects: Mapping[str, Any] | None = None,
        merge: bool = True,
        focus_workbench: bool = False,
    ) -> dict[str, Any]:
        """Apply Sound Editor effect state to rendered Music Lab audio clips.

        Composer owns MIDI/arrangement.  Sound shaping should still flow through
        the Sound Editor effect model, so this action finds the rendered Music
        Mix or requested stem tracks and merges ``AudioClip.effects`` there.
        """
        owner = self._require_owner()
        target_role = str(role or "mix").strip().lower()
        target_aliases = _music_render_role_aliases(target_role)
        if target_role in {"", "all", "*", "music"}:
            target_aliases = set()
        elif target_role == "mix":
            target_aliases = {"mix"}
        if not isinstance(effects, Mapping):
            effects = {}

        from app.audio_tracks import default_effects_state

        defaults = default_effects_state()
        changed: list[dict[str, Any]] = []
        last_track = None
        last_clip = None
        for track in list(getattr(owner, "_audio_tracks", []) or []):
            cid = str(getattr(track, "music_composition_id", "") or "")
            if composition_id and cid != str(composition_id):
                continue
            music_role = str(getattr(track, "music_role", "") or "").strip().lower()
            label = str(getattr(track, "label", "") or "").strip().lower()
            is_music = bool(music_role or label.startswith("music"))
            if not is_music:
                continue
            if target_aliases and music_role not in target_aliases:
                continue
            for clip in list(getattr(track, "clips", []) or []):
                if getattr(clip, "source_path", None) is None:
                    continue
                if not isinstance(getattr(clip, "effects", None), dict) or not merge:
                    clip.effects = copy.deepcopy(defaults)
                self._merge_sound_editor_effects(clip.effects, effects)
                self._update_audio_track(track)
                last_track = track
                last_clip = clip
                changed.append(
                    {
                        "track_id": _int(getattr(track, "id", 0)),
                        "clip_id": _int(getattr(clip, "id", 0)),
                        "role": music_role or "music",
                        "label": str(getattr(track, "label", "") or ""),
                    }
                )
        ui_updated = False
        if last_track is not None and last_clip is not None:
            ui_updated = self._focus_workbench_sound_editor(
                last_track,
                last_clip,
                focus_workbench=_bool(focus_workbench, False),
            )
        if changed:
            self._after_timeline_mutation("Action apply Composer master FX")
        return {
            "schema": MUSIC_SCHEMA,
            "composition_id": str(composition_id or ""),
            "role": target_role,
            "changed": changed,
            "changed_count": len(changed),
            "ui_updated": ui_updated,
        }

    def music_regenerate_section(
        self,
        *,
        composition_id: str,
        section_name: str,
        mood: str = "",
        intensity: float | None = None,
        backend: str = "auto",
        ai_provider: str = "",
        soundfont_path: str | None = None,
        drum_kit_path: str | None = None,
        sample_library_policy: str | None = None,
    ) -> dict[str, Any]:
        composition = self._music_composition(composition_id)
        regenerate_section(composition, section_name, mood=mood, intensity=intensity)
        self._store_music_composition(composition)
        return {"schema": MUSIC_SCHEMA, "summary": summary(composition), "composition": composition.to_dict()}

    def music_section_set(
        self,
        *,
        composition_id: str,
        section_name: str = "",
        index: int | None = None,
        name: str | None = None,
        start_ms: int | None = None,
        duration_ms: int | None = None,
        intensity: float | None = None,
        chord_progression: Sequence[str] | None = None,
        backend: str = "auto",
        ai_provider: str = "",
        soundfont_path: str | None = None,
        drum_kit_path: str | None = None,
        sample_library_policy: str | None = None,
    ) -> dict[str, Any]:
        composition = self._music_composition(composition_id)
        section = self._section(composition, section_name=section_name, index=index)
        before = dict(section.__dict__)
        if name is not None:
            section.name = str(name or section.name).strip() or section.name
        if start_ms is not None:
            section.start_ms = max(0, _int(start_ms, section.start_ms))
        if duration_ms is not None:
            section.duration_ms = max(1, _int(duration_ms, section.duration_ms))
        if intensity is not None:
            section.intensity = max(0.05, min(1.0, _float(intensity, section.intensity)))
        if chord_progression is not None:
            chords = [str(chord).strip() for chord in list(chord_progression or []) if str(chord).strip()]
            if chords:
                section.chord_progression = chords
        composition.rendered_stems = {}
        composition.preview_mix_path = ""
        self._store_music_composition(composition)
        return {"schema": MUSIC_SCHEMA, "composition_id": composition.id, "old": before, "new": dict(section.__dict__)}

    def music_track_create(
        self,
        *,
        composition_id: str,
        role: str,
        instrument: str = "",
        volume: float = 0.8,
        pan: float = 0.0,
    ) -> dict[str, Any]:
        composition = self._music_composition(composition_id)
        base = _safe_id(role, "track")
        existing = {track.id for track in composition.tracks}
        track_id = base
        index = 2
        while track_id in existing:
            track_id = f"{base}_{index}"
            index += 1
        track = MusicTrack(
            id=track_id,
            role=base,
            instrument=str(instrument or base.title()),
            volume=max(0.0, min(1.5, _float(volume, 0.8))),
            pan=max(-1.0, min(1.0, _float(pan, 0.0))),
        )
        composition.tracks.append(track)
        composition.rendered_stems = {}
        composition.preview_mix_path = ""
        self._store_music_composition(composition)
        return {"schema": MUSIC_SCHEMA, "composition_id": composition.id, "track": track.__dict__}

    def music_track_set_instrument(self, *, composition_id: str, track_id: str, instrument: str) -> dict[str, Any]:
        composition = self._music_composition(composition_id)
        track = self._music_track(composition, track_id)
        old = track.instrument
        track.instrument = str(instrument or old).strip() or old
        composition.rendered_stems = {}
        composition.preview_mix_path = ""
        self._store_music_composition(composition)
        return {"schema": MUSIC_SCHEMA, "composition_id": composition.id, "track_id": track.id, "old": old, "instrument": track.instrument}

    def midi_clip_create(
        self,
        *,
        composition_id: str,
        track_id: str,
        section_name: str = "",
        start_ms: int = 0,
        duration_ms: int = 1000,
        clip_id: str = "",
    ) -> dict[str, Any]:
        composition = self._music_composition(composition_id)
        track = self._music_track(composition, track_id)
        if section_name:
            section = self._section(composition, section_name=section_name)
            start = section.start_ms
            duration = section.duration_ms
            section_label = section.name
        else:
            start = max(0, _int(start_ms, 0))
            duration = max(1, _int(duration_ms, 1000))
            section_label = ""
        cid = str(clip_id or "").strip() or f"{track.id}_clip_{len(track.clips) + 1}"
        if any(clip.id == cid for clip in track.clips):
            raise ValueError(f"midi clip already exists: {cid}")
        clip = MidiClip(id=cid, section_name=section_label, start_ms=start, duration_ms=duration)
        track.clips.append(clip)
        track.clips.sort(key=lambda row: row.start_ms)
        composition.rendered_stems = {}
        composition.preview_mix_path = ""
        self._store_music_composition(composition)
        return {"schema": MUSIC_SCHEMA, "composition_id": composition.id, "track_id": track.id, "clip": clip.__dict__}

    def midi_clip_write_notes(
        self,
        *,
        composition_id: str,
        track_id: str,
        clip_id: str,
        notes: Sequence[Mapping[str, Any]] | Sequence[Sequence[Any]],
        replace: bool = True,
    ) -> dict[str, Any]:
        composition = self._music_composition(composition_id)
        _track, clip = self._midi_clip(composition, track_id, clip_id)
        rows: list[MidiNote] = []
        for note in list(notes or []):
            if isinstance(note, Mapping):
                rows.append(
                    MidiNote(
                        pitch=max(0, min(127, _int(note.get("pitch"), 60))),
                        start_tick=max(0, _int(note.get("start_tick", note.get("start")), 0)),
                        duration_tick=max(1, _int(note.get("duration_tick", note.get("duration")), TICKS_PER_BEAT)),
                        velocity=max(1, min(127, _int(note.get("velocity"), 90))),
                    )
                )
            else:
                values = list(note or [])
                if len(values) < 3:
                    continue
                rows.append(
                    MidiNote(
                        pitch=max(0, min(127, _int(values[0], 60))),
                        start_tick=max(0, _int(values[1], 0)),
                        duration_tick=max(1, _int(values[2], TICKS_PER_BEAT)),
                        velocity=max(1, min(127, _int(values[3], 90) if len(values) > 3 else 90)),
                    )
                )
        if _bool(replace, True):
            clip.notes = rows
        else:
            clip.notes.extend(rows)
            clip.notes.sort(key=lambda row: row.start_tick)
        composition.rendered_stems = {}
        composition.preview_mix_path = ""
        self._store_music_composition(composition)
        return {"schema": MUSIC_SCHEMA, "composition_id": composition.id, "track_id": track_id, "clip_id": clip.id, "note_count": len(clip.notes)}

    def midi_clip_write_chords(
        self,
        *,
        composition_id: str,
        track_id: str,
        clip_id: str,
        chords: Sequence[str] | Sequence[Mapping[str, Any]],
        key: str = "",
        octave: int = 1,
        replace: bool = True,
    ) -> dict[str, Any]:
        composition = self._music_composition(composition_id)
        _track, clip = self._midi_clip(composition, track_id, clip_id)
        cursor = ms_to_tick(clip.start_ms, composition.bpm)
        rows: list[MidiNote] = []
        for chord in list(chords or []):
            if isinstance(chord, Mapping):
                label = str(chord.get("chord") or chord.get("name") or "").strip()
                bars = max(1, _int(chord.get("bars"), 1))
            else:
                label = str(chord or "").strip()
                bars = 1
            if not label:
                continue
            duration = TICKS_PER_BEAT * 4 * bars
            for pitch in chord_notes(label, key or composition.key, octave=_int(octave, 1)):
                rows.append(MidiNote(pitch=pitch, start_tick=cursor, duration_tick=max(1, duration - 24), velocity=76))
            cursor += duration
        if _bool(replace, True):
            clip.notes = rows
        else:
            clip.notes.extend(rows)
            clip.notes.sort(key=lambda row: row.start_tick)
        composition.rendered_stems = {}
        composition.preview_mix_path = ""
        self._store_music_composition(composition)
        return {"schema": MUSIC_SCHEMA, "composition_id": composition.id, "track_id": track_id, "clip_id": clip.id, "note_count": len(clip.notes)}

    def midi_clip_quantize(
        self,
        *,
        composition_id: str,
        track_id: str,
        clip_id: str,
        grid: str = "1/8",
        quantize_duration: bool = False,
    ) -> dict[str, Any]:
        composition = self._music_composition(composition_id)
        _track, clip = self._midi_clip(composition, track_id, clip_id)
        ticks = _grid_ticks(grid)
        for note in clip.notes:
            note.start_tick = max(0, int(round(note.start_tick / ticks)) * ticks)
            if _bool(quantize_duration, False):
                note.duration_tick = max(ticks, int(round(note.duration_tick / ticks)) * ticks)
        clip.notes.sort(key=lambda row: row.start_tick)
        composition.rendered_stems = {}
        composition.preview_mix_path = ""
        self._store_music_composition(composition)
        return {"schema": MUSIC_SCHEMA, "composition_id": composition.id, "track_id": track_id, "clip_id": clip.id, "grid_ticks": ticks, "note_count": len(clip.notes)}
