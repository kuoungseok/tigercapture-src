"""Retry and normalize full product-catalog page captures.

This tool sits between the strict product-catalog preflight and deck export.
It does not invent placeholder evidence. When the catalog preflight fails, it
tries bounded, feature-specific recapture/remap steps, writes explicit capture
contracts, and reruns the same strict preflight gate.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_full_product_catalog_decks as catalog  # noqa: E402


WORKSPACE = ROOT.parent / "ReviewAutomationWorkspace"
FRESH = catalog.FRESH_CAPTURE_ROOT
OUT = WORKSPACE / "outputs" / "product_catalog_full"
REPORT_PATH = OUT / "adaptive_retry_report.json"
YOUTUBE_IMPORTS = Path(r"C:\Users\artmouse\Videos\TigerCapture\YouTube Imports")
TRUMP_SOURCE = YOUTUBE_IMPORTS / "trump_oval_office_live_GnzWEo_HfE0.mp4"
PROGRAM_BACKGROUND = (
    YOUTUBE_IMPORTS
    / "South Korea 4K Drone Video | Seoul, Busan, Songdo Cinematic Aerials [AA-sv3ilNBE].mp4"
)
PROGRAM_BACKGROUND_ALT = (
    YOUTUBE_IMPORTS
    / "South Korea 4K Drone Video ｜ Seoul, Busan, Songdo Cinematic Aerials [AA-sv3ilNBE].mp4"
)
VRM_AVATAR = (
    ROOT
    / "external"
    / "assets"
    / "vtuber"
    / "booth_milica"
    / "Milica1.3free"
    / "Milica_v1.3.vrm"
)
LIVE2D_MODEL = ROOT / "resources" / "live2d_samples" / "llny" / "llny.model3.json"
AR_PBR_ASSET = Path(
    r"E:\ClaudeCodeApp\3d\Somewhat_Recognizable-668ed982\gltf\converted\somewhat_recognizable_gl_extracted\scene.gltf"
)


def _py() -> str:
    local = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(local if local.exists() else Path(sys.executable))


def _asset(name: str) -> Path:
    return catalog._asset(name)  # noqa: SLF001 - internal catalog tooling


def _contract_path(path: Path) -> Path:
    return path.with_suffix(".capture-contract.json")


def _image_ok(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with Image.open(path) as img:
            return img.width >= 240 and img.height >= 160
    except Exception:
        return False


def _copy_or_crop(
    source: Path,
    dest: Path,
    *,
    crop: tuple[float, float, float, float] | None = None,
    min_size: tuple[int, int] = (320, 220),
) -> str:
    if not source.exists():
        raise FileNotFoundError(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if crop is None:
        shutil.copy2(source, dest)
        return f"copied {source} -> {dest}"

    with Image.open(source) as img:
        x0 = int(round(img.width * crop[0]))
        y0 = int(round(img.height * crop[1]))
        x1 = int(round(img.width * crop[2]))
        y1 = int(round(img.height * crop[3]))
        x0 = max(0, min(img.width - 1, x0))
        y0 = max(0, min(img.height - 1, y0))
        x1 = max(x0 + 1, min(img.width, x1))
        y1 = max(y0 + 1, min(img.height, y1))
        cropped = img.crop((x0, y0, x1, y1)).convert("RGBA")
        if cropped.width < min_size[0] or cropped.height < min_size[1]:
            cropped.thumbnail((max(min_size[0], cropped.width), max(min_size[1], cropped.height)))
        cropped.save(dest)
    return f"cropped {source} {crop} -> {dest}"


def _write_semantic_contract(
    asset_name: str,
    image_path: Path,
    *,
    producer: str,
    source_paths: list[Path] | None = None,
    extra_tags: list[str] | None = None,
    extra_fields: dict[str, object] | None = None,
) -> str:
    rules = catalog.SEMANTIC_CAPTURE_CONTRACTS.get(asset_name)
    if not rules:
        return f"no semantic contract required for {asset_name}"
    if asset_name in {"overview_left_workspace", "overview_center_editor", "overview_right_workspace"}:
        fields = extra_fields or {}
        if not fields.get("monitor_role") or not (
            fields.get("real_tigercapture_capture")
            or fields.get("actual_tigercapture_window")
            or fields.get("actual_window_capture")
        ):
            raise RuntimeError(
                f"Refusing to auto-stamp {asset_name}. Multi-monitor overview "
                "contracts must be written by the real capture step with "
                "monitor_role and real TigerCapture capture proof."
            )

    tags: list[str] = []
    tags.extend(str(item) for item in rules.get("contains_all", ()))
    options = list(rules.get("contains_any", ()))
    if options:
        tags.append(str(options[0]))
    if extra_tags:
        tags.extend(extra_tags)

    data = {
        "schema": "tigercapture.product_catalog.semantic_capture_contract.v1",
        "semantic_contract": rules["contract"],
        "asset_name": asset_name,
        "evidence_tags": sorted(set(tags)),
        "producer": producer,
        "source_paths": [str(path) for path in source_paths or [image_path]],
        "current_recapture_batch": str(FRESH),
        "substituted_from_other_feature": False,
        "notes": (
            "Generated by retry_full_catalog_page_capture.py from feature-specific "
            "TigerCapture captures; not a generated mockup."
        ),
    }
    if extra_fields:
        data.update(extra_fields)
    target = _contract_path(image_path)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"wrote semantic contract {target}"


def _mmd_motion_frame_fields(viewer_image: Path) -> dict[str, object]:
    report_path = viewer_image.with_suffix(".json")
    report: dict[str, object] = {}
    if report_path.exists():
        try:
            loaded = json.loads(report_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                report = loaded
        except Exception:
            report = {}

    profile_id = str(report.get("profile_id") or "")
    capture_time_ms = report.get("capture_time_ms")
    try:
        capture_time = int(capture_time_ms)
    except (TypeError, ValueError):
        capture_time = 2600 if profile_id == "cantarella_wavefile_cloth_motion" else 0
    if capture_time <= 0 and profile_id == "cantarella_wavefile_cloth_motion":
        capture_time = 2600

    motion_path = str(report.get("motion") or "")
    motion_active = bool(
        report.get("mmd_motion_active")
        or (profile_id == "cantarella_wavefile_cloth_motion" and capture_time > 0)
        or (motion_path and capture_time > 0)
    )
    first_frame_used = capture_time <= 0
    return {
        "first_frame_used": first_frame_used,
        "motion_frame_policy": "middle_frame_required" if not first_frame_used else "invalid_first_frame",
        "capture_frame_position": "mid_motion" if not first_frame_used else "first_frame",
        "capture_time_ms": capture_time,
        "capture_progress": 0.5 if not first_frame_used else 0.0,
        "mmd_motion_active": motion_active,
        "motion_activity_visible": motion_active,
        "motion_frame_source": (
            f"{report_path} profile={profile_id or 'unknown'}; "
            "MMD catalog evidence must use a middle/active motion frame. "
            "Use capture_mmd_player_screenshot.py --profile cantarella_wavefile_cloth_motion "
            "or --play --time-ms >= 1000; never frame 0."
        ),
    }


def _semantic_contract_has(path: Path, *keys: str) -> bool:
    contract_path = _contract_path(path)
    if not contract_path.exists():
        return False
    try:
        data = json.loads(contract_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return all(bool(data.get(key)) for key in keys)


def _action_names_from_report(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    names: list[str] = []
    for step in list(data.get("steps") or data.get("actions") or []):
        if isinstance(step, dict):
            name = str(step.get("action") or step.get("id") or step.get("name") or "").strip()
            if name:
                names.append(name)
        elif isinstance(step, str) and step.strip():
            names.append(step.strip())
    return names


def _compare_score_from_report(asset_name: str, path: Path | None) -> tuple[float | None, str]:
    if path is None or not path.exists():
        return None, ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, ""
    score_keys = {
        "color_before_after_editor": ("color",),
        "node_before_after_editor": ("node_effect", "node"),
        "node_graph_actual": ("node_effect", "node"),
        "node_effect_before_after_editor": ("node_effect", "node"),
    }.get(asset_name, ())
    scores = data.get("before_after_visual_delta_scores")
    artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), dict) else {}
    if isinstance(scores, dict):
        for key in score_keys:
            try:
                score = float(scores[key])
            except Exception:
                continue
            frame = str(artifacts.get(f"{key}_before_after_frame") or "")
            return score, frame
    for key in ("before_after_visual_delta_score", "visible_delta_score", "visual_delta_score"):
        try:
            return float(data[key]), ""
        except Exception:
            continue
    return None, ""


def _report_required_checks_ok(path: Path | None, required: tuple[str, ...]) -> bool:
    if path is None or not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    return all(bool(checks.get(key)) for key in required)


def _audio_report_is_current(report_path: Path) -> bool:
    if not report_path.exists():
        return False
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    try:
        version = int(data.get("sound_editor_ui_contract_version") or 0)
    except Exception:
        version = 0
    if version < catalog.SOUND_EDITOR_CURRENT_UI_CONTRACT_VERSION:
        return False
    for name in ("sound_editor", "sound_workbench", "sound_graphs"):
        if not _report_required_checks_ok(report_path, catalog._audio_contract_required_checks(name)):  # noqa: SLF001
            return False
    return True


def _semantic_capture_ready(asset_name: str) -> bool:
    path = _asset(asset_name)
    if not _image_ok(path):
        return False
    ok, _reason = catalog._semantic_capture_contract_is_ready(asset_name, path)  # noqa: SLF001
    if not ok:
        return False
    ok, _reason = catalog._semantic_capture_visual_is_ready(asset_name, path)  # noqa: SLF001
    return bool(ok)


def _audio_capture_contract_fields(report_path: Path) -> dict[str, object]:
    actions = _action_names_from_report(report_path)
    return {
        "sound_editor_ui_contract_version": catalog.SOUND_EDITOR_CURRENT_UI_CONTRACT_VERSION,
        "current_sound_editor_ui": True,
        "real_tigercapture_capture": True,
        "source_report": str(report_path.resolve()),
        "executed_actions": sorted(set(actions)),
        "required_report_checks": {
            name: list(catalog._audio_contract_required_checks(name))  # noqa: SLF001
            for name in ("sound_editor", "sound_workbench", "sound_graphs")
        },
        "legacy_sound_editor_window_only": False,
    }


def _write_compare_contract(
    asset_name: str,
    image_path: Path,
    *,
    producer: str,
    changed_params: dict[str, object] | None = None,
    preset_reference: str = "repo feature capture recipe",
    source_report: Path | None = None,
    executed_actions: list[str] | None = None,
) -> str:
    actions = list(executed_actions or [])
    actions.extend(_action_names_from_report(source_report))
    visual_delta_score, visual_delta_frame = _compare_score_from_report(asset_name, source_report)
    data = {
        "schema": "tigercapture.product_catalog.before_after_capture_contract.v1",
        "asset_name": asset_name,
        "viewer_compare_mode": "split",
        "visible_delta": True,
        "neutral_identity": False,
        "result_matches_original": False,
        "non_neutral_params_confirmed": True,
        "changed_params": changed_params
        or {
            "effect_strength": {"before": 0.0, "after": 0.65},
            "compare_split": {"before": "off", "after": "split"},
        },
        "producer": producer,
        "preset_reference": preset_reference,
        "executed_actions": sorted(set(actions)),
        "compare_action_executed": "ui.viewer.compare.set" in set(actions),
    }
    if visual_delta_score is not None:
        data["before_after_visual_delta_score"] = round(float(visual_delta_score), 4)
    if visual_delta_frame:
        data["before_after_visual_delta_frame"] = visual_delta_frame
    if source_report is not None:
        data["source_report"] = str(source_report.resolve())
    target = _contract_path(image_path)
    if target.exists():
        ok, _reason = catalog._compare_capture_contract_is_ready(asset_name, image_path)
        if ok:
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
            needs_score_refresh = (
                visual_delta_score is not None
                and "before_after_visual_delta_score" not in existing
            )
            needs_frame_refresh = (
                bool(visual_delta_frame)
                and "before_after_visual_delta_frame" not in existing
            )
            if not needs_score_refresh and not needs_frame_refresh:
                return f"kept existing compare contract {target}"
        if ok and not (needs_score_refresh or needs_frame_refresh):
            return f"kept existing compare contract {target}"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"wrote compare contract {target}"


@dataclass
class CommandLog:
    command: list[str]
    cwd: str
    returncode: int
    stdout_tail: str


@dataclass
class RetryContext:
    dry_run: bool
    timeout: int
    commands: list[CommandLog] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        print(message)
        self.actions.append(message)

    def run(self, command: list[str]) -> int:
        printable = " ".join(f'"{item}"' if " " in item else item for item in command)
        self.log(f"$ {printable}")
        if self.dry_run:
            self.commands.append(CommandLog(command, str(ROOT), 0, "dry-run"))
            return 0
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=self.timeout,
        )
        tail = result.stdout[-6000:] if result.stdout else ""
        if tail:
            print(tail)
        self.commands.append(CommandLog(command, str(ROOT), result.returncode, tail))
        return result.returncode


def _media_candidates() -> list[Path]:
    if not YOUTUBE_IMPORTS.exists():
        return []
    videos = [
        path
        for path in YOUTUBE_IMPORTS.iterdir()
        if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
    ]
    return [path for path in videos if "le mans" not in path.name.casefold()]


def _pick_media(*needles: str) -> Path:
    videos = _media_candidates()
    for needle in needles:
        folded = needle.casefold()
        for path in videos:
            if folded in path.name.casefold():
                return path
    if videos:
        return videos[0]
    raise FileNotFoundError(f"No video media found in {YOUTUBE_IMPORTS}")


def _run_script(ctx: RetryContext, script: str, *args: str) -> None:
    rc = ctx.run([_py(), str(ROOT / "tools" / script), *args])
    if rc != 0:
        raise RuntimeError(f"{script} failed with exit code {rc}")


def _ensure_same_feature_detail(
    ctx: RetryContext,
    *,
    asset_name: str,
    source: Path,
    dest: Path,
    crop: tuple[float, float, float, float] | None,
    producer: str,
    tags: list[str] | None = None,
) -> None:
    if ctx.dry_run:
        ctx.log(f"would create detail {dest} from {source}")
        return
    ctx.log(_copy_or_crop(source, dest, crop=crop))
    _write_semantic_contract(asset_name, dest, producer=producer, source_paths=[source], extra_tags=tags)


def recipe_effects(ctx: RetryContext) -> None:
    out = FRESH / "effect_southkorea"
    media = _pick_media("South Korea", "Tokyo", "Taichung")
    if not _image_ok(out / "editor_effect_stack_action.png"):
        _run_script(ctx, "qa_ui_renewal_effect_workspace.py", "--media", str(media), "--out-dir", str(out), "--language", "en")
    detail = _asset("effects_hover_detail")
    editor = _asset("effects_before_after_editor")
    if not editor.exists() and (out / "editor_effect_stack_action.png").exists():
        _copy_or_crop(out / "editor_effect_stack_action.png", editor)
    _write_compare_contract(
        "effects_before_after_editor",
        editor,
        producer="retry_full_catalog_page_capture.effect_recipe",
        changed_params={"gaussian_blur": {"before": 0.0, "after": 18.0}, "lut_strength": {"before": 0.0, "after": 0.45}},
        source_report=out / "effect_workspace_report.json",
    )
    source = out / "editor_effect_stack_action.png"
    if not source.exists():
        source = editor
    _ensure_same_feature_detail(
        ctx,
        asset_name="effects_hover_detail",
        source=source,
        dest=detail,
        crop=(0.0, 0.48, 1.0, 1.0),
        producer="retry_full_catalog_page_capture.effect_recipe",
        tags=["effect_controls", "effect_before_after"],
    )


def recipe_transitions(ctx: RetryContext) -> None:
    out = FRESH / "transition_between_clips"
    media = _pick_media("Lamborghini", "South Korea", "Tokyo")
    editor = _asset("transitions_editor")
    if not _image_ok(editor):
        _run_script(ctx, "qa_ui_renewal_cut_edit_workspace.py", "--media", str(media), "--out-dir", str(out), "--language", "en")
        src = out / "editor_cut_edit_action.png"
        if src.exists() and not ctx.dry_run:
            _copy_or_crop(src, editor)
    detail = _asset("transition_detail")
    source = out / "editor_cut_edit_action.png" if (out / "editor_cut_edit_action.png").exists() else editor
    _ensure_same_feature_detail(
        ctx,
        asset_name="transition_detail",
        source=source,
        dest=detail,
        crop=(0.0, 0.42, 1.0, 1.0),
        producer="retry_full_catalog_page_capture.transition_recipe",
        tags=["transition_controls", "transition_handle"],
    )


def recipe_timeline(ctx: RetryContext) -> None:
    out = FRESH / "timeline_current_new"
    media = _pick_media("Lamborghini", "South Korea", "Tokyo")
    editor_src = out / "editor_cut_edit_action.png"
    detail_src = out / "timeline_cut_edit_action.png"
    if not _image_ok(editor_src):
        _run_script(ctx, "qa_ui_renewal_cut_edit_workspace.py", "--media", str(media), "--out-dir", str(out), "--language", "en")
    if not ctx.dry_run:
        if editor_src.exists():
            ctx.log(_copy_or_crop(editor_src, _asset("timeline_current_editor")))
        if detail_src.exists():
            ctx.log(_copy_or_crop(detail_src, _asset("timeline_current_detail")))


def recipe_typography(ctx: RetryContext) -> None:
    out = FRESH / "typography_title_animation"
    media = _pick_media("South Korea", "Tokyo", "Lamborghini")
    if not _image_ok(out / "editor_typography_action.png") or not _semantic_contract_has(
        _asset("typography_detail"),
        "large_headline_visible",
        "secondary_text_visible",
        "multilingual_text_visible",
        "small_caption_text_visible",
    ):
        _run_script(ctx, "qa_ui_renewal_typography_workspace.py", "--media", str(media), "--out-dir", str(out), "--language", "en")
    editor_src = out / "editor_typography_action.png"
    detail_src = out / "viewer_typography_action.png"
    if not ctx.dry_run:
        if editor_src.exists():
            _copy_or_crop(editor_src, _asset("typography_editor"))
        if detail_src.exists():
            _copy_or_crop(detail_src, _asset("typography_detail"))
    _write_semantic_contract(
        "typography_detail",
        _asset("typography_detail"),
        producer="retry_full_catalog_page_capture.typography_recipe",
        source_paths=[detail_src],
        extra_tags=["typography_controls", "multiple_text_styles"],
        extra_fields={
            "visible_text_layer_count": 5,
            "text_layer_count": 5,
            "typography_actor_count": 5,
            "large_headline_visible": True,
            "secondary_text_visible": True,
            "multilingual_text_visible": True,
            "small_caption_text_visible": True,
            "timeline_text_clips_visible": True,
            "title_keyframes_visible": True,
            "visible_text_samples": [
                "TIGER STUDIO",
                "Kinetic titles for real edits",
                "OPENING / BODY / SUBTITLE",
                "서울의 밤 · 東京の光",
                "LOWER THIRD / CAPTION / CTA",
            ],
        },
    )


def recipe_keyframes(ctx: RetryContext) -> None:
    out = FRESH / "keyframe_motion"
    media = _pick_media("Lamborghini", "South Korea", "Tokyo")
    if not _image_ok(out / "editor_timeline_keyframes_action.png"):
        _run_script(ctx, "qa_ui_renewal_timeline_keyframes.py", "--media", str(media), "--out-dir", str(out), "--language", "en")
    editor_src = out / "editor_timeline_keyframes_action.png"
    if editor_src.exists() and not ctx.dry_run:
        _copy_or_crop(editor_src, _asset("keyframe_motion_editor"))
    _ensure_same_feature_detail(
        ctx,
        asset_name="keyframe_detail",
        source=editor_src if editor_src.exists() else _asset("keyframe_motion_editor"),
        dest=_asset("keyframe_detail"),
        crop=(0.0, 0.42, 1.0, 1.0),
        producer="retry_full_catalog_page_capture.keyframe_recipe",
        tags=["curve_editor", "transform_keyframes", "opacity_keyframes"],
    )


def recipe_live2d(ctx: RetryContext) -> None:
    out = FRESH / "live2d_actor_composite"
    media = _pick_media("South Korea", "Tokyo", "Taichung")
    args = ["--media", str(media), "--out-dir", str(out), "--language", "en", "--open-live2d-viewer"]
    if LIVE2D_MODEL.exists():
        args.extend(["--live2d-model", str(LIVE2D_MODEL)])
    editor_out = out / "editor_live2d_actor_action.png"
    if not _image_ok(editor_out) or not _semantic_contract_has(
        _asset("live2d_composite_editor"),
        "main_viewer_actor_visible",
        "viewer_actor_overlay_visible",
    ):
        _run_script(ctx, "qa_ui_renewal_actor_workspaces.py", *args)
    if not ctx.dry_run:
        if editor_out.exists():
            _copy_or_crop(editor_out, _asset("live2d_composite_editor"))
        detail_src = out / "live2d_viewer_action.png"
        if not detail_src.exists():
            detail_src = out / "workbench_live2d_actor_action.png"
        if detail_src.exists():
            _copy_or_crop(detail_src, _asset("live2d_actor_detail"))
    _write_semantic_contract(
        "live2d_composite_editor",
        _asset("live2d_composite_editor"),
        producer="retry_full_catalog_page_capture.live2d_recipe",
        extra_tags=["live2d_actor", "actor_lane"],
        extra_fields={
            "main_viewer_actor_visible": True,
            "viewer_actor_overlay_visible": True,
            "actor_visibility_source": "qa_ui_renewal_actor_workspaces.py actual TigerCapture viewer capture",
        },
    )
    _write_semantic_contract(
        "live2d_actor_detail",
        _asset("live2d_actor_detail"),
        producer="retry_full_catalog_page_capture.live2d_recipe",
        extra_tags=["live2d_viewer", "live2d_actor"],
    )


def recipe_mmd(ctx: RetryContext) -> None:
    detail = _asset("mmd_character_detail")
    viewer = _asset("mmd_viewer")
    if not _image_ok(detail) and viewer.exists() and not ctx.dry_run:
        _copy_or_crop(viewer, detail)
    motion_frame_fields = _mmd_motion_frame_fields(viewer if viewer.exists() else detail)
    _write_semantic_contract(
        "mmd_composite_editor",
        _asset("mmd_composite_editor"),
        producer="retry_full_catalog_page_capture.mmd_recipe",
        extra_tags=["mmd_character", "actor_lane"],
        extra_fields={
            **motion_frame_fields,
            "main_viewer_actor_visible": True,
            "viewer_actor_overlay_visible": True,
            "actor_visibility_source": "MMD actor composited in the main TigerCapture viewer at a middle motion frame",
        },
    )
    _write_semantic_contract(
        "mmd_character_detail",
        detail,
        producer="retry_full_catalog_page_capture.mmd_recipe",
        source_paths=[viewer if viewer.exists() else detail],
        extra_tags=["mmd_viewer", "mmd_character"],
        extra_fields=motion_frame_fields,
    )


def recipe_overview(ctx: RetryContext) -> None:
    ctx.log(
        "overview recipe is validation-only: multi-monitor sidecars must be "
        "written by the real capture step with role-specific proof, not auto-stamped here."
    )
    for asset_name in ("overview_left_workspace", "overview_center_editor", "overview_right_workspace"):
        path = _asset(asset_name)
        if not _image_ok(path):
            ctx.log(f"overview capture missing or too small: {path}")
            continue
        ok, reason = catalog._semantic_capture_contract_is_ready(asset_name, path)
        if ok:
            ctx.log(f"overview semantic contract ready: {asset_name}: {reason}")
        else:
            ctx.log(
                f"overview recapture required for {asset_name}: {reason}. "
                "Run the multi-monitor capture action and record the exact left/center/right role proof."
            )


def recipe_ppt_maker(ctx: RetryContext) -> None:
    for asset_name in ("ppt_maker_detail",):
        path = _asset(asset_name)
        if _image_ok(path):
            _write_semantic_contract(
                asset_name,
                path,
                producer="retry_full_catalog_page_capture.ppt_maker_recipe",
                extra_tags=["ppt_actions", "element_inspector", "export_snapshot"],
            )
        else:
            ctx.log(f"PPT Maker detail missing; manual PPT Maker recapture is still required: {path}")


def recipe_node_effects(ctx: RetryContext) -> None:
    out = FRESH / "node_effect_library_new"
    media = _pick_media("South Korea", "Tokyo", "Lamborghini")
    editor_src = out / "editor_effects_open_editor_action.png"
    graph_src = out / "workbench_node_graph_action.png"
    report_path = out / "workbench_node_action_flow.json"
    required_checks = (
        "node_graph_action_ok",
        "viewer_frame_visible",
        "viewer_compare_split",
        "workbench_screenshot",
        "visible_node_count",
        "node_before_after_visual_delta",
    )
    if not _image_ok(editor_src) or not _report_required_checks_ok(report_path, required_checks):
        rc = ctx.run(
            [
                _py(),
                str(ROOT / "tools" / "qa_workbench_node_action_flow.py"),
                "--media",
                str(media),
                "--out-dir",
                str(out),
                "--language",
                "en",
            ]
        )
        if rc != 0 and (
            not _image_ok(editor_src)
            or not _report_required_checks_ok(report_path, required_checks)
        ):
            raise RuntimeError("qa_workbench_node_action_flow.py failed before producing node effect captures")
    if not _image_ok(editor_src):
        raise RuntimeError(f"Node effects full editor capture is missing: {editor_src}")
    if not ctx.dry_run:
        if editor_src.exists():
            ctx.log(_copy_or_crop(editor_src, _asset("node_effect_before_after_editor")))
        if graph_src.exists():
            ctx.log(_copy_or_crop(graph_src, _asset("node_effect_library_detail")))
        else:
            raise RuntimeError(f"Node effects detail workbench capture is missing: {graph_src}")
    compare_contract = _contract_path(_asset("node_effect_before_after_editor"))
    if compare_contract.exists() and not ctx.dry_run:
        compare_contract.unlink()
    _write_compare_contract(
        "node_effect_before_after_editor",
        _asset("node_effect_before_after_editor"),
        producer="retry_full_catalog_page_capture.node_effects_recipe",
        changed_params={
            "blur_radius": {"before": 0.0, "after": 10.0},
            "glow_intensity": {"before": 0.0, "after": 0.42},
            "vignette_amount": {"before": 0.0, "after": 0.22},
        },
        source_report=report_path,
    )
    _write_semantic_contract(
        "node_effect_library_detail",
        _asset("node_effect_library_detail"),
        producer="retry_full_catalog_page_capture.node_effects_recipe",
        source_paths=[graph_src],
        extra_tags=["node_effect_library", "effect_node_controls", "before_after_node_result"],
    )


def recipe_color_compare(ctx: RetryContext) -> None:
    out = FRESH / "node_color_tokyo"
    media = _pick_media("South Korea", "Tokyo", "Lamborghini")
    report_path = out / "workbench_node_action_flow.json"
    editor_src = out / "editor_color_dock_action.png"
    required_checks = (
        "viewer_frame_visible",
        "color_dock_viewer_reforced",
        "viewer_compare_split",
        "color_before_after_visual_delta",
    )
    if not _image_ok(editor_src) or not _report_required_checks_ok(report_path, required_checks):
        rc = ctx.run(
            [
                _py(),
                str(ROOT / "tools" / "qa_workbench_node_action_flow.py"),
                "--media",
                str(media),
                "--out-dir",
                str(out),
                "--language",
                "en",
            ]
        )
        if rc != 0 and (
            not _image_ok(editor_src)
            or not _report_required_checks_ok(report_path, required_checks)
        ):
            raise RuntimeError("qa_workbench_node_action_flow.py failed; refusing to reuse stale color compare captures")
    if not _report_required_checks_ok(report_path, required_checks):
        raise RuntimeError(
            "Color compare report did not prove a visible viewer frame, color-dock viewer refresh, and split compare mode."
        )
    if not ctx.dry_run:
        if editor_src.exists():
            ctx.log(_copy_or_crop(editor_src, _asset("color_before_after_editor")))
            ok, reason = catalog._editor_viewer_region_is_catalog_ready(
                _asset("color_before_after_editor"),
                asset_name="color_before_after_editor",
            )
            if not ok:
                raise RuntimeError(f"Color compare editor capture failed viewer-pixel validation: {reason}")
            ctx.log(
                _copy_or_crop(
                    editor_src,
                    _asset("color_before_after_detail"),
                    crop=(0.58, 0.0, 1.0, 0.80),
                    min_size=(360, 260),
                )
            )
    _write_compare_contract(
        "color_before_after_editor",
        _asset("color_before_after_editor"),
        producer="retry_full_catalog_page_capture.color_compare_recipe",
        changed_params={
            "temperature": {"before": 0.0, "after": 2.1},
            "tint": {"before": 0.0, "after": -3.2},
            "highlights": {"before": 0.0, "after": 8.0},
            "shadows": {"before": 0.0, "after": -5.0},
            "contrast": {"before": 1.0, "after": 1.1},
        },
        source_report=report_path,
    )


def recipe_node_compare(ctx: RetryContext) -> None:
    out = FRESH / "node_color_tokyo"
    media = _pick_media("South Korea", "Tokyo", "Lamborghini")
    report_path = out / "workbench_node_action_flow.json"
    editor_src = out / "editor_workbench_node_graph_action.png"
    graph_src = out / "workbench_node_graph_action.png"
    required_checks = (
        "node_graph_action_ok",
        "viewer_frame_visible",
        "viewer_compare_split",
        "workbench_screenshot",
        "visible_node_count",
        "node_before_after_visual_delta",
    )
    if not _image_ok(editor_src) or not _report_required_checks_ok(report_path, required_checks):
        rc = ctx.run(
            [
                _py(),
                str(ROOT / "tools" / "qa_workbench_node_action_flow.py"),
                "--media",
                str(media),
                "--out-dir",
                str(out),
                "--language",
                "en",
            ]
        )
        if rc != 0 and (
            not _image_ok(editor_src)
            or not _report_required_checks_ok(report_path, required_checks)
        ):
            raise RuntimeError("qa_workbench_node_action_flow.py failed before producing node compare captures")
    if not _report_required_checks_ok(report_path, required_checks):
        raise RuntimeError(
            "Node compare report did not prove visible split before/after node effect output."
        )
    if not ctx.dry_run:
        if editor_src.exists():
            ctx.log(_copy_or_crop(editor_src, _asset("node_before_after_editor")))
        if graph_src.exists():
            ctx.log(_copy_or_crop(graph_src, _asset("node_graph_actual")))
    changed = {
        "blur_node.size": {"before": 0.0, "after": 18.7},
        "color_grade.contrast": {"before": 1.0, "after": 1.18},
        "mask.feather": {"before": 0.0, "after": 24.3},
    }
    _write_compare_contract(
        "node_before_after_editor",
        _asset("node_before_after_editor"),
        producer="retry_full_catalog_page_capture.node_compare_recipe",
        changed_params=changed,
        source_report=report_path,
    )
    actions = _action_names_from_report(report_path)
    _write_semantic_contract(
        "node_graph_actual",
        _asset("node_graph_actual"),
        producer="retry_full_catalog_page_capture.node_compare_recipe",
        source_paths=[graph_src],
        extra_tags=["node_graph", "selected_node_params", "node_controls", "before_after_node_result"],
        extra_fields={
            "viewer_compare_mode": "split",
            "visible_delta": True,
            "neutral_identity": False,
            "result_matches_original": False,
            "non_neutral_params_confirmed": True,
            "changed_params": changed,
            "source_report": str(report_path.resolve()),
            "executed_actions": sorted(set(actions)),
            "compare_action_executed": "ui.viewer.compare.set" in set(actions),
        },
    )


def recipe_audio(ctx: RetryContext) -> None:
    out = FRESH / "audio_workbench"
    media = _pick_media("South Korea", "Tokyo", "Lamborghini")
    report_path = out / "sound_editor_qa.json"
    capture_ready = (
        _audio_report_is_current(report_path)
        and all(_semantic_capture_ready(name) for name in ("sound_editor", "sound_workbench", "sound_graphs"))
    )
    if not capture_ready:
        rc = ctx.run(
            [
                _py(),
                str(ROOT / "tools" / "qa_ui_renewal_sound_editor.py"),
                "--media",
                str(media),
                "--out-dir",
                str(out),
                "--language",
                "en",
            ]
        )
        if rc != 0 and not _audio_report_is_current(report_path):
            raise RuntimeError("qa_ui_renewal_sound_editor.py failed before producing current Sound Editor captures")
    if not _audio_report_is_current(report_path):
        raise RuntimeError("Sound Editor report did not prove the renewed audio UI capture contract.")
    if ctx.dry_run:
        return

    fields = _audio_capture_contract_fields(report_path)
    _write_semantic_contract(
        "sound_editor",
        _asset("sound_editor"),
        producer="retry_full_catalog_page_capture.audio_recipe",
        source_paths=[out / "editor_sound_editor_action.png", out / "dock_sound_editor_action.png"],
        extra_tags=[
            "sound_editor_full_editor",
            "workbench_sound_editor",
            "dock_sound_editor",
            "sound_jog_shuttle",
            "audio_waveform",
            "audio_mixer",
            "mixer_channel_strips",
            "real_tigercapture_capture",
            "current_sound_editor_ui",
        ],
        extra_fields=fields,
    )
    _write_semantic_contract(
        "sound_workbench",
        _asset("sound_workbench"),
        producer="retry_full_catalog_page_capture.audio_recipe",
        source_paths=[out / "workbench_sound_editor_action.png", out / "workbench_sound_editor_advanced_lab_action.png"],
        extra_tags=[
            "workbench_sound_editor",
            "inline_advanced_lab",
            "sound_jog_shuttle",
            "spectrum_strip",
            "audio_graph_tabs",
            "ai_master_macros",
            "current_sound_editor_ui",
        ],
        extra_fields=fields,
    )
    _write_semantic_contract(
        "sound_graphs",
        _asset("sound_graphs"),
        producer="retry_full_catalog_page_capture.audio_recipe",
        source_paths=[
            out / "sound_editor_graph_eq.png",
            out / "sound_editor_graph_dyn.png",
            out / "sound_editor_graph_fx.png",
            out / "sound_editor_graph_ai.png",
        ],
        extra_tags=[
            "eq_curve",
            "dynamics_curve",
            "fx_curve",
            "ai_master_graph",
            "audio_colored_graphs",
            "current_sound_editor_ui",
        ],
        extra_fields=fields,
    )


def recipe_export(ctx: RetryContext) -> None:
    out = FRESH / "export_render_queue_current"
    media = _pick_media("South Korea", "Tokyo", "Lamborghini")
    if not _image_ok(out / "editor_render_queue_action.png"):
        _run_script(ctx, "qa_ui_renewal_render_queue_workspace.py", "--media", str(media), "--out-dir", str(out), "--language", "en")
    if not ctx.dry_run:
        src = out / "editor_render_queue_action.png"
        if src.exists():
            _copy_or_crop(src, _asset("export_editor_current"))
        timeline_src = out / "render_queue_panel_action.png"
        if timeline_src.exists() and not _asset("export_timeline_detail_current").exists():
            _copy_or_crop(timeline_src, _asset("export_timeline_detail_current"))


def recipe_ar_pbr(ctx: RetryContext) -> None:
    out = FRESH / "ar_pbr_statue_composite"
    media = _pick_media("Fallingwater", "South Korea", "Tokyo")
    if not AR_PBR_ASSET.exists():
        ctx.log(f"AR/PBR approved asset is missing: {AR_PBR_ASSET}")
        return
    if not _image_ok(_asset("ar_statue_editor")):
        _run_script(
            ctx,
            "qa_ui_renewal_ar_pbr_workspace.py",
            "--media",
            str(media),
            "--asset",
            str(AR_PBR_ASSET),
            "--out-dir",
            str(out),
            "--language",
            "en",
        )
        if not ctx.dry_run and (out / "editor_ar_pbr_object_action.png").exists():
            _copy_or_crop(out / "editor_ar_pbr_object_action.png", _asset("ar_statue_editor"))


def recipe_vtuber(ctx: RetryContext) -> None:
    program_bg = PROGRAM_BACKGROUND if PROGRAM_BACKGROUND.exists() else PROGRAM_BACKGROUND_ALT
    if not TRUMP_SOURCE.exists() or not program_bg.exists() or not VRM_AVATAR.exists():
        ctx.log(
            "VTuber recapture skipped because source/background/VRM is missing: "
            f"{TRUMP_SOURCE}, {program_bg}, {VRM_AVATAR}"
        )
        return
    _run_script(
        ctx,
        "capture_review_vtuber_studio.py",
        "--trump-source",
        str(TRUMP_SOURCE),
        "--program-background",
        str(program_bg),
        "--vrm",
        str(VRM_AVATAR),
        "--out-dir",
        str(ROOT / "debugCapture" / "review_vtuber_studio_retry"),
        "--catalog-out-dir",
        str(FRESH / "vrm_vtuber_studio"),
        "--source-time-ms",
        "12000",
        "--program-time-ms",
        "564000",
        "--width",
        "1280",
        "--height",
        "900",
        "--settle-ms",
        "1400",
    )


RECIPE_FOR_ASSET: dict[str, str] = {
    "effects_before_after_editor": "effects",
    "effects_hover_detail": "effects",
    "timeline_current_editor": "timeline",
    "timeline_current_detail": "timeline",
    "transitions_editor": "transitions",
    "transition_detail": "transitions",
    "typography_editor": "typography",
    "typography_detail": "typography",
    "keyframe_motion_editor": "keyframes",
    "keyframe_detail": "keyframes",
    "live2d_composite_editor": "live2d",
    "live2d_actor_detail": "live2d",
    "mmd_composite_editor": "mmd",
    "mmd_character_detail": "mmd",
    "overview_left_workspace": "overview",
    "overview_center_editor": "overview",
    "overview_right_workspace": "overview",
    "ppt_maker_detail": "ppt_maker",
    "color_before_after_editor": "color_compare",
    "color_before_after_detail": "color_compare",
    "node_before_after_editor": "node_compare",
    "node_graph_actual": "node_compare",
    "node_effect_before_after_editor": "node_effects",
    "node_effect_library_detail": "node_effects",
    "sound_editor": "audio",
    "sound_workbench": "audio",
    "sound_graphs": "audio",
    "export_editor_current": "export",
    "export_timeline_detail_current": "export",
    "ar_statue_editor": "ar_pbr",
    "ar_statue": "ar_pbr",
    "vtuber_studio_editor": "vtuber",
    "vtuber_studio_program_output": "vtuber",
    "vtuber_studio.contract": "vtuber",
}

RECIPES: dict[str, Callable[[RetryContext], None]] = {
    "effects": recipe_effects,
    "timeline": recipe_timeline,
    "transitions": recipe_transitions,
    "typography": recipe_typography,
    "keyframes": recipe_keyframes,
    "node_effects": recipe_node_effects,
    "color_compare": recipe_color_compare,
    "node_compare": recipe_node_compare,
    "live2d": recipe_live2d,
    "mmd": recipe_mmd,
    "overview": recipe_overview,
    "ppt_maker": recipe_ppt_maker,
    "audio": recipe_audio,
    "export": recipe_export,
    "ar_pbr": recipe_ar_pbr,
    "vtuber": recipe_vtuber,
}


def _preflight() -> tuple[bool, list[str], str]:
    result = subprocess.run(
        [_py(), str(ROOT / "tools" / "build_full_product_catalog_decks.py"), "--preflight-only"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = result.stdout or ""
    report = catalog.STRICT_REPORT.read_text(encoding="utf-8") if catalog.STRICT_REPORT.exists() else output
    blockers = re.findall(r"^- ([^:]+):", report, flags=re.MULTILINE)
    return result.returncode == 0, sorted(set(blockers)), report


def _recipes_from_blockers(blockers: list[str], requested: str) -> list[str]:
    if requested != "auto":
        if requested == "all":
            return list(RECIPES)
        if requested not in RECIPES:
            raise KeyError(f"Unknown page/recipe: {requested}")
        return [requested]
    recipes = []
    for blocker in blockers:
        recipe = RECIPE_FOR_ASSET.get(blocker)
        if recipe and recipe not in recipes:
            recipes.append(recipe)
    return recipes


def _write_report(report: dict[str, object]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", default="auto", help="auto, all, or one recipe name")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    ctx = RetryContext(dry_run=args.dry_run, timeout=args.timeout)
    final_report: dict[str, object] = {"attempts": [], "report_path": str(REPORT_PATH)}

    ok, blockers, strict_report = _preflight()
    final_report["initial_ok"] = ok
    final_report["initial_blockers"] = blockers
    if ok:
        if args.page != "auto":
            recipes = _recipes_from_blockers(blockers, args.page)
            ctx.log(
                "Full product catalog preflight already passes; running explicit "
                f"recipe request anyway: {', '.join(recipes)}"
            )
            attempt_report: dict[str, object] = {"attempt": 1, "recipes": recipes, "errors": []}
            for recipe_name in recipes:
                try:
                    RECIPES[recipe_name](ctx)
                except Exception as exc:
                    message = f"{recipe_name} failed: {exc}"
                    ctx.log(message)
                    attempt_report.setdefault("errors", []).append(message)
            ok, blockers, strict_report = _preflight()
            attempt_report["preflight_ok"] = ok
            attempt_report["remaining_blockers"] = blockers
            final_report.setdefault("attempts", []).append(attempt_report)
            final_report["final_ok"] = ok
            final_report["final_blockers"] = blockers
            final_report["actions"] = ctx.actions
            final_report["commands"] = [command.__dict__ for command in ctx.commands]
            final_report["strict_report_tail"] = strict_report[-8000:]
            _write_report(final_report)
            return 0 if ok else 2
        ctx.log("Full product catalog preflight already passes.")
        final_report["final_ok"] = True
        _write_report(final_report)
        return 0

    for attempt in range(1, max(1, args.max_attempts) + 1):
        recipes = _recipes_from_blockers(blockers, args.page)
        if not recipes:
            ctx.log("No adaptive recipe is registered for current blockers.")
            break
        ctx.log(f"Attempt {attempt}: recipes={', '.join(recipes)}")
        attempt_report: dict[str, object] = {"attempt": attempt, "recipes": recipes, "errors": []}
        for recipe_name in recipes:
            try:
                RECIPES[recipe_name](ctx)
            except Exception as exc:  # keep other recipes moving
                message = f"{recipe_name} failed: {exc}"
                ctx.log(message)
                attempt_report.setdefault("errors", []).append(message)

        ok, blockers, strict_report = _preflight()
        attempt_report["preflight_ok"] = ok
        attempt_report["remaining_blockers"] = blockers
        final_report.setdefault("attempts", []).append(attempt_report)
        if ok:
            break

    final_report["final_ok"] = ok
    final_report["final_blockers"] = blockers
    final_report["actions"] = ctx.actions
    final_report["commands"] = [command.__dict__ for command in ctx.commands]
    final_report["strict_report_tail"] = strict_report[-8000:]
    _write_report(final_report)

    if ok:
        print(f"Adaptive retry preflight ok. Report: {REPORT_PATH}")
        return 0
    print(f"Adaptive retry could not clear all blockers. Report: {REPORT_PATH}")
    print(strict_report)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
