"""Owner-only render window for the Action Sequencer bridge."""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size, unreal_engine_icon
from app.action_sequencer_ar_pbr_proxy import (
    default_owner_ar_pbr_proxy_path,
    write_owner_ar_pbr_proxy_asset,
)
from app.action_sequencer_stage_pair import (
    default_action_sequencer_stage_pair_path,
    write_action_sequencer_stage_pair_asset,
)
from app.action_sequencer_unreal_asset_bridge import (
    default_owner_unreal_ar_pbr_path,
    export_owner_unreal_ar_pbr_asset,
    export_owner_unreal_animation_clip,
    export_owner_unreal_animation_clips_batch,
    owner_unreal_animation_clip_cache_status,
)
from app.action_sequencer_animation_sequence import (
    ACTION_SEQUENCE_REFERENCE_PIPELINE,
    animation_sequence_summary,
    build_owner_animation_sequence,
)
from app.unreal_link_reference_paths import unreal_link_reference_roots


ACTION_SEQUENCER_PROJECT_ENV = "TIGERSTUDIO_ACTION_SEQUENCER_PROJECT"
DEFAULT_ACTION_SEQUENCER_PROJECT = Path("E:/ue5example/ActionSequencer/ActionSequencer.uproject")
OWNER_ANIMATION_PANEL_WIDTH = 200
OWNER_ANIMATION_PREVIEW_BACKEND = "uasset_inspector_gpu_bone_palette"
OWNER_POSE_CLIP_DURATION_THRESHOLD_MS = 250.0
OWNER_ANIMATION_PREVIEW_MAX_GEOMETRY_HEIGHT_RATIO = 2.25
OWNER_ANIMATION_PREVIEW_SAMPLE_VERTICES = 8000
OWNER_STAGE_PREVIEW_VIEW = {
    "pitch": 0.0,
    "yaw": -90.0,
    "pan_x": -0.04,
    "zoom": 1.28,
}
OWNER_ANIMATION_FILTERS = (
    ("All", "all"),
    ("Combat", "combat"),
    ("Motion", "motion"),
    ("Weapon", "weapon"),
    ("Move", "movement"),
    ("Pose", "pose"),
)
OWNER_ANIMATION_CATEGORY_LABELS = {
    "combat": "Combat Motions",
    "weapon": "Weapon Actions",
    "movement": "Movement",
    "pose": "Pose Fragments",
    "other": "Other",
}
OWNER_ANIMATION_CATEGORY_PRIORITY = {
    "combat": 0,
    "weapon": 1,
    "movement": 2,
    "pose": 3,
    "other": 9,
}


@dataclass(frozen=True)
class OwnerRenderDescriptor:
    project_path: Path
    owner_name: str
    owner_asset_path: Path | None
    owner_class_name: str
    render_asset_path: Path | None
    animation_blueprint_path: Path | None
    idle_animation_path: Path | None
    action_candidate_path: Path | None
    animation_sequence_paths: tuple[Path, ...] = field(default_factory=tuple)
    stage_position: tuple[float, float, float] = (-120.0, 0.0, 0.0)
    stage_forward: str = "+X / screen right"
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    @property
    def can_render(self) -> bool:
        return self.render_asset_path is not None and self.render_asset_path.exists()

    def summary_rows(self) -> list[tuple[str, str]]:
        return [
            ("Project", _display_path(self.project_path)),
            ("Owner", self.owner_name),
            ("Owner class", self.owner_class_name),
            ("Owner asset", _display_path(self.owner_asset_path)),
            ("Render mesh", _display_path(self.render_asset_path)),
            ("Idle pose", _display_path(self.idle_animation_path)),
            ("Action candidate", _display_path(self.action_candidate_path)),
            ("Animation sequences", str(len(self.animation_sequence_paths))),
            ("Stage", f"left {self.stage_position}, facing {self.stage_forward}"),
        ]

    def to_result(self) -> dict[str, Any]:
        return {
            "project_path": str(self.project_path),
            "owner_name": self.owner_name,
            "owner_asset_path": str(self.owner_asset_path) if self.owner_asset_path else None,
            "owner_class_name": self.owner_class_name,
            "render_asset_path": str(self.render_asset_path) if self.render_asset_path else None,
            "animation_blueprint_path": str(self.animation_blueprint_path) if self.animation_blueprint_path else None,
            "idle_animation_path": str(self.idle_animation_path) if self.idle_animation_path else None,
            "action_candidate_path": str(self.action_candidate_path) if self.action_candidate_path else None,
            "animation_sequence_paths": [str(path) for path in self.animation_sequence_paths],
            "stage_position": list(self.stage_position),
            "stage_forward": self.stage_forward,
            "diagnostics": list(self.diagnostics),
            "can_render": self.can_render,
        }


def default_action_sequencer_project_path() -> Path:
    configured = os.environ.get(ACTION_SEQUENCER_PROJECT_ENV, "").strip()
    if configured:
        return Path(configured)
    return DEFAULT_ACTION_SEQUENCER_PROJECT


def discover_owner_render_descriptor(project_path: Path | str | None = None) -> OwnerRenderDescriptor:
    project = Path(project_path) if project_path is not None else default_action_sequencer_project_path()
    diagnostics: list[str] = []
    content_root = project.parent / "Content"
    if not project.exists():
        diagnostics.append(f"Project file not found: {project}")
    if not content_root.exists():
        diagnostics.append(f"Content folder not found: {content_root}")

    owner_asset = _first_existing(
        content_root / "Variant_Combat" / "Blueprints" / "BP_CombatCharacter.uasset",
        *_safe_rglob(content_root, "BP_CombatCharacter.uasset"),
    )
    if owner_asset is None:
        diagnostics.append("BP_CombatCharacter was not found; falling back to mesh-only owner preview.")

    render_asset = _first_existing(
        content_root / "Characters" / "Mannequins" / "Meshes" / "SKM_Manny_Simple.uasset",
        content_root / "Characters" / "Mannequins" / "Meshes" / "SK_Mannequin.uasset",
        *_safe_rglob(content_root / "Characters" / "Mannequins" / "Meshes", "SK*.uasset"),
    )
    if render_asset is None:
        diagnostics.append("No mannequin skeletal mesh was found for Owner rendering.")

    anim_bp = _first_existing(
        content_root / "Variant_Combat" / "Anims" / "ABP_Manny_Combat.uasset",
        content_root / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "ABP_Unarmed.uasset",
    )
    idle_anim = _first_existing(
        content_root / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "MM_Idle.uasset",
    )
    action_candidate = _first_existing(
        content_root / "Characters" / "Mannequins" / "Anims" / "Unarmed" / "Attack" / "MM_Attack_01.uasset",
        content_root / "Variant_Combat" / "Anims" / "AM_ComboAttack.uasset",
    )
    animation_sequences = _discover_animation_sequence_paths(content_root)

    references = unreal_link_reference_roots()
    inspector_root = references["uasset_inspector"]
    if not inspector_root.exists or inspector_root.missing_children:
        diagnostics.append("UAssetInspector reference root is missing or incomplete.")
    engine_root = references["ue_58"]
    if not engine_root.exists or engine_root.missing_children:
        diagnostics.append("UE 5.8 reference root is missing or incomplete.")

    return OwnerRenderDescriptor(
        project_path=project,
        owner_name="BP_CombatCharacter",
        owner_asset_path=owner_asset,
        owner_class_name="ACombatCharacter",
        render_asset_path=render_asset,
        animation_blueprint_path=anim_bp,
        idle_animation_path=idle_anim,
        action_candidate_path=action_candidate,
        animation_sequence_paths=animation_sequences,
        diagnostics=tuple(diagnostics),
    )


def _discover_animation_sequence_paths(content_root: Path) -> tuple[Path, ...]:
    roots = (
        content_root / "Variant_Combat" / "Anims",
        content_root / "Characters" / "Mannequins" / "Anims",
    )
    seen: set[Path] = set()
    candidates: list[Path] = []
    for root in roots:
        for asset in _safe_rglob(root, "*.uasset"):
            resolved = asset.resolve()
            if resolved in seen or not _is_animation_sequence_candidate(asset):
                continue
            seen.add(resolved)
            candidates.append(asset)
    return tuple(sorted(candidates, key=lambda path: _animation_browser_sort_key(content_root, path)))


def _is_animation_sequence_candidate(path: Path) -> bool:
    name = path.stem.casefold()
    if name.startswith(("abp_", "bs_", "ao_")):
        return False
    if "animblueprint" in name or "blendspace" in name or "aimoffset" in name:
        return False
    return name.startswith(("mm_", "mf_"))


def _animation_sort_key(content_root: Path, path: Path) -> tuple[int, str, str]:
    return (
        _animation_sequence_priority(path),
        _animation_display_group(content_root, path).casefold(),
        path.stem.casefold(),
    )


def _animation_browser_sort_key(content_root: Path, path: Path) -> tuple[int, int, int, str, str]:
    category = _animation_browser_category(content_root, path)
    return (
        OWNER_ANIMATION_CATEGORY_PRIORITY.get(category, OWNER_ANIMATION_CATEGORY_PRIORITY["other"]),
        _animation_browser_subpriority(content_root, path),
        _animation_sequence_priority(path),
        _animation_display_group(content_root, path).casefold(),
        path.stem.casefold(),
    )


def _animation_display_label(content_root: Path, path: Path) -> str:
    group = _animation_display_group(content_root, path)
    kind = _animation_sequence_kind(path)
    prefix = {
        "action": "Action",
        "motion": "Motion",
        "pose": "Pose",
    }.get(kind, "Anim")
    body = f"{group} / {path.stem}" if group else path.stem
    return f"{prefix} / {body}"


def _animation_browser_item_label(content_root: Path, path: Path) -> str:
    kind = _animation_sequence_kind(path)
    badge = {
        "action": "A",
        "motion": "M",
        "pose": "P",
    }.get(kind, "N")
    group = _animation_display_group(content_root, path).replace(" / ", " ")
    body = f"{group} / {path.stem}" if group else path.stem
    return f"{badge} {body}"


