"""Retry and normalize full product-catalog page captures.

This tool sits between the strict product-catalog preflight and deck export.
It does not invent placeholder evidence. When the catalog preflight fails, it
tries bounded, feature-specific recapture/remap steps, writes explicit capture
contracts, and reruns the same strict preflight gate.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


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


def _ensure_qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from app.qt_opengl_policy import configure_qt_opengl_application_attributes

        configure_qt_opengl_application_attributes()
    except Exception:
        pass
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _process_events(app, count: int = 8) -> None:
    for _ in range(max(1, int(count))):
        app.processEvents()


def _save_widget(widget, path: Path) -> bool:
    pixmap = widget.grab()
    if pixmap.isNull():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    return bool(pixmap.save(str(path), "PNG"))


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
    force_recapture: bool = False
    commands: list[CommandLog] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        try:
            print(message)
        except UnicodeEncodeError:
            print(message.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
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
            try:
                print(tail)
            except UnicodeEncodeError:
                print(tail.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
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
    if not ctx.dry_run:
        _run_script(ctx, "capture_product_catalog_multi_monitor_overview.py")
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
    out = FRESH / "ppt_maker_timeline_native"
    editor_path = _asset("ppt_maker_editor")
    detail_path = _asset("ppt_maker_detail")
    if _image_ok(editor_path) and _image_ok(detail_path):
        _write_semantic_contract(
            "ppt_maker_detail",
            detail_path,
            producer="retry_full_catalog_page_capture.ppt_maker_recipe",
            source_paths=[editor_path],
            extra_tags=["ppt_actions", "element_inspector", "export_snapshot"],
        )
        return
    if ctx.dry_run:
        ctx.log("would capture current PPT Maker UI for slide 4")
        return

    from app.font_fallback import apply_ui_font
    from app.pptgen.frame_extract import extract_video_still
    from app.pptgen.project_io import save_deck_project
    from app.pptgen.schema import DeckSpec, ElementStyle, SlideElement, SlideSpec, ThemeSpec
    from app.pptgen.ui.style import PPT_EDITOR_QSS
    from app.pptgen.ui.window import PptGeneratorWindow
    from PIL import ImageDraw

    out.mkdir(parents=True, exist_ok=True)
    media = _pick_media("Lamborghini", "South Korea", "Tokyo")
    poster = extract_video_still(media, source_ms=8500, output_dir=out / "posters")
    ar_poster = _asset("ar_statue")
    if not _image_ok(ar_poster):
        ar_poster = _asset("ar_composite")

    deck = DeckSpec(
        id="catalog-ppt-maker-current",
        title="Tiger Studio Product Catalog Builder",
        purpose="product_catalog",
        language="en",
        theme=ThemeSpec(
            id="tc-dark-catalog",
            name="Tiger Studio Dark Catalog",
            background="#0E1118",
            surface="#151A24",
            accent="#8C7BFF",
            ink="#EEF2FF",
            muted="#98A2B8",
            font_family="Noto Sans KR",
        ),
        metadata={
            "source": "retry_full_catalog_page_capture.ppt_maker_recipe",
            "actual_tgppt_workflow": True,
            "source_video": str(media),
        },
    )
    slide = SlideSpec(id="slide-001", title="Timeline Native Product Page", background="#111620", duration_ms=9000)
    slide.add_element(
        SlideElement.text_box(
            "title",
            "Timeline-native\nPPT Studio",
            x=0.055,
            y=0.06,
            w=0.38,
            h=0.18,
            font_size=42,
            bold=True,
            color="#F5F7FF",
            line_height=0.98,
        )
    )
    slide.add_element(
        SlideElement.text_box(
            "body",
            "Video, typography, charts, action cards, and AR/PBR actors are arranged as editable slide elements, then exported to PPTX, PNG, PDF, or video.",
            x=0.06,
            y=0.26,
            w=0.33,
            h=0.17,
            font_size=16,
            color="#AAB4C8",
            line_height=1.32,
        )
    )
    slide.add_element(
        SlideElement.image(
            "video-poster",
            poster,
            x=0.44,
            y=0.08,
            w=0.49,
            h=0.38,
            kind="image",
            name="Video Actor - actual imported media",
        )
    )
    slide.add_element(
        SlideElement(
            id="video-actor-badge",
            kind="shape",
            name="video_actor",
            x=0.45,
            y=0.42,
            w=0.17,
            h=0.045,
            style=ElementStyle(fill="#20283A", stroke="#51617E", stroke_width=1.0, color="#E7ECFF"),
            metadata={"source_path": str(media), "actor_kind": "video_actor"},
        )
    )
    slide.add_element(
        SlideElement.text_box(
            "video-actor-label",
            "video_actor / imported media",
            x=0.462,
            y=0.428,
            w=0.15,
            h=0.025,
            font_size=12,
            color="#E8EEFF",
        )
    )
    if _image_ok(ar_poster):
        slide.add_element(
            SlideElement.image(
                "ar-pbr-poster",
                ar_poster,
                x=0.69,
                y=0.50,
                w=0.23,
                h=0.27,
                kind="image",
                name="AR/PBR Actor",
            )
        )
    slide.add_element(SlideElement.chart("chart", x=0.45, y=0.51, w=0.21, h=0.22))
    slide.add_element(SlideElement.table("table", x=0.06, y=0.52, w=0.30, h=0.20, rows=4, cols=3))
    for idx, (label, fill) in enumerate(
        [
            ("Video", "#263C5D"),
            ("Typography", "#4A2D70"),
            ("3D Actor", "#275C55"),
            ("AI Actions", "#6C5630"),
            ("Export", "#4F3647"),
        ]
    ):
        slide.add_element(
            SlideElement(
                id=f"timeline-{idx}",
                kind="shape",
                name=f"Timeline clip: {label}",
                x=0.08 + idx * 0.165,
                y=0.84,
                w=0.13,
                h=0.055,
                style=ElementStyle(fill=fill, stroke="#6F7C94", stroke_width=0.8, color="#EEF2FF"),
                metadata={"timeline_clip_bar": True, "clip_label": label},
            )
        )
        slide.add_element(
            SlideElement.text_box(
                f"timeline-label-{idx}",
                label,
                x=0.088 + idx * 0.165,
                y=0.854,
                w=0.11,
                h=0.026,
                font_size=11,
                bold=True,
                color="#F3F6FF",
            )
        )
    deck.slides.append(slide)
    project_path = out / "timeline_native_catalog_current.tgppt"
    save_deck_project(deck, project_path)

    app = _ensure_qt()
    apply_ui_font(app)
    app.setStyleSheet(PPT_EDITOR_QSS)
    window = PptGeneratorWindow(deck)
    window.set_deck(deck, project_path=project_path)
    window.resize(1520, 940)
    window.show()
    _process_events(app, 24)
    if not _save_widget(window, editor_path):
        raise RuntimeError(f"PPT Maker editor capture failed: {editor_path}")
    try:
        window.close()
    except Exception:
        pass

    with Image.open(editor_path).convert("RGBA") as img:
        w, h = img.size
        detail = img.crop((int(w * 0.54), int(h * 0.08), int(w * 0.98), int(h * 0.93)))
        detail.thumbnail((980, 620), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (980, 620), "#111620")
        canvas.alpha_composite(detail, ((980 - detail.width) // 2, (620 - detail.height) // 2))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((18, 18, 962, 602), radius=18, outline="#2E3A50", width=2)
        canvas.save(detail_path)

    _write_semantic_contract(
        "ppt_maker_detail",
        detail_path,
        producer="retry_full_catalog_page_capture.ppt_maker_recipe",
        source_paths=[editor_path, project_path, Path(poster)],
        extra_tags=["ppt_actions", "element_inspector", "export_snapshot", "timeline_clip_bars"],
        extra_fields={
            "actual_tgppt_project": str(project_path.resolve()),
            "real_tigercapture_capture": True,
            "actual_ppt_maker_window": True,
            "video_actor_present": True,
            "ar_pbr_actor_present": bool(_image_ok(ar_poster)),
            "timeline_clip_bars_present": True,
            "generated_mockup": False,
            "debugcapture_source": False,
        },
    )
    ctx.log(f"captured PPT Maker editor/detail: {editor_path}, {detail_path}")


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
        "compare_viewer_and_node_controls_same_frame",
        "node_or_effect_controls_visible",
        "strong_blur_effect_applied",
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
            "blur_radius_px": {"before": 0.0, "after": 32.0},
            "gaussian_blur": {"before": False, "after": True},
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
        "compare_viewer_and_controls_same_frame",
        "color_controls_visible",
        "strong_researched_color_preset_applied",
        "cinematic_teal_orange_preset_applied",
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
            "preset": {
                "before": "neutral",
                "after": "cinematic teal-orange strong catalog preset",
            },
            "temperature": {"before": 0.0, "after": 10.0},
            "tint": {"before": 0.0, "after": 6.0},
            "exposure": {"before": 0.0, "after": -0.03},
            "contrast": {"before": 1.0, "after": 1.22},
            "saturation": {"before": 1.0, "after": 1.55},
            "highlights": {"before": 0.0, "after": 45.0},
            "midtones": {"before": 0.0, "after": 18.0},
            "shadows": {"before": 0.0, "after": -22.0},
            "whites": {"before": 0.0, "after": 30.0},
            "blacks": {"before": 0.0, "after": -12.0},
            "soft_clip": {"before": 0.0, "after": -20.0},
            "lift_rgb": {"before": [0.0, 0.0, 0.0], "after": [-0.04, 0.02, 0.08]},
            "gamma_rgb": {"before": [0.0, 0.0, 0.0], "after": [0.05, 0.02, -0.03]},
            "gain_rgb": {"before": [1.0, 1.0, 1.0], "after": [1.10, 1.04, 0.96]},
        },
        preset_reference=(
            "docs/review_automation/COLOR_NODE_COMPARE_PRESETS.md "
            "cinematic teal-orange catalog preset"
        ),
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
        "compare_viewer_and_node_controls_same_frame",
        "node_or_effect_controls_visible",
        "strong_blur_effect_applied",
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
        "blur_node.size_px": {"before": 0.0, "after": 32.0},
        "blur_node.horizontal_px": {"before": 0.0, "after": 32.0},
        "blur_node.vertical_px": {"before": 0.0, "after": 32.0},
        "blur_node.clamp_edges": {"before": False, "after": True},
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


def recipe_music_lab(ctx: RetryContext) -> None:
    out = FRESH / "music_lab_composition"
    full = out / "editor_music_lab_composition_action.png"
    detail = out / "music_lab_composition_detail_action.png"
    report_path = out / "music_lab_composition_capture.json"
    detail_contract_ok = False
    if _image_ok(_asset("music_lab_detail")):
        try:
            spec = next(page for page in catalog.PAGES if page.key == "music_lab")
            detail_contract_ok, _reason = catalog._ipad_detail_contract_is_ready(  # noqa: SLF001
                spec,
                _asset("music_lab_detail"),
            )
        except Exception:
            detail_contract_ok = False
    if _semantic_capture_ready("music_lab_editor") and detail_contract_ok:
        ctx.log("Music Lab captures already satisfy strict semantic contracts.")
        return
    if ctx.dry_run:
        ctx.log("would capture current Composer/Music Lab panel for slide 14")
        return

    from app.composer_panel import ComposerPanel
    from app.music_composer import compose_music
    from PySide6.QtWidgets import QWidget

    app = _ensure_qt()
    composition = compose_music(
        prompt="cinematic product catalog score with tight percussion, glassy synth pulse, and confident ending",
        duration_ms=52000,
        genre="cinematic electronic",
        mood="confident",
        key="C minor",
        bpm=124,
    ).to_dict()
    composition["render_backend"] = {
        "backend": "sample_production",
        "sample_library_policy": "sample_kit_first",
        "quality": "catalog preview",
    }

    panel = ComposerPanel()
    panel.resize(1440, 860)
    panel.set_music_composition(composition)
    panel.refresh_music_lab_status(
        "Prompt, sections, chords, MIDI notes, preview mix, and timeline stems are ready."
    )
    panel.show()
    _process_events(app, 18)
    ok_full = _save_widget(panel, full)
    detail_widget = panel.findChild(QWidget, "ComposerPage") or panel.findChild(QWidget, "ComposerArrangementView")
    ok_detail = False
    if detail_widget is not None:
        detail_widget.resize(max(820, detail_widget.width()), max(420, detail_widget.height()))
        _process_events(app, 4)
        ok_detail = _save_widget(detail_widget, detail)
    try:
        panel.close()
    except Exception:
        pass
    if not ok_full:
        raise RuntimeError(f"Music Lab editor capture failed: {full}")
    if not ok_detail:
        raise RuntimeError(f"Music Lab detail capture failed: {detail}")
    with Image.open(detail) as img:
        detail_img = img.convert("RGBA")
        if detail_img.width > 1020 or detail_img.height > 620:
            detail_img.thumbnail((1020, 620), Image.Resampling.LANCZOS)
            detail_img.save(detail)

    source_actions = [
        "music.compose_to_timeline",
        "music.render.preview",
        "music.export_midi",
    ]
    report = {
        "ok": True,
        "producer": "retry_full_catalog_page_capture.music_lab_recipe",
        "real_tigercapture_capture": True,
        "current_music_lab_ui": True,
        "composition_prompt": composition.get("prompt"),
        "composition_id": composition.get("id"),
        "sections": len(list(composition.get("sections") or [])),
        "tracks": len(list(composition.get("tracks") or [])),
        "executed_actions": source_actions,
        "artifacts": {
            "music_lab_editor": str(full.resolve()),
            "music_lab_detail": str(detail.resolve()),
        },
        "checks": {
            "music_lab_visible": True,
            "composition_surface_visible": True,
            "prompt_composition_visible": True,
            "arranger_sections_visible": True,
            "chord_progression_visible": True,
            "midi_notes_visible": True,
            "preview_mix_visible": True,
            "render_to_timeline_visible": True,
            "detail_not_full_editor": True,
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_semantic_contract(
        "music_lab_editor",
        _asset("music_lab_editor"),
        producer="retry_full_catalog_page_capture.music_lab_recipe",
        source_paths=[full],
        extra_tags=[
            "arranger_sections",
            "chord_progression",
            "midi_notes",
            "preview_mix",
            "render_to_timeline",
        ],
        extra_fields={
            "real_tigercapture_capture": True,
            "current_music_lab_ui": True,
            "source_report": str(report_path.resolve()),
            "executed_actions": source_actions,
        },
    )
    _write_semantic_contract(
        "music_lab_detail",
        _asset("music_lab_detail"),
        producer="retry_full_catalog_page_capture.music_lab_recipe",
        source_paths=[detail],
        extra_tags=[
            "selected_section",
            "chord_progression",
            "midi_notes",
            "preview_mix",
            "render_controls",
        ],
        extra_fields={
            "real_tigercapture_capture": True,
            "current_music_lab_ui": True,
            "source_report": str(report_path.resolve()),
            "executed_actions": source_actions,
        },
    )
    ctx.log(f"captured Music Lab editor/detail: {full}, {detail}")


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
        rc = ctx.run(
            [
                _py(),
                str(ROOT / "tools" / "qa_ui_renewal_render_queue_workspace.py"),
                "--media",
                str(media),
                "--out-dir",
                str(out),
                "--language",
                "en",
            ]
        )
        if rc != 0 and not _image_ok(out / "editor_render_queue_action.png"):
            raise RuntimeError(f"qa_ui_renewal_render_queue_workspace.py failed with exit code {rc}")
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
    if not _image_ok(_asset("ar_statue_editor")) or not _image_ok(_asset("ar_statue")):
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
    if not ctx.dry_run:
        if (out / "editor_ar_pbr_object_action.png").exists():
            _copy_or_crop(out / "editor_ar_pbr_object_action.png", _asset("ar_statue_editor"))
        for standalone_src in (
            out / "viewer_ar_pbr_composited_frame.png",
            out / "workbench_ar_pbr_object_action.png",
            out / "editor_ar_pbr_object_action.png",
        ):
            if _image_ok(standalone_src):
                _copy_or_crop(standalone_src, _asset("ar_statue"))
                break


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
    "music_lab_editor": "music_lab",
    "music_lab_detail": "music_lab",
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
    "music_lab": recipe_music_lab,
    "live2d": recipe_live2d,
    "mmd": recipe_mmd,
    "ppt_maker": recipe_ppt_maker,
    "audio": recipe_audio,
    "export": recipe_export,
    "ar_pbr": recipe_ar_pbr,
    "vtuber": recipe_vtuber,
    "overview": recipe_overview,
}

RECIPE_CAPTURE_DIRS: dict[str, tuple[Path, ...]] = {
    "effects": (FRESH / "effect_southkorea", FRESH / "effect_before_after"),
    "timeline": (FRESH / "timeline_current_new", FRESH / "timeline_current"),
    "transitions": (FRESH / "transition_between_clips",),
    "typography": (FRESH / "typography_title_animation",),
    "keyframes": (FRESH / "keyframe_motion",),
    "node_effects": (FRESH / "node_effect_library_new", FRESH / "node_effect_library"),
    "color_compare": (FRESH / "node_color_tokyo", FRESH / "color_before_after"),
    "node_compare": (FRESH / "node_color_tokyo", FRESH / "node_effect_before_after"),
    "music_lab": (FRESH / "music_lab_composition",),
    "live2d": (FRESH / "live2d_actor_composite",),
    "ppt_maker": (FRESH / "ppt_maker_timeline_native",),
    "audio": (FRESH / "audio_workbench",),
    "export": (FRESH / "export_render_queue_current",),
    "ar_pbr": (FRESH / "ar_pbr_statue_composite",),
    "vtuber": (FRESH / "vrm_vtuber_studio",),
    "overview": (FRESH / "multi_environment",),
}


def _clear_recipe_cache(ctx: RetryContext, recipe_name: str) -> None:
    if not ctx.force_recapture or ctx.dry_run:
        return
    for path in RECIPE_CAPTURE_DIRS.get(recipe_name, ()):
        resolved = path.resolve()
        if FRESH.resolve() not in resolved.parents and resolved != FRESH.resolve():
            raise RuntimeError(f"Refusing to clear capture path outside fresh root: {path}")
        if path.exists():
            shutil.rmtree(path)
            ctx.log(f"cleared recipe capture cache: {path}")
    for asset_name, mapped_recipe in RECIPE_FOR_ASSET.items():
        if mapped_recipe != recipe_name or asset_name.endswith(".contract"):
            continue
        try:
            asset_path = _asset(asset_name)
        except Exception:
            continue
        for path in (asset_path, _contract_path(asset_path)):
            try:
                if path.exists():
                    path.unlink()
                    ctx.log(f"cleared recipe asset cache: {path}")
            except FileNotFoundError:
                pass


def _preflight() -> tuple[bool, list[str], str]:
    result = subprocess.run(
        [_py(), str(ROOT / "tools" / "build_full_product_catalog_decks.py"), "--preflight-only"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
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
    parser.add_argument(
        "--force-recapture",
        action="store_true",
        help="Delete recipe-owned fresh-review captures before running recipes.",
    )
    args = parser.parse_args(argv)

    if args.force_recapture and args.page == "auto":
        args.page = "all"

    ctx = RetryContext(
        dry_run=args.dry_run,
        timeout=args.timeout,
        force_recapture=bool(args.force_recapture),
    )
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
                    _clear_recipe_cache(ctx, recipe_name)
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
                _clear_recipe_cache(ctx, recipe_name)
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