def _animation_browser_category(content_root: Path, path: Path) -> str:
    kind = _animation_sequence_kind(path)
    group = _animation_display_group(content_root, path)
    text = f"{group} {path.stem}".casefold()
    if kind == "pose":
        return "pose"
    if any(token in text for token in ("attack", "hitreact", "death", "charged")):
        return "combat"
    if any(token in text for token in ("dash", "fall", "jog", "jump", "land", "run", "walk", "walljump")):
        return "movement"
    if any(token in text for token in ("ads", "aim", "dryfire", "equip", "fire", "pistol", "reload", "rifle")):
        return "weapon"
    return "other"


def _animation_browser_subpriority(content_root: Path, path: Path) -> int:
    category = _animation_browser_category(content_root, path)
    text = f"{_animation_display_group(content_root, path)} {path.stem}".casefold()
    if category == "combat":
        if "attack" in text or "charged" in text:
            return 0
        if "hitreact" in text:
            return 1
        if "death" in text:
            return 2
        return 3
    if category == "movement":
        if "dash" in text:
            return 0
        if "jump" in text or "fall" in text or "land" in text:
            return 1
        if "jog" in text or "run" in text:
            return 2
        if "walk" in text:
            return 3
    return 0


def _animation_browser_filter_matches(content_root: Path, path: Path, filter_key: str) -> bool:
    key = str(filter_key or "all")
    if key == "all":
        return True
    if key == "motion":
        return _animation_sequence_kind(path) in {"action", "motion"}
    return _animation_browser_category(content_root, path) == key


def _animation_browser_category_label(category: str) -> str:
    return OWNER_ANIMATION_CATEGORY_LABELS.get(str(category or "other"), "Other")


def _recommended_target_animation_path(
    owner_path: Path | None,
    candidates: tuple[Path, ...] | list[Path],
    content_root: Path,
) -> Path | None:
    if owner_path is None:
        return None
    owner_text = f"{_animation_display_group(content_root, owner_path)} {owner_path.stem}".casefold()
    ranked: list[tuple[int, str, Path]] = []
    for candidate in candidates:
        if candidate == owner_path:
            continue
        if _animation_sequence_kind(candidate) == "pose":
            continue
        text = f"{_animation_display_group(content_root, candidate)} {candidate.stem}".casefold()
        score = _target_reaction_score(owner_text, text)
        if score < 999:
            ranked.append((score, candidate.stem.casefold(), candidate))
    if not ranked:
        return None
    return sorted(ranked)[0][2]


def _target_reaction_score(owner_text: str, target_text: str) -> int:
    if "attack" in owner_text or "charged" in owner_text:
        if "hitreact" in target_text and "front" in target_text and ("med" in target_text or "hvy" in target_text):
            return 0
        if "hitreact" in target_text:
            return 1
        if "death" in target_text:
            return 4
    if "dash" in owner_text:
        if "hitreact" in target_text and "back" in target_text:
            return 0
        if "hitreact" in target_text:
            return 2
    if "fire" in owner_text or "pistol" in owner_text or "rifle" in owner_text:
        if "hitreact" in target_text:
            return 1
    if "death" in target_text:
        return 6
    return 999


def _build_action_pair_animation_clip(
    owner_clip: Mapping[str, Any] | None,
    target_clip: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    owner_data = dict(owner_clip or {})
    target_data = dict(target_clip or {})
    owner_id = str(owner_data.get("id") or owner_data.get("name") or "owner")
    target_id = str(target_data.get("id") or target_data.get("name") or "target")
    owner_curves = owner_data.get("model_curves") if isinstance(owner_data.get("model_curves"), Mapping) else {}
    target_curves = target_data.get("model_curves") if isinstance(target_data.get("model_curves"), Mapping) else {}
    combined_curves: dict[str, Any] = {
        str(key): dict(value) if isinstance(value, Mapping) else value
        for key, value in owner_curves.items()
    }
    combined_curves.update(_target_animation_curves(target_curves))
    duration_ms = max(_clip_duration_ms(owner_data), _clip_duration_ms(target_data))
    sample_count = max(
        int(float(owner_data.get("sampled_frame_count") or owner_data.get("frame_count") or 0)),
        int(float(target_data.get("sampled_frame_count") or target_data.get("frame_count") or 0)),
        0,
    )
    return {
        "id": f"pair_{owner_id}__{target_id if target_curves else 'static_target'}",
        "name": f"{owner_id} + {target_id if target_curves else 'Static Target'}",
        "duration_ms": duration_ms,
        "sampled_frame_count": sample_count,
        "rotation_space": str(owner_data.get("rotation_space") or target_data.get("rotation_space") or "tiger_basis_quat_v1"),
        "source_mode": "action_sequencer_pair_clip",
        "owner_clip_id": owner_id,
        "target_clip_id": target_id if target_curves else "",
        "model_curves": combined_curves,
    }


def _target_animation_curves(curves: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in curves.items():
        target_key = _target_curve_key(str(key))
        if isinstance(value, Mapping):
            copied = dict(value)
            if copied.get("bone_name"):
                copied["bone_name"] = f"Target / {copied.get('bone_name')}"
        else:
            copied = value
        out[target_key] = copied
    return out


def _target_curve_key(key: str) -> str:
    text = str(key or "")
    if text.startswith("target_"):
        return text
    return f"target_{text}"


def _clip_duration_ms(clip: Mapping[str, Any]) -> float:
    try:
        return max(0.0, float(clip.get("duration_ms") or 0.0))
    except Exception:
        return 0.0


def _animation_sequence_kind(path: Path) -> str:
    stem = path.stem.casefold()
    if stem.startswith("am_"):
        return "action"
    if stem.startswith("mm_"):
        return "motion"
    if stem.startswith("mf_"):
        return "pose"
    return "other"


def _animation_sequence_priority(path: Path) -> int:
    kind = _animation_sequence_kind(path)
    if kind == "action":
        return 0
    if kind == "motion":
        return 1
    if kind == "pose":
        return 2
    return 9


def _animation_clip_is_pose(path: Path, clip: Mapping[str, Any] | None, sequence_plan: Mapping[str, Any] | None) -> bool:
    if _animation_sequence_kind(path) == "pose":
        return True
    playback = sequence_plan.get("playback") if isinstance(sequence_plan, Mapping) else {}
    duration = playback.get("duration_ms") if isinstance(playback, Mapping) else None
    if duration is None and isinstance(clip, Mapping):
        duration = clip.get("duration_ms")
    try:
        return float(duration or 0.0) > 0.0 and float(duration or 0.0) < OWNER_POSE_CLIP_DURATION_THRESHOLD_MS
    except Exception:
        return False


def _owner_animation_preview_safety_report(
    descriptor: Mapping[str, Any] | None,
    clip: Mapping[str, Any] | None,
    *,
    max_height_ratio: float = OWNER_ANIMATION_PREVIEW_MAX_GEOMETRY_HEIGHT_RATIO,
) -> dict[str, Any]:
    """Return whether a clip is safe to preview with the local GPU palette path."""

    if not isinstance(descriptor, Mapping) or not isinstance(clip, Mapping):
        return {"ok": True, "reason": "missing_descriptor_or_clip"}
    try:
        import numpy as np
        from app.ar_pbr.animation import skin_matrices_for_clip
    except Exception as exc:
        return {"ok": True, "reason": f"safety_check_unavailable:{type(exc).__name__}"}

    local_descriptor = dict(descriptor)
    local_descriptor["animation_clips"] = [dict(clip)]
    clip_id = str(clip.get("id") or clip.get("name") or "")
    track = {
        "id": "action_sequencer_preview_safety",
        "start_ms": 0,
        "animation": {
            "auto_play": True,
            "loop": False,
            "clip": clip_id,
            "speed": 1.0,
            "start_offset_ms": 0.0,
        },
    }
    try:
        duration_ms = max(0.0, float(clip.get("duration_ms") or 0.0))
    except Exception:
        duration_ms = 0.0
    sample_times = [0.0] if duration_ms <= 0.0 else [
        0.0,
        duration_ms * 0.25,
        duration_ms * 0.5,
        duration_ms * 0.75,
        duration_ms,
    ]
    geometries = [
        item for item in local_descriptor.get("geometries", []) or []
        if isinstance(item, Mapping)
        and item.get("skin_weights")
        and str(item.get("role_slot") or "actor_a") in {"", "actor_a"}
    ]
    if not geometries:
        return {"ok": True, "reason": "no_owner_skeletal_geometry"}

    worst: dict[str, Any] = {
        "geometry": "",
        "time_ms": 0.0,
        "height_ratio": 1.0,
        "base_height": 0.0,
        "animated_height": 0.0,
    }
    for time_ms in sample_times:
        skinning = skin_matrices_for_clip(local_descriptor, track, int(round(time_ms)))
        matrices = skinning.get("matrices") if isinstance(skinning, dict) else None
        if matrices is None:
            continue
        matrices_np = np.asarray(matrices, dtype=np.float64)
        if matrices_np.ndim != 3 or matrices_np.shape[1:] != (4, 4):
            continue
        for geometry in geometries:
            vertices = np.asarray(geometry.get("vertices") or [], dtype=np.float64)
            if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) <= 0:
                continue
            base_min = vertices.min(axis=0)
            base_max = vertices.max(axis=0)
            base_height = float(max(base_max[1] - base_min[1], 1.0e-6))
            sampled = _sample_skinned_geometry_points(vertices, geometry.get("skin_weights"), matrices_np)
            if sampled is None or len(sampled) <= 0:
                continue
            animated_min = sampled.min(axis=0)
            animated_max = sampled.max(axis=0)
            animated_height = float(animated_max[1] - animated_min[1])
            height_ratio = animated_height / base_height
            if height_ratio > float(worst["height_ratio"]):
                worst = {
                    "geometry": str(geometry.get("name") or geometry.get("id") or ""),
                    "time_ms": float(time_ms),
                    "height_ratio": float(height_ratio),
                    "base_height": float(base_height),
                    "animated_height": float(animated_height),
                    "base_y": [float(base_min[1]), float(base_max[1])],
                    "animated_y": [float(animated_min[1]), float(animated_max[1])],
                }

    ok = float(worst["height_ratio"]) <= float(max_height_ratio)
    return {
        "ok": bool(ok),
        "reason": "within_preview_bounds" if ok else "animated_geometry_bounds_exceeded",
        "max_height_ratio": float(max_height_ratio),
        "worst": worst,
        "source_mode": str(clip.get("source_mode") or clip.get("_exporter") or ""),
    }


def _sample_skinned_geometry_points(vertices, skin_weights: Any, matrices) -> Any:
    try:
        import numpy as np
    except Exception:
        return None
    rows = skin_weights if isinstance(skin_weights, list) else []
    if not rows:
        return None
    stride = max(1, int(len(vertices) // max(1, OWNER_ANIMATION_PREVIEW_SAMPLE_VERTICES)))
    indices = np.arange(0, len(vertices), stride, dtype=np.int64)
    sampled = vertices[indices]
    hv = np.concatenate([sampled, np.ones((len(sampled), 1), dtype=np.float64)], axis=1)
    out = np.zeros((len(sampled), 4), dtype=np.float64)
    total = np.zeros((len(sampled),), dtype=np.float64)
    for sample_idx, vertex_idx in enumerate(indices):
        influence_rows = _owner_skin_rows(rows[int(vertex_idx)] if int(vertex_idx) < len(rows) else None)
        slot_count = 0
        for bone_index, weight in influence_rows:
            if slot_count >= 4:
                break
            if weight <= 1.0e-8 or bone_index < 0 or bone_index >= len(matrices):
                continue
            out[sample_idx] += (matrices[int(bone_index)] @ hv[sample_idx]) * float(weight)
            total[sample_idx] += float(weight)
            slot_count += 1
    valid = total > 1.0e-8
    if not bool(np.any(valid)):
        return None
    result = sampled.copy()
    skinned = out[valid, :3]
    w = out[valid, 3:4]
    nonzero_w = np.abs(w[:, 0]) > 1.0e-8
    skinned[nonzero_w] = skinned[nonzero_w] / w[nonzero_w]
    result[valid] = skinned
    return result


def _owner_skin_rows(value: Any) -> list[tuple[int, float]]:
    if isinstance(value, Mapping):
        joints = value.get("joints")
        weights = value.get("weights")
        if isinstance(joints, (list, tuple)) and isinstance(weights, (list, tuple)):
            out: list[tuple[int, float]] = []
            for idx, joint in enumerate(joints):
                try:
                    bone_index = int(joint)
                    weight = float(weights[idx] if idx < len(weights) else 0.0)
                except Exception:
                    continue
                out.append((bone_index, weight))
            return out
    if isinstance(value, list):
        out = []
        for row in value:
            if not isinstance(row, Mapping):
                continue
            text = str(row.get("bone_id") or row.get("model_id") or row.get("bone_index") or row.get("joint") or "")
            if text.startswith("bone_"):
                text = text.split("_", 1)[1]
            try:
                out.append((int(text), float(row.get("weight", 0.0) or 0.0)))
            except Exception:
                continue
        return out
    return []


def _reset_owner_animation_preview_window(window: Any) -> None:
    try:
        timer = getattr(window, "_animation_timer", None)
        if timer is not None and hasattr(timer, "stop"):
            timer.stop()
    except Exception:
        pass
    try:
        setattr(window, "_animation_track", None)
        setattr(window, "_animation_pending_frame", None)
        current_generation = int(getattr(window, "_animation_generation", 0) or 0)
        setattr(window, "_animation_generation", current_generation + 1)
    except Exception:
        pass
    try:
        gl_widget = getattr(window, "_gl_widget", None)
        clear_skinning = getattr(gl_widget, "clear_skinning_matrices", None)
        if callable(clear_skinning):
            clear_skinning()
    except Exception:
        pass


def _animation_display_group(content_root: Path, path: Path) -> str:
    try:
        relative = path.relative_to(content_root)
    except ValueError:
        return path.parent.name
    parts = list(relative.parts)
    if len(parts) <= 2:
        return path.parent.name
    if "Anims" in parts:
        index = parts.index("Anims")
        folder_parts = parts[index + 1 : -1]
        return " / ".join(folder_parts) if folder_parts else "Anims"
    return " / ".join(parts[:-1])


def default_owner_render_capture_path(descriptor: OwnerRenderDescriptor) -> Path:
    root = Path(__file__).resolve().parents[1] / "debugCapture"
    project_stem = descriptor.project_path.stem or "ActionSequencer"
    owner = descriptor.owner_name or "Owner"
    return root / f"action_sequencer_{project_stem}_{owner}_owner_render.png"


def uasset_inspector_executable() -> Path:
    root = unreal_link_reference_roots()["uasset_inspector"].path
    return root / "src" / "UAssetInspector.App" / "bin" / "Debug" / "net8.0-windows" / "UAssetInspector.App.exe"


def render_owner_preview_frame(
    descriptor: OwnerRenderDescriptor,
    output_path: Path | str | None = None,
    *,
    timeout_s: float = 18.0,
) -> Path:
    if descriptor.render_asset_path is None:
        raise RuntimeError("Owner render mesh is not available.")
    asset_path = descriptor.render_asset_path
    if not asset_path.exists():
        raise RuntimeError(f"Owner render mesh does not exist: {asset_path}")

    exe = uasset_inspector_executable()
    if not exe.exists():
        raise RuntimeError(f"UAssetInspector executable was not found: {exe}")

    target = Path(output_path) if output_path is not None else default_owner_render_capture_path(descriptor)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.unlink()
    except FileNotFoundError:
        pass

    env = os.environ.copy()
    env["UASSETINSPECTOR_CAPTURE_FRAME"] = str(target)

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    process = subprocess.Popen(
        [str(exe), "--file", str(asset_path)],
        cwd=str(exe.parent),
        env=env,
        startupinfo=startupinfo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + max(2.0, float(timeout_s))
    try:
        while time.monotonic() < deadline:
            if target.exists() and target.stat().st_size > 0:
                return target
            if process.poll() is not None:
                break
            time.sleep(0.25)
        raise RuntimeError(f"Owner render capture was not produced: {target}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()


def open_uasset_inspector_for_owner(descriptor: OwnerRenderDescriptor) -> None:
    if descriptor.render_asset_path is None:
        raise RuntimeError("Owner render mesh is not available.")
    exe = uasset_inspector_executable()
    if not exe.exists():
        raise RuntimeError(f"UAssetInspector executable was not found: {exe}")
    subprocess.Popen(
        [str(exe), "--file", str(descriptor.render_asset_path)],
        cwd=str(exe.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class _OwnerRenderWorker(QThread):
    rendered = Signal(str)
    failed = Signal(str)

    def __init__(self, descriptor: OwnerRenderDescriptor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._descriptor = descriptor

    def run(self) -> None:
        try:
            path = render_owner_preview_frame(self._descriptor)
        except Exception as exc:  # pragma: no cover - exercised through UI smoke/manual QA
            self.failed.emit(str(exc))
            return
        self.rendered.emit(str(path))


class _OwnerAnimationClipExportWorker(QThread):
    exported = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        descriptor: OwnerRenderDescriptor,
        animation_path: Path,
        *,
        max_samples: int = 48,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._descriptor = descriptor
        self._animation_path = Path(animation_path)
        self._max_samples = max(2, int(max_samples))

    def run(self) -> None:
        try:
            clip = export_owner_unreal_animation_clip(
                self._descriptor,
                self._animation_path,
                max_samples=self._max_samples,
            )
        except Exception as exc:  # pragma: no cover - exercised through UI/manual QA
            self.failed.emit({
                "status": "export_failed",
                "animation_path": str(self._animation_path),
                "error": type(exc).__name__,
                "message": str(exc),
            })
            return
        self.exported.emit({
            "status": "animation_clip_exported",
            "animation_path": str(self._animation_path),
            "clip": clip,
            "summary": _animation_clip_summary(clip),
        })


class _OwnerAnimationClipBatchExportWorker(QThread):
    exported = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        descriptor: OwnerRenderDescriptor,
        animation_paths: list[Path],
        *,
        selected_path: Path | None = None,
        max_samples: int = 48,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._descriptor = descriptor
        self._animation_paths = [Path(path) for path in animation_paths]
        self._selected_path = Path(selected_path) if selected_path is not None else (self._animation_paths[0] if self._animation_paths else None)
        self._max_samples = max(2, int(max_samples))

    def run(self) -> None:
        try:
            results = export_owner_unreal_animation_clips_batch(
                self._descriptor,
                self._animation_paths,
                max_samples=self._max_samples,
            )
        except Exception as exc:  # pragma: no cover - exercised through UI/manual QA
            self.failed.emit({
                "status": "batch_export_failed",
                "error": type(exc).__name__,
                "message": str(exc),
            })
            return
        selected_key = str(self._selected_path) if self._selected_path is not None else ""
        selected = results.get(selected_key) if selected_key else None
        self.exported.emit({
            "status": "animation_clip_batch_exported",
            "selected_path": selected_key,
            "selected": selected if isinstance(selected, dict) else None,
            "results": results,
            "count": len(results),
            "cached_count": sum(1 for item in results.values() if item.get("status") == "cached"),
            "exported_count": sum(1 for item in results.values() if item.get("status") == "animation_clip_exported"),
            "failed_count": sum(1 for item in results.values() if item.get("status") == "export_failed"),
        })


def _animation_clip_summary(clip: dict[str, Any] | None) -> dict[str, Any]:
    data = clip if isinstance(clip, dict) else {}
    curves = data.get("model_curves") if isinstance(data.get("model_curves"), dict) else {}
    export_path = str(data.get("_export_path") or "")
    return {
        "id": str(data.get("id") or data.get("name") or ""),
        "name": str(data.get("name") or data.get("id") or ""),
        "duration_ms": float(data.get("duration_ms", 0.0) or 0.0),
        "frame_count": int(data.get("frame_count", 0) or 0),
        "sampled_frame_count": int(data.get("sampled_frame_count", 0) or 0),
        "bone_curve_count": len(curves),
        "source_mode": str(data.get("source_mode") or data.get("_exporter") or "cue4parse_animation"),
        "export_path": export_path,
    }


class _OwnerRenderCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._message = "Rendering Owner..."
        self.setMinimumSize(680, 430)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_render(self, path: Path | str) -> None:
        pixmap = QPixmap(str(path))
        self._pixmap = pixmap if not pixmap.isNull() else QPixmap()
        self._message = "" if not self._pixmap.isNull() else "Render image could not be loaded."
        self.update()

    def set_message(self, message: str) -> None:
        self._message = message
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
        bg.setColorAt(0.0, QColor("#0B0F16"))
        bg.setColorAt(0.55, QColor("#121923"))
        bg.setColorAt(1.0, QColor("#080A0E"))
        painter.fillRect(rect, bg)

        painter.setPen(QPen(QColor(255, 255, 255, 16), 1))
        horizon = rect.height() * 0.66
        for i in range(15):
            y = horizon + i * rect.height() * 0.035
            painter.drawLine(QPointF(0, y), QPointF(rect.width(), y))
        for i in range(-8, 16):
            x = rect.width() * 0.18 + i * rect.width() * 0.065
            painter.drawLine(QPointF(x, horizon), QPointF(x + rect.width() * 0.20, rect.height()))

        owner_x = rect.width() * 0.22
        owner_y = rect.height() * 0.81
        painter.setPen(QPen(QColor("#72F7A7"), 2))
        painter.drawLine(QPointF(owner_x, owner_y - 60), QPointF(owner_x, owner_y + 22))
        painter.drawEllipse(QPointF(owner_x, owner_y), 9, 9)
        painter.drawLine(QPointF(owner_x + 16, owner_y - 42), QPointF(owner_x + 120, owner_y - 42))
        painter.drawLine(QPointF(owner_x + 120, owner_y - 42), QPointF(owner_x + 102, owner_y - 52))
        painter.drawLine(QPointF(owner_x + 120, owner_y - 42), QPointF(owner_x + 102, owner_y - 32))
        painter.setFont(_font(10, bold=True))
        painter.drawText(QRectF(owner_x - 52, owner_y + 18, 150, 24), Qt.AlignmentFlag.AlignLeft, "OWNER LEFT")

        if not self._pixmap.isNull():
            max_w = rect.width() * 0.74
            max_h = rect.height() * 0.78
            scale = min(max_w / self._pixmap.width(), max_h / self._pixmap.height())
            draw_w = self._pixmap.width() * scale
            draw_h = self._pixmap.height() * scale
            x = rect.width() * 0.11
            y = (rect.height() - draw_h) * 0.43
            image_rect = QRectF(x, y, draw_w, draw_h)
            painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
            painter.drawRoundedRect(image_rect.adjusted(-8, -8, 8, 8), 8, 8)
            painter.drawPixmap(image_rect, self._pixmap, QRectF(self._pixmap.rect()))
        else:
            painter.setFont(_font(17, bold=True))
            painter.setPen(QColor("#EEF4FF"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._message)

        painter.setFont(_font(10))
        painter.setPen(QColor("#A8B2C1"))
        painter.drawText(
            QRectF(18, 16, rect.width() - 36, 28),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Owner-only render pass - Action Sequencer stage-left preview",
        )
        painter.end()


class ActionSequencerOwnerRenderWindow(QWidget):
    def __init__(self, project_path: Path | str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.descriptor = discover_owner_render_descriptor(project_path)
        self._worker: _OwnerRenderWorker | None = None
        self.setWindowTitle("Action Sequencer - Owner Render")
        self.resize(1160, 720)
        self.setObjectName("ActionSequencerOwnerRenderWindow")
        self.setStyleSheet(_window_qss())

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("ACTION SEQUENCER / OWNER RENDER", self)
        title.setObjectName("OwnerRenderTitle")
        header.addWidget(title, stretch=1)
        self._render_btn = QPushButton("Render Owner", self)
        self._render_btn.setIcon(app_icon("play", size=13))
        self._render_btn.setIconSize(icon_size(13))
        self._render_btn.clicked.connect(self.render_owner)
        header.addWidget(self._render_btn)
        self._inspector_btn = QPushButton("Open Inspector", self)
        self._inspector_btn.setIcon(unreal_engine_icon(14))
        self._inspector_btn.setIconSize(icon_size(14))
        self._inspector_btn.clicked.connect(self._open_inspector)
        header.addWidget(self._inspector_btn)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(10)
        self._canvas = _OwnerRenderCanvas(self)
        body.addWidget(self._canvas, stretch=1)
        body.addWidget(self._build_side_panel(), stretch=0)
        root.addLayout(body, stretch=1)

        self._status = QLabel("Ready.", self)
        self._status.setObjectName("OwnerRenderStatus")
        root.addWidget(self._status)

        QTimer.singleShot(120, self.render_owner)

    def render_owner(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if not self.descriptor.can_render:
            self._status.setText("Owner mesh is not available. Check the connected project path.")
            self._canvas.set_message("Owner mesh was not found.")
            return
        self._render_btn.setEnabled(False)
        self._canvas.set_message("Rendering Owner...")
        self._status.setText("Rendering BP_CombatCharacter owner mesh with UAssetInspector...")
        worker = _OwnerRenderWorker(self.descriptor, self)
        worker.rendered.connect(self._on_rendered)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda: self._render_btn.setEnabled(True))
        self._worker = worker
        worker.start()

    def _on_rendered(self, path: str) -> None:
        self._canvas.set_render(path)
        self._status.setText(f"Rendered Owner preview: {path}")

    def _on_failed(self, message: str) -> None:
        self._canvas.set_message("Owner render failed.")
        self._status.setText(message)

    def _open_inspector(self) -> None:
        try:
            open_uasset_inspector_for_owner(self.descriptor)
            self._status.setText("Opened UAssetInspector on the Owner render mesh.")
        except Exception as exc:
            self._status.setText(str(exc))

    def _build_side_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("OwnerRenderSidePanel")
        panel.setFixedWidth(345)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        heading = QLabel("Owner Target", panel)
        heading.setObjectName("OwnerRenderSideHeading")
        layout.addWidget(heading)

        for label, value in self.descriptor.summary_rows():
            layout.addWidget(_info_row(panel, label, value))

        if self.descriptor.diagnostics:
            diag = QLabel("\n".join(f"- {item}" for item in self.descriptor.diagnostics), panel)
            diag.setObjectName("OwnerRenderDiagnostics")
            diag.setWordWrap(True)
            layout.addWidget(diag)

        layout.addStretch(1)
        return panel


class _OwnerAnimationPanel(QFrame):
    animation_selected = Signal(object)
    animation_preview_requested = Signal(object)
    animation_cache_batch_requested = Signal(object)

    def __init__(self, descriptor: OwnerRenderDescriptor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.descriptor = descriptor
        self._content_root = descriptor.project_path.parent / "Content"
        self._all_paths = list(descriptor.animation_sequence_paths)
        self._category_filter = "all"
        self._category_buttons: dict[str, QPushButton] = {}
        self._active_slot = "owner"
        self._owner_selected_path = descriptor.action_candidate_path or descriptor.idle_animation_path
        self._target_recommended_path = _recommended_target_animation_path(
            self._owner_selected_path,
            self._all_paths,
            self._content_root,
        )
        self._target_selected_path: Path | None = None
        self._slot_buttons: dict[str, QPushButton] = {}
        self.setObjectName("OwnerAnimationPanel")
        self.setFixedWidth(OWNER_ANIMATION_PANEL_WIDTH)
        self.setStyleSheet(_owner_animation_panel_qss())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Owner Animations", self)
        title.setObjectName("OwnerAnimationTitle")
        layout.addWidget(title)

        self._count = QLabel(self._count_text(len(self._all_paths)), self)
        self._count.setObjectName("OwnerAnimationCount")
        layout.addWidget(self._count)

        slot_row = QHBoxLayout()
        slot_row.setSpacing(5)
        for label, key in (("Owner", "owner"), ("Target", "target")):
            button = QPushButton(label, self)
            button.setObjectName("OwnerAnimationSlotButton")
            button.setCheckable(True)
            button.setChecked(key == self._active_slot)
            button.clicked.connect(lambda _checked=False, slot_key=key: self._set_active_slot(slot_key))
            self._slot_buttons[key] = button
            slot_row.addWidget(button)
        layout.addLayout(slot_row)

        self._slot_summary = QLabel("", self)
        self._slot_summary.setObjectName("OwnerAnimationSlotSummary")
        self._slot_summary.setWordWrap(True)
        layout.addWidget(self._slot_summary)

        self._filter = QLineEdit(self)
        self._filter.setObjectName("OwnerAnimationFilter")
        self._filter.setPlaceholderText("Filter animations")
        self._filter.textChanged.connect(self._refresh)
        layout.addWidget(self._filter)

        filters = QFrame(self)
        filters.setObjectName("OwnerAnimationFilterButtons")
        filter_layout = QGridLayout(filters)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setHorizontalSpacing(5)
        filter_layout.setVerticalSpacing(5)
        for index, (label, key) in enumerate(OWNER_ANIMATION_FILTERS):
            button = QPushButton(label, filters)
            button.setObjectName("OwnerAnimationCategoryButton")
            button.setCheckable(True)
            button.setChecked(key == self._category_filter)
            button.clicked.connect(lambda _checked=False, filter_key=key: self._set_category_filter(filter_key))
            self._category_buttons[key] = button
            filter_layout.addWidget(button, index // 2, index % 2)
        layout.addWidget(filters)

        action_row = QHBoxLayout()
        action_row.setSpacing(5)

        self._play_pair_btn = QPushButton("Play Pair", self)
        self._play_pair_btn.setObjectName("OwnerAnimationPlayPairButton")
        self._play_pair_btn.setIcon(app_icon("play", size=12))
        self._play_pair_btn.setIconSize(icon_size(12))
        self._play_pair_btn.clicked.connect(self._on_play_pair_clicked)
        action_row.addWidget(self._play_pair_btn)

        self._cache_nearby_btn = QPushButton("Cache nearby", self)
        self._cache_nearby_btn.setObjectName("OwnerAnimationCacheButton")
        self._cache_nearby_btn.setIcon(app_icon("download", size=12))
        self._cache_nearby_btn.setIconSize(icon_size(12))
        self._cache_nearby_btn.clicked.connect(self._on_cache_nearby_clicked)
        action_row.addWidget(self._cache_nearby_btn)
        layout.addLayout(action_row)

        self._list = QListWidget(self)
        self._list.setObjectName("OwnerAnimationList")
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._list.currentItemChanged.connect(self._on_current_item_changed)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, stretch=1)

        hint = QLabel("Select an animation for the Owner action slot.", self)
        hint.setObjectName("OwnerAnimationHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._sequence_status = QLabel("No animation sequence loaded.", self)
        self._sequence_status.setObjectName("OwnerAnimationSequenceStatus")
        self._sequence_status.setWordWrap(True)
        layout.addWidget(self._sequence_status)

        self._refresh()
        self._select_default()
        self._update_slot_summary()

    def selected_animation_path(self) -> Path | None:
        return self.selected_owner_animation_path()

    def selected_owner_animation_path(self) -> Path | None:
        return self._owner_selected_path

    def selected_target_animation_path(self) -> Path | None:
        return self._target_selected_path

    def active_slot_animation_path(self) -> Path | None:
        if self._active_slot == "owner":
            return self._owner_selected_path
        return self._target_selected_path or self._target_recommended_path

    def preview_payload(self, *, play_once: bool = True, apply_frame_ms: int = 0) -> dict[str, Any]:
        preview_role = "target" if self._active_slot == "target" else "owner"
        owner_selection = self.selected_owner_animation_path()
        target_selection = self.selected_target_animation_path()
        selected_path = owner_selection if preview_role == "owner" else (target_selection or self._target_recommended_path)
        owner_preview_path = selected_path if preview_role == "owner" else None
        target_preview_path = selected_path if preview_role == "target" else None
        batch_paths: list[Path] = []
        for path in (selected_path, owner_selection, target_selection, self._target_recommended_path):
            if path is not None and path not in batch_paths:
                batch_paths.append(path)
        for path in self.preview_batch_paths(selected_path, limit=8):
            if path not in batch_paths:
                batch_paths.append(path)
        return {
            "animation_path": selected_path,
            "owner_animation_path": owner_preview_path,
            "target_animation_path": target_preview_path,
            "context_owner_animation_path": owner_selection,
            "context_target_animation_path": target_selection,
            "target_recommended_animation_path": self._target_recommended_path,
            "batch_paths": [str(path) for path in batch_paths],
            "clip": selected_path.stem if selected_path is not None else "",
            "target_clip": target_preview_path.stem if target_preview_path is not None else "",
            "active_slot": self._active_slot,
            "preview_role": preview_role,
            "apply_frame_ms": int(apply_frame_ms),
            "play_once": bool(play_once),
        }

    def pair_preview_payload(self, *, play_once: bool = True, apply_frame_ms: int = 0) -> dict[str, Any]:
        owner_path = self.selected_owner_animation_path()
        target_path = self.selected_target_animation_path()
        batch_paths: list[Path] = []
        for path in (owner_path, target_path):
            if path is not None and path not in batch_paths:
                batch_paths.append(path)
        for selected in (owner_path, target_path):
            for path in self.preview_batch_paths(selected, limit=6):
                if path not in batch_paths:
                    batch_paths.append(path)
        return {
            "animation_path": owner_path,
            "owner_animation_path": owner_path,
            "target_animation_path": target_path,
            "context_owner_animation_path": owner_path,
            "context_target_animation_path": target_path,
            "target_recommended_animation_path": self._target_recommended_path,
            "batch_paths": [str(path) for path in batch_paths],
            "clip": owner_path.stem if owner_path is not None else "",
            "target_clip": target_path.stem if target_path is not None else "",
            "active_slot": self._active_slot,
            "preview_role": "pair",
            "apply_frame_ms": int(apply_frame_ms),
            "play_once": bool(play_once),
        }

    def _current_list_animation_path(self) -> Path | None:
        item = self._list.currentItem()
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return Path(str(data)) if data else None

    def preview_batch_paths(self, selected: Path | None = None, *, limit: int = 10) -> list[Path]:
        selected = selected or self.active_slot_animation_path()
        if self._list.count() <= 0:
            return []
        current_row = self._list.currentRow()
        if selected is not None:
            for index in range(self._list.count()):
                item = self._list.item(index)
                data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
                if data and Path(str(data)) == selected:
                    current_row = index
                    break
        if current_row < 0:
            current_row = 0
        ordered_rows = [current_row]
        for offset in range(1, max(self._list.count(), int(limit))):
            before = current_row - offset
            after = current_row + offset
            if before >= 0:
                ordered_rows.append(before)
            if after < self._list.count():
                ordered_rows.append(after)
            if len(ordered_rows) >= int(limit):
                break
        out: list[Path] = []
        seen: set[str] = set()
        for row in ordered_rows:
            item = self._list.item(row)
            if item is None:
                continue
            data = item.data(Qt.ItemDataRole.UserRole)
            if not data:
                continue
            path = Path(str(data))
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            out.append(path)
        return out[: max(1, int(limit))]

    def set_sequence_status(self, message: str, *, state: str = "idle") -> None:
        self._sequence_status.setProperty("state", state)
        self._sequence_status.setText(message)
        self._sequence_status.style().unpolish(self._sequence_status)
        self._sequence_status.style().polish(self._sequence_status)

    def _refresh(self) -> None:
        query = self._filter.text().strip().casefold()
        current = self.active_slot_animation_path()
        visible_paths = [
            path for path in self._all_paths
            if _animation_browser_filter_matches(self._content_root, path, self._category_filter)
        ]
        self._list.blockSignals(True)
        try:
            self._list.clear()
            current_category = ""
            visible_count = 0
            for path in visible_paths:
                label = _animation_display_label(self._content_root, path)
                if query and query not in label.casefold():
                    continue
                category = _animation_browser_category(self._content_root, path)
                if category != current_category:
                    current_category = category
                    self._list.addItem(self._header_item(category))
                cache = owner_unreal_animation_clip_cache_status(self.descriptor, path)
                is_ready_cache = bool(cache.get("exists") and cache.get("fresh") and cache.get("validated"))
                prefix = "✓" if is_ready_cache else "○"
                item = QListWidgetItem(f"{prefix} {_animation_browser_item_label(self._content_root, path)}")
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                item.setData(Qt.ItemDataRole.UserRole + 1, str(cache.get("cache_path") or ""))
                item.setData(Qt.ItemDataRole.UserRole + 2, "cached" if is_ready_cache else "uncached")
                if path == self.descriptor.idle_animation_path:
                    item.setToolTip("Default idle sequence")
                elif path == self.descriptor.action_candidate_path:
                    item.setToolTip("Primary action candidate")
                elif _animation_sequence_kind(path) == "pose":
                    item.setToolTip("Short pose or aim fragment. It applies a pose but may not visibly animate.")
                else:
                    item.setToolTip("Playable animation sequence")
                if is_ready_cache:
                    item.setToolTip(f"{item.toolTip()}\nCached preview clip is ready.")
                elif cache.get("exists") and cache.get("fresh") and cache.get("reason"):
                    item.setToolTip(
                        f"{item.toolTip()}\nExisting preview cache will be rebuilt: {cache.get('reason')}"
                    )
                else:
                    item.setToolTip(f"{item.toolTip()}\nPreview clip needs batch caching before instant playback.")
                self._list.addItem(item)
                visible_count += 1
                if current is not None and path == current:
                    self._list.setCurrentItem(item)
            self._count.setText(self._count_text(visible_count))
        finally:
            self._list.blockSignals(False)
        if self._list.currentItem() is None and self._list.count() > 0:
            first_row = self._first_selectable_row()
            if first_row >= 0:
                self._list.blockSignals(True)
                try:
                    self._list.setCurrentRow(first_row)
                finally:
                    self._list.blockSignals(False)

    def _set_category_filter(self, key: str) -> None:
        self._category_filter = str(key or "all")
        for button_key, button in self._category_buttons.items():
            button.setChecked(button_key == self._category_filter)
        self._refresh()

    def _set_active_slot(self, key: str) -> None:
        self._active_slot = "target" if str(key) == "target" else "owner"
        for button_key, button in self._slot_buttons.items():
            button.setChecked(button_key == self._active_slot)
        self._refresh()
        self._select_default()
        self._update_slot_summary()

    def _count_text(self, visible_count: int) -> str:
        motion_count = sum(1 for path in self._all_paths if _animation_sequence_kind(path) in {"action", "motion"})
        pose_count = sum(1 for path in self._all_paths if _animation_sequence_kind(path) == "pose")
        return f"{visible_count} shown / {motion_count} motion / {pose_count} pose"

    def _header_item(self, category: str) -> QListWidgetItem:
        item = QListWidgetItem(_animation_browser_category_label(category).upper())
        item.setData(Qt.ItemDataRole.UserRole + 3, "header")
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setForeground(QColor("#7FF2B1" if category == "combat" else "#8EA2BA"))
        item.setBackground(QColor("#0E1622"))
        item.setFont(_font(9, bold=True))
        return item

    def _first_selectable_row(self) -> int:
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is not None and item.data(Qt.ItemDataRole.UserRole):
                return index
        return -1

    def _select_default(self) -> None:
        preferred = self.active_slot_animation_path()
        if preferred is None:
            return
        for index in range(self._list.count()):
            item = self._list.item(index)
            data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            if data and Path(str(data)) == preferred:
                self._list.blockSignals(True)
                try:
                    self._list.setCurrentRow(index)
                finally:
                    self._list.blockSignals(False)
                return

    def _on_current_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if data:
            path = Path(str(data))
            self._set_selected_path_for_active_slot(path, auto_recommend_target=False)
            self.animation_selected.emit(self.preview_payload(play_once=False))

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not data:
            return
        path = Path(str(data))
        self._set_selected_path_for_active_slot(path, auto_recommend_target=self._active_slot == "owner")
        self.animation_selected.emit(self.preview_payload(play_once=False))
        self.animation_preview_requested.emit(self.preview_payload(play_once=True))

    def _on_play_pair_clicked(self) -> None:
        if self._owner_selected_path is None:
            self.set_sequence_status("Select an Owner animation before playing a pair.", state="error")
            return
        payload = self.pair_preview_payload(play_once=True)
        self.animation_selected.emit(payload)
        self.animation_preview_requested.emit(payload)

    def _on_cache_nearby_clicked(self) -> None:
        paths: list[Path] = []
        selected_path = self.active_slot_animation_path()
        for path in (selected_path, self._owner_selected_path, self._target_selected_path, self._target_recommended_path):
            if path is not None and path not in paths:
                paths.append(path)
        for path in self.preview_batch_paths(selected_path, limit=24):
            if path not in paths:
                paths.append(path)
        if paths:
            payload = self.preview_payload(play_once=False)
            payload["batch_paths"] = [str(path) for path in paths]
            self.animation_cache_batch_requested.emit(payload)

    def _set_selected_path_for_active_slot(self, path: Path, *, auto_recommend_target: bool) -> None:
        if self._active_slot == "target":
            self._target_selected_path = path
        else:
            self._owner_selected_path = path
            self._target_recommended_path = _recommended_target_animation_path(path, self._all_paths, self._content_root)
        self._update_slot_summary()

    def _update_slot_summary(self) -> None:
        owner = self._owner_selected_path.stem if self._owner_selected_path is not None else "None"
        if self._target_selected_path is not None:
            target = self._target_selected_path.stem
        elif self._target_recommended_path is not None:
            target = f"Static (suggest: {self._target_recommended_path.stem})"
        else:
            target = "Static"
        self._slot_summary.setText(f"Owner: {owner}\nTarget: {target}")


def open_action_sequencer_owner_render_window(owner: object, project_path: Path | str | None = None) -> QWidget:
    descriptor = discover_owner_render_descriptor(project_path)
    unreal_asset, preview_asset, stage_pair_error = _resolve_action_pair_preview_assets(descriptor)
    from app.ar_pbr.preview_window import ArPbrAssetPreviewWindow, preview_look_preset_settings
    from app.ar_pbr.render_profile import PROFILE_MARMOSET_PBR

    animation_panel = _OwnerAnimationPanel(descriptor)
    initial_lighting = {
        **preview_look_preset_settings("bloomed"),
        "render_profile": PROFILE_MARMOSET_PBR,
        "look_preset": "bloomed",
        "hdri_id": "studio_small_09",
        "show_environment_background": False,
        "ibl_exposure": 1.35,
        "ibl_rotation": 0.08,
        "light_azimuth": 38.0,
        "light_elevation": 48.0,
        "direct_strength": 0.62,
        "shadow_strength": 0.78,
        "shadow_pcf_radius": 1.8,
        "self_shadow_strength": 0.58,
        "shadow_catcher_opacity": 0.68,
        "reflection_catcher_opacity": 0.0,
        "contact_reflection_strength": 0.0,
        "surface_override_strength": 0.18,
        "surface_roughness": 0.36,
        "surface_reflectance": 0.62,
        "tone_mapping": "aces",
        "tone_exposure": 0.10,
        "tone_white_balance": 6800.0,
        "ambient_occlusion_mode": "screen",
        "ao_strength": 0.55,
    }

    window = ArPbrAssetPreviewWindow(
        preview_asset,
        parent=None,
        initial_lighting=initial_lighting,
        initial_view=OWNER_STAGE_PREVIEW_VIEW,
        left_panel=animation_panel,
        track_label=f"{descriptor.owner_name} Actor A/B",
        max_triangles=180_000,
        texture_max_size=1024,
        controls_mode="cubemap_only",
        display_title="CombatCharacter Action Pair",
        display_subtitle="Actor A stands left; Actor B target slot stands right, facing back toward Actor A.",
    )
    window.setWindowTitle("Action Sequencer - CombatCharacter AR/PBR Pair")
    setattr(window, "owner_render_descriptor", descriptor)
    setattr(window, "owner_unreal_ar_pbr_asset", unreal_asset)
    setattr(window, "action_sequencer_stage_pair_asset", preview_asset)
    if stage_pair_error:
        setattr(window, "action_sequencer_stage_pair_error", stage_pair_error)
    setattr(window, "owner_animation_panel", animation_panel)
    selected_animation = animation_panel.selected_animation_path()
    if selected_animation is not None:
        setattr(window, "owner_selected_animation_path", selected_animation)

    def _set_sequence_status(message: str, *, state: str = "idle") -> None:
        setter = getattr(animation_panel, "set_sequence_status", None)
        if callable(setter):
            setter(message, state=state)

    def _on_animation_selected(payload_or_path: object) -> None:
        preview_role = "owner"
        if isinstance(payload_or_path, Mapping):
            raw_role = str(payload_or_path.get("preview_role") or payload_or_path.get("active_slot") or "")
            preview_role = "pair" if raw_role == "pair" else "target" if raw_role == "target" else "owner"
            owner_path = payload_or_path.get("owner_animation_path")
            target_path = payload_or_path.get("target_animation_path")
            selected_path = payload_or_path.get("animation_path")
            if preview_role == "pair":
                path = Path(str(owner_path or selected_path)) if (owner_path or selected_path) else None
                target = Path(str(target_path)) if target_path else None
            elif preview_role == "target":
                path = None
                target = Path(str(target_path or selected_path)) if (target_path or selected_path) else None
            else:
                path = Path(str(owner_path or selected_path)) if (owner_path or selected_path) else None
                target = Path(str(target_path)) if target_path else None
        else:
            path = Path(str(payload_or_path)) if payload_or_path else None
            target = None
        if path is not None:
            setattr(window, "owner_selected_animation_path", path)
        if target is not None:
            setattr(window, "target_selected_animation_path", target)
        target_text = f" -> Target {target.stem}" if target is not None and preview_role != "target" else ""
        if preview_role == "target":
            selected_text = f"Selected Target: {target.stem if target is not None else 'None'}"
        elif preview_role == "pair":
            selected_text = f"Selected Pair: {path.stem if path is not None else 'None'}{target_text}"
        else:
            selected_text = f"Selected Owner: {path.stem if path is not None else 'None'}{target_text}"
        _set_sequence_status(selected_text, state="idle")
        status = getattr(window, "_status", None)
        if status is not None and hasattr(status, "setText"):
            status.setText(selected_text)

    def _on_animation_preview_requested(payload: dict[str, Any]) -> None:
        raw_role = str(payload.get("preview_role") or payload.get("active_slot") or "")
        preview_role = "pair" if raw_role == "pair" else "target" if raw_role == "target" else "owner"
        raw_selected_path = payload.get("animation_path")
        raw_owner_path = payload.get("owner_animation_path")
        raw_target_path = payload.get("target_animation_path")
        selected_path = Path(str(raw_selected_path)) if raw_selected_path else None
        owner_path = Path(str(raw_owner_path)) if raw_owner_path else None
        target_path = Path(str(raw_target_path)) if raw_target_path else None
        if preview_role == "pair":
            path = owner_path or selected_path
            owner_preview_path = path
            target_preview_path = target_path
        elif preview_role == "target":
            path = target_path or selected_path
            owner_preview_path = None
            target_preview_path = path
        else:
            path = owner_path or selected_path
            owner_preview_path = path
            target_preview_path = None
        if owner_preview_path is not None:
            setattr(window, "owner_selected_animation_path", path)
        if target_preview_path is not None:
            setattr(window, "target_selected_animation_path", target_preview_path)
        active_worker = getattr(window, "owner_animation_export_worker", None)
        worker_running = False
        if active_worker is not None and hasattr(active_worker, "isRunning"):
            try:
                worker_running = bool(active_worker.isRunning())
            except RuntimeError:
                worker_running = False
        if worker_running:
            status = getattr(window, "_status", None)
            if status is not None and hasattr(status, "setText"):
                status.setText("Animation export is already running. Wait for the current sequence.")
            _set_sequence_status("Export already running.", state="busy")
            return
        request = {
            **dict(payload),
            "preview_backend": OWNER_ANIMATION_PREVIEW_BACKEND,
            "ar_pbr_animation_enabled": True,
            "requires_unreal_playback": True,
            "reference_pipeline": ACTION_SEQUENCE_REFERENCE_PIPELINE,
        }
        setattr(window, "owner_animation_preview_request", request)
        clip = str(payload.get("clip") or (path.stem if path is not None else ""))
        if path is None:
            result = {
                "status": "export_failed",
                "reason": "missing_animation_path",
                "clip": clip,
                "preview_backend": OWNER_ANIMATION_PREVIEW_BACKEND,
                "ar_pbr_animation_enabled": True,
            }
            setattr(window, "owner_animation_preview_result", result)
            status = getattr(window, "_status", None)
            if status is not None and hasattr(status, "setText"):
                status.setText("Animation export failed: missing asset path")
            _set_sequence_status("Missing animation asset path.", state="error")
            return
        raw_batch_paths = payload.get("batch_paths")
        if isinstance(raw_batch_paths, (list, tuple)):
            batch_paths = [Path(str(item)) for item in raw_batch_paths if str(item)]
        else:
            batch_paths = []
        if path not in batch_paths:
            batch_paths.insert(0, path)
        if preview_role == "pair" and target_preview_path is not None and target_preview_path not in batch_paths:
            batch_paths.insert(1, target_preview_path)
        result = {
            "status": "caching_animation_batch",
            "clip": clip,
            "target_clip": str(payload.get("target_clip") or (target_preview_path.stem if target_preview_path is not None else "")),
            "preview_role": preview_role,
            "animation_path": str(path),
            "owner_animation_path": str(owner_preview_path or ""),
            "target_animation_path": str(target_preview_path or ""),
            "batch_paths": [str(item) for item in batch_paths],
            "preview_backend": OWNER_ANIMATION_PREVIEW_BACKEND,
            "ar_pbr_animation_enabled": True,
            "play_once": bool(payload.get("play_once", True)),
            "apply_frame_ms": int(payload.get("apply_frame_ms", 0) or 0),
            "requires_gpu_palette_renderer": True,
        }
        setattr(window, "owner_animation_preview_result", result)
        status = getattr(window, "_status", None)
        if status is not None and hasattr(status, "setText"):
            status.setText(f"Caching animation batch: {clip} + {max(0, len(batch_paths) - 1)} nearby")
        _set_sequence_status(f"Caching batch: {len(batch_paths)} sequence(s)", state="busy")

        worker = _OwnerAnimationClipBatchExportWorker(descriptor, batch_paths, selected_path=path, parent=window)

        def _on_exported(event: dict[str, Any]) -> None:
            results_by_path = event.get("results") if isinstance(event, dict) and isinstance(event.get("results"), dict) else {}
            selected_event = event.get("selected") if isinstance(event, dict) else None
            owner_event = (
                results_by_path.get(str(owner_preview_path))
                if isinstance(results_by_path, dict) and owner_preview_path is not None
                else None
            )
            if not isinstance(owner_event, dict):
                owner_event = selected_event if preview_role in {"owner", "pair"} and isinstance(selected_event, dict) else None
            target_event = (
                results_by_path.get(str(target_preview_path))
                if isinstance(results_by_path, dict) and target_preview_path is not None
                else None
            )
            if not isinstance(target_event, dict):
                target_event = selected_event if preview_role == "target" and isinstance(selected_event, dict) else None
            exported_owner_clip = owner_event.get("clip") if isinstance(owner_event, dict) else None
            exported_target_clip = target_event.get("clip") if isinstance(target_event, dict) else None
            selected_exported_clip = exported_target_clip if preview_role == "target" else exported_owner_clip
            exported_clip = _build_action_pair_animation_clip(
                exported_owner_clip if isinstance(exported_owner_clip, dict) else None,
                exported_target_clip if isinstance(exported_target_clip, dict) else None,
            )
            summary = _animation_clip_summary(exported_clip)
            sequence_plan = build_owner_animation_sequence(
                exported_clip if isinstance(exported_clip, dict) else None,
                animation_path=path,
                play_once=bool(payload.get("play_once", True)),
                apply_frame_ms=int(payload.get("apply_frame_ms", 0) or 0),
                backend=OWNER_ANIMATION_PREVIEW_BACKEND,
            )
            sequence_info = animation_sequence_summary(sequence_plan)
            is_pose_clip = _animation_clip_is_pose(
                path,
                selected_exported_clip if isinstance(selected_exported_clip, dict) else exported_clip if isinstance(exported_clip, dict) else None,
                sequence_plan,
            )
            playback_result: dict[str, Any] | None = None
            playback_error = ""
            should_play = bool(payload.get("play_once", True))
            preview_safety_report: dict[str, Any] | None = None
            if should_play and isinstance(exported_clip, dict) and sequence_plan.get("status") == "ready":
                preview_descriptor = getattr(window, "_descriptor", None)
                if not isinstance(preview_descriptor, Mapping):
                    preview_descriptor = None
                preview_safety_report = _owner_animation_preview_safety_report(preview_descriptor, exported_clip)
                if not preview_safety_report.get("ok", True):
                    _reset_owner_animation_preview_window(window)
                    playback_result = {
                        "status": "blocked_by_preview_safety",
                        "clip": str(exported_clip.get("id") or exported_clip.get("name") or clip),
                        "reason": preview_safety_report.get("reason"),
                        "safety": preview_safety_report,
                    }
                    playback_error = "unsafe evaluated animation bounds"
                    should_play = False
            if should_play and isinstance(exported_clip, dict) and sequence_plan.get("status") == "ready":
                try:
                    attach = getattr(window, "attach_animation_clip", None)
                    apply_once = getattr(window, "apply_animation_preview_once", None)
                    apply_pose = getattr(window, "apply_animation_pose_frame", None)
                    if callable(attach):
                        attach(exported_clip)
                    if is_pose_clip and callable(apply_pose):
                        playback_result = apply_pose(
                            str(exported_clip.get("id") or exported_clip.get("name") or clip),
                            time_ms=int(payload.get("apply_frame_ms", 0) or 0),
                        )
                    elif callable(apply_once):
                        playback_result = apply_once(
                            str(exported_clip.get("id") or exported_clip.get("name") or clip),
                            duration_ms=float(sequence_info.get("duration_ms") or 0.0) or None,
                        )
                except Exception as exc:
                    playback_error = str(exc)
            result = {
                "status": "animation_clip_batch_exported",
                "clip": clip,
                "target_clip": str(payload.get("target_clip") or (target_preview_path.stem if target_preview_path is not None else "")),
                "preview_role": preview_role,
                "animation_path": str(path),
                "owner_animation_path": str(owner_preview_path or ""),
                "target_animation_path": str(target_preview_path or ""),
                "batch_paths": [str(item) for item in batch_paths],
                "preview_backend": OWNER_ANIMATION_PREVIEW_BACKEND,
                "ar_pbr_animation_enabled": True,
                "requires_gpu_palette_renderer": True,
                "play_once": bool(payload.get("play_once", True)),
                "apply_frame_ms": int(payload.get("apply_frame_ms", 0) or 0),
                "reference_pipeline": ACTION_SEQUENCE_REFERENCE_PIPELINE,
                "sequence_plan": sequence_plan,
                "sequence_summary": sequence_info,
                "sequence_kind": "pose" if is_pose_clip else _animation_sequence_kind(path),
                "pair_clip": str(exported_clip.get("id") or exported_clip.get("name") or ""),
                "owner_clip_export": exported_owner_clip,
                "target_clip_export": exported_target_clip,
                "playback_result": playback_result,
                "playback_error": playback_error,
                "preview_safety_report": preview_safety_report,
                "batch_count": int(event.get("count", 0) or 0) if isinstance(event, dict) else 0,
                "cached_count": int(event.get("cached_count", 0) or 0) if isinstance(event, dict) else 0,
                "exported_count": int(event.get("exported_count", 0) or 0) if isinstance(event, dict) else 0,
                "failed_count": int(event.get("failed_count", 0) or 0) if isinstance(event, dict) else 0,
                "summary": dict(summary) if isinstance(summary, dict) else _animation_clip_summary(exported_clip),
            }
            setattr(window, "owner_animation_preview_result", result)
            setattr(window, "owner_animation_clip_export", exported_clip)
            setattr(window, "target_animation_clip_export", exported_target_clip)
            setattr(window, "owner_animation_sequence_plan", sequence_plan)
            refresh = getattr(animation_panel, "_refresh", None)
            if callable(refresh):
                refresh()
            status = getattr(window, "_status", None)
            if status is not None and hasattr(status, "setText"):
                if isinstance(playback_result, dict) and playback_result.get("status") == "blocked_by_preview_safety":
                    status.setText(
                        f"Animation preview blocked: {clip} produced unsafe skinning bounds; kept bind pose"
                    )
                elif playback_error:
                    status.setText(f"Animation sequence ready but playback failed: {playback_error}")
                elif isinstance(playback_result, dict) and playback_result.get("status") == "pose_applied":
                    status.setText(
                        f"Pose fragment applied: {clip} "
                        f"({sequence_info.get('sample_count', 0)} samples, {sequence_info.get('bone_count', 0)} bones)"
                    )
                elif isinstance(playback_result, dict) and playback_result.get("status") == "playing":
                    status.setText(
                        f"Playing animation sequence: {clip} "
                        f"({sequence_info.get('sample_count', 0)} samples, {sequence_info.get('bone_count', 0)} bones, "
                        f"batch {result['cached_count']} cached/{result['exported_count']} exported)"
                    )
                else:
                    status.setText(
                        f"Animation sequence ready: {clip} "
                        f"({sequence_info.get('sample_count', 0)} samples, {sequence_info.get('bone_count', 0)} bones, "
                        f"batch {result['cached_count']} cached/{result['exported_count']} exported)"
                    )
            duration_s = float(sequence_info.get("duration_ms") or 0.0) / 1000.0
            panel_state = "error" if playback_error else "ready"
            if isinstance(playback_result, dict) and playback_result.get("status") == "blocked_by_preview_safety":
                playback_suffix = " / preview blocked"
            elif isinstance(playback_result, dict) and playback_result.get("status") == "pose_applied":
                playback_suffix = " / pose applied"
            elif isinstance(playback_result, dict) and playback_result.get("status") == "playing":
                playback_suffix = " / playing once"
            else:
                playback_suffix = ""
            _set_sequence_status(
                f"Ready: {clip} / {duration_s:.2f}s / "
                f"{sequence_info.get('sample_count', 0)} samples / {sequence_info.get('bone_count', 0)} bones"
                f"{playback_suffix} / batch {result['cached_count']} cached, {result['exported_count']} exported",
                state=panel_state,
            )

        def _on_failed(event: dict[str, Any]) -> None:
            result = {
                "status": "export_failed",
                "clip": clip,
                "preview_role": preview_role,
                "animation_path": str(path),
                "owner_animation_path": str(owner_preview_path or ""),
                "target_animation_path": str(target_preview_path or ""),
                "preview_backend": OWNER_ANIMATION_PREVIEW_BACKEND,
                "ar_pbr_animation_enabled": True,
                "requires_gpu_palette_renderer": True,
                "error": str(event.get("error") or "RuntimeError") if isinstance(event, dict) else "RuntimeError",
                "message": str(event.get("message") or event) if isinstance(event, dict) else str(event),
            }
            setattr(window, "owner_animation_preview_result", result)
            status = getattr(window, "_status", None)
            if status is not None and hasattr(status, "setText"):
                status.setText(f"Animation export failed: {result['message']}")
            _set_sequence_status(f"Failed: {result['message']}", state="error")

        def _on_finished() -> None:
            if getattr(window, "owner_animation_export_worker", None) is worker:
                setattr(window, "owner_animation_export_worker", None)
            worker.deleteLater()

        worker.exported.connect(_on_exported)
        worker.failed.connect(_on_failed)
        worker.finished.connect(_on_finished)
        setattr(window, "owner_animation_export_worker", worker)
        worker.start()

    animation_panel.animation_selected.connect(_on_animation_selected)
    animation_panel.animation_preview_requested.connect(_on_animation_preview_requested)
    animation_panel.animation_cache_batch_requested.connect(_on_animation_preview_requested)
    setattr(owner, "_action_sequencer_owner_render_window", window)
    window.show()
    window.raise_()
    window.activateWindow()
    return window


def _resolve_action_pair_preview_assets(descriptor: OwnerRenderDescriptor) -> tuple[Path, Path, str]:
    cached_stage_pair = default_action_sequencer_stage_pair_path(descriptor)
    unreal_asset = default_owner_unreal_ar_pbr_path(descriptor)
    if (
        cached_stage_pair.exists()
        and cached_stage_pair.stat().st_size > 0
        and _action_pair_stage_cache_usable(cached_stage_pair)
    ):
        return unreal_asset if unreal_asset.exists() else cached_stage_pair, cached_stage_pair, "using_cached_stage_pair"

    if not unreal_asset.exists() or unreal_asset.stat().st_size <= 0:
        unreal_asset = export_owner_unreal_ar_pbr_asset(descriptor)
    preview_asset = unreal_asset
    stage_pair_error = ""
    try:
        preview_asset = write_action_sequencer_stage_pair_asset(unreal_asset, descriptor)
    except Exception as exc:
        stage_pair_error = str(exc)
    return unreal_asset, preview_asset, stage_pair_error


def _action_pair_stage_cache_usable(path: Path) -> bool:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return False
    descriptor = payload.get("descriptor") if isinstance(payload, Mapping) else None
    if not isinstance(descriptor, Mapping):
        descriptor = payload if isinstance(payload, Mapping) else None
    if not isinstance(descriptor, Mapping):
        return False
    metadata = descriptor.get("metadata") if isinstance(descriptor.get("metadata"), Mapping) else {}
    stage = metadata.get("action_sequencer_stage_pair") if isinstance(metadata.get("action_sequencer_stage_pair"), Mapping) else {}
    offset = 0
    for role in stage.get("roles") or []:
        if not isinstance(role, Mapping) or str(role.get("id") or "") != "actor_b":
            continue
        try:
            offset = int(role.get("target_bone_index_offset") or 0)
        except Exception:
            offset = 0
        break
    if offset <= 0:
        return False
    saw_target_skinning = False
    for geometry in descriptor.get("geometries") or []:
        if not isinstance(geometry, Mapping) or str(geometry.get("role_slot") or "") != "actor_b":
            continue
        rows = geometry.get("skin_weights")
        if not isinstance(rows, list) or not rows:
            continue
        saw_target_skinning = True
        for row in rows[:64]:
            for bone_index in _skin_weight_row_indices(row):
                if 0 <= bone_index < offset:
                    return False
    return saw_target_skinning


def _skin_weight_row_indices(value: Any) -> list[int]:
    out: list[int] = []
    if isinstance(value, Mapping):
        for key in ("bone_index", "joint", "joint_index"):
            if key in value:
                try:
                    out.append(int(value.get(key)))
                except Exception:
                    pass
        joints = value.get("joints")
        if isinstance(joints, list):
            for item in joints:
                try:
                    out.append(int(item))
                except Exception:
                    pass
        return out
    if isinstance(value, list):
        for item in value:
            out.extend(_skin_weight_row_indices(item))
    return out


def _safe_rglob(root: Path, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    try:
        return sorted(root.rglob(pattern))
    except OSError:
        return []


def _first_existing(*paths: Path | None) -> Path | None:
    for path in paths:
        if path is not None and path.exists():
            return path
    return None


def _display_path(path: Path | None) -> str:
    if path is None:
        return "not found"
    return path.as_posix()


def _font(size: int, *, bold: bool = False) -> QFont:
    font = QFont("Segoe UI")
    font.setPixelSize(size)
    font.setBold(bold)
    return font


def _info_row(parent: QWidget, label: str, value: str) -> QWidget:
    row = QFrame(parent)
    row.setObjectName("OwnerRenderInfoRow")
    layout = QVBoxLayout(row)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.setSpacing(2)
    key = QLabel(label, row)
    key.setObjectName("OwnerRenderInfoKey")
    val = QLabel(value, row)
    val.setObjectName("OwnerRenderInfoValue")
    val.setWordWrap(True)
    layout.addWidget(key)
    layout.addWidget(val)
    return row


def _window_qss() -> str:
    return """
    QWidget#ActionSequencerOwnerRenderWindow {
        background: #090C11;
        color: #EAF0FA;
    }
    QLabel#OwnerRenderTitle {
        color: #F2F7FF;
        font-size: 13px;
        font-weight: 820;
        letter-spacing: 2px;
    }
    QLabel#OwnerRenderStatus {
        color: #9FAAB8;
        font-size: 10px;
        padding: 4px 2px;
    }
    QPushButton {
        color: #EAF0FA;
        background: #151A22;
        border: 1px solid #2D3542;
        border-radius: 5px;
        padding: 6px 10px;
        font-size: 10px;
        font-weight: 720;
    }
    QPushButton:hover {
        background: #202837;
        border-color: #5B6A7E;
    }
    QPushButton:disabled {
        color: #687180;
        background: #10141A;
        border-color: #202631;
    }
    QFrame#OwnerRenderSidePanel {
        background: #10141B;
        border: 1px solid #28303B;
        border-radius: 8px;
    }
    QLabel#OwnerRenderSideHeading {
        color: #72F7A7;
        font-size: 12px;
        font-weight: 840;
        letter-spacing: 1px;
    }
    QFrame#OwnerRenderInfoRow {
        background: #0C1016;
        border: 1px solid #222A35;
        border-radius: 5px;
    }
    QLabel#OwnerRenderInfoKey {
        color: #7F8A99;
        font-size: 9px;
        font-weight: 760;
        text-transform: uppercase;
    }
    QLabel#OwnerRenderInfoValue {
        color: #D8E0EC;
        font-size: 10px;
    }
    QLabel#OwnerRenderDiagnostics {
        color: #E5B45D;
        background: #19150B;
        border: 1px solid #463C22;
        border-radius: 5px;
        padding: 8px;
        font-size: 10px;
    }
    """


def _owner_animation_panel_qss() -> str:
    return """
    QFrame#OwnerAnimationPanel {
        background: #0D111A;
        border-right: 1px solid #242C3A;
    }
    QLabel#OwnerAnimationTitle {
        color: #F4F7FB;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 0px;
    }
    QLabel#OwnerAnimationCount,
    QLabel#OwnerAnimationHint {
        color: #8E9BAD;
        font-size: 10px;
    }
    QLabel#OwnerAnimationSlotSummary {
        color: #B7C7DB;
        background: #0A1019;
        border: 1px solid #1E2A3B;
        border-radius: 6px;
        padding: 6px 7px;
        font-size: 9px;
    }
    QLabel#OwnerAnimationSequenceStatus {
        color: #9DB2CF;
        background: #101724;
        border: 1px solid #273448;
        border-radius: 6px;
        padding: 7px 8px;
        font-size: 10px;
    }
    QLabel#OwnerAnimationSequenceStatus[state="busy"] {
        color: #F5D485;
        border-color: #68542A;
        background: #1B170E;
    }
    QLabel#OwnerAnimationSequenceStatus[state="ready"] {
        color: #B7F6D2;
        border-color: #2E6B52;
        background: #0D1B18;
    }
    QLabel#OwnerAnimationSequenceStatus[state="error"] {
        color: #FFB7B7;
        border-color: #703238;
        background: #211012;
    }
    QLineEdit#OwnerAnimationFilter {
        color: #E8EEF7;
        background: #121824;
        border: 1px solid #2A3445;
        border-radius: 5px;
        padding: 7px 8px;
        selection-background-color: #2E6CE6;
    }
    QPushButton#OwnerAnimationPlayPairButton,
    QPushButton#OwnerAnimationCacheButton {
        color: #DDE8F7;
        background: #121A24;
        border: 1px solid #2A3A4D;
        border-radius: 5px;
        padding: 5px 7px;
        font-size: 10px;
        font-weight: 760;
    }
    QPushButton#OwnerAnimationSlotButton {
        color: #AEBBD0;
        background: #101722;
        border: 1px solid #263346;
        border-radius: 5px;
        padding: 6px 4px;
        font-size: 10px;
        font-weight: 820;
    }
    QPushButton#OwnerAnimationSlotButton:hover {
        color: #FFFFFF;
        border-color: #48627F;
        background: #152033;
    }
    QPushButton#OwnerAnimationSlotButton:checked {
        color: #081019;
        background: #72F7A7;
        border-color: #B7FFD4;
    }
    QPushButton#OwnerAnimationCategoryButton {
        color: #AAB7C8;
        background: #0F1621;
        border: 1px solid #253044;
        border-radius: 5px;
        padding: 5px 4px;
        font-size: 9px;
        font-weight: 760;
    }
    QPushButton#OwnerAnimationCategoryButton:hover {
        color: #E9F2FF;
        border-color: #3A4C68;
        background: #141E2C;
    }
    QPushButton#OwnerAnimationCategoryButton:checked {
        color: #FFFFFF;
        background: #1F4C7D;
        border-color: #65A5FF;
    }
    QListWidget#OwnerAnimationList {
        color: #DCE5F2;
        background: #090D14;
        border: 1px solid #202838;
        border-radius: 6px;
        outline: 0;
        padding: 4px;
    }
    QListWidget#OwnerAnimationList::item {
        border-radius: 4px;
        padding: 7px 8px;
        margin: 1px;
    }
    QListWidget#OwnerAnimationList::item:selected {
        color: #FFFFFF;
        background: #1F4C7D;
    }
    QListWidget#OwnerAnimationList::item:hover {
        background: #172235;
    }
    """


__all__ = [
    "ACTION_SEQUENCER_PROJECT_ENV",
    "OWNER_ANIMATION_PANEL_WIDTH",
    "OWNER_ANIMATION_PREVIEW_BACKEND",
    "DEFAULT_ACTION_SEQUENCER_PROJECT",
    "OWNER_STAGE_PREVIEW_VIEW",
    "ActionSequencerOwnerRenderWindow",
    "OwnerRenderDescriptor",
    "default_action_sequencer_project_path",
    "default_owner_ar_pbr_proxy_path",
    "default_owner_render_capture_path",
    "default_owner_unreal_ar_pbr_path",
    "discover_owner_render_descriptor",
    "export_owner_unreal_ar_pbr_asset",
    "open_action_sequencer_owner_render_window",
    "open_uasset_inspector_for_owner",
    "render_owner_preview_frame",
    "uasset_inspector_executable",
    "write_owner_ar_pbr_proxy_asset",
]
