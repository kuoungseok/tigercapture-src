from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.actions import build_default_action_registry

from .artifacts import relpath
from .sample_resources import DEFAULT_REVIEW_SAMPLE_MANIFEST, review_sample_resource_report


ROOT = Path(__file__).resolve().parents[2]


class _ScenarioMediaPool:
    def __init__(self) -> None:
        self._paths: list[str] = []

    def add_path(self, path: Path) -> bool:
        text = str(path.resolve())
        if text in self._paths:
            return False
        self._paths.append(text)
        return True

    def items(self) -> list[str]:
        return list(self._paths)


class _ScenarioPlayer:
    def __init__(self) -> None:
        self._position_ms = 0

    def setPosition(self, value: int) -> None:
        self._position_ms = max(0, int(value or 0))

    def position(self) -> int:
        return self._position_ms


class _ReviewScenarioOwner:
    """Minimal editor-shaped object for action-only review scenarios."""

    def __init__(self) -> None:
        self._tracks: list[Any] = []
        self._audio_tracks: list[Any] = []
        self._timeline_markers: list[dict[str, Any]] = []
        self._selected_clips: list[dict[str, Any]] = []
        self._project_settings: dict[str, Any] = {"screenstudio_mode": True}
        self._media_pool = _ScenarioMediaPool()
        self._player = _ScenarioPlayer()
        self._px_per_sec = 64.0
        self._registered_changes: list[str] = []
        self._active_track_id: int | None = None
        self._active_audio_track_id: int | None = None
        self._selected_audio_clip_id: int | None = None

    def _register_change(self, label: str) -> None:
        self._registered_changes.append(str(label or "Action change"))

    def _refresh_player_tracks(self) -> None:
        return None

    def _update_tracks_host_width(self) -> None:
        return None

    def _refresh_workbench(self) -> None:
        return None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _safe_scenario_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or "").strip().lower())
    return text.strip("_") or "summary"


def _resources_by_id(sample_report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("id")): row
        for row in list(sample_report.get("resources", []) or [])
        if isinstance(row, Mapping) and row.get("id")
    }


def _resolve_resource_path(row: Mapping[str, Any] | None, *, root: Path) -> Path | None:
    if not row:
        return None
    path = Path(str(row.get("path") or ""))
    resolved = path if path.is_absolute() else root / path
    return resolved if resolved.exists() else None


def _resource_duration_ms(row: Mapping[str, Any] | None, default: int) -> int:
    metadata = row.get("metadata") if isinstance(row, Mapping) else {}
    if isinstance(metadata, Mapping):
        value = _as_int(metadata.get("duration_ms"), 0)
        if value > 0:
            return value
    return int(default)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _extract_video_frame(video: Path, out_path: Path, *, at_seconds: float = 0.1) -> Path | None:
    if not video.exists():
        return None
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except Exception:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        get_ffmpeg_exe(),
        "-y",
        "-ss",
        f"{max(0.0, float(at_seconds)):.3f}",
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-vf",
        "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2",
        str(out_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return out_path if proc.returncode == 0 and out_path.exists() else None


def _draw_action_storyboard(
    path: Path,
    *,
    scenario: str,
    actions_executed: int,
    timeline: Mapping[str, Any],
    warnings: list[str],
    media_thumbnail: Path | None = None,
    media_label: str = "",
) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False

    width, height = 1400, 820
    image = Image.new("RGB", (width, height), (17, 20, 27))
    draw = ImageDraw.Draw(image)
    try:
        from app.review_automation.fonts import load_pil_font

        font_title = load_pil_font(40, bold=True)
        font_head = load_pil_font(24, bold=True)
        font_body = load_pil_font(20)
        font_small = load_pil_font(16)
    except Exception:
        try:
            font_title = ImageFont.truetype("arial.ttf", 40)
            font_head = ImageFont.truetype("arial.ttf", 24)
            font_body = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font_title = font_head = font_body = font_small = ImageFont.load_default()

    draw.rectangle((0, 0, width, 132), fill=(241, 245, 249))
    draw.text((48, 36), "Action-driven review scenario", fill=(14, 20, 30), font=font_title)
    draw.text(
        (50, 88),
        f"scenario={scenario}  actions={actions_executed}  duration={_as_int(timeline.get('duration_ms')) / 1000:.1f}s",
        fill=(71, 85, 105),
        font=font_body,
    )

    lane_left, lane_right = 110, width - 72
    lane_width = lane_right - lane_left
    timeline_duration = max(1000, _as_int(timeline.get("duration_ms"), 1000))
    ruler_y = 188
    draw.line((lane_left, ruler_y, lane_right, ruler_y), fill=(148, 163, 184), width=2)
    for tick_ms in range(0, timeline_duration + 1, max(1000, timeline_duration // 6)):
        x = lane_left + int(lane_width * (tick_ms / timeline_duration))
        draw.line((x, ruler_y - 8, x, ruler_y + 8), fill=(203, 213, 225), width=2)
        draw.text((x - 18, ruler_y - 34), f"{tick_ms / 1000:.0f}s", fill=(226, 232, 240), font=font_small)

    colors = {
        "video": (56, 189, 248),
        "audio": (52, 211, 153),
    }
    thumb_image = None
    if media_thumbnail is not None and media_thumbnail.exists():
        try:
            thumb_image = Image.open(media_thumbnail).convert("RGB")
        except Exception:
            thumb_image = None

    y = 238
    for track in list(timeline.get("tracks") or []):
        if not isinstance(track, Mapping):
            continue
        kind = str(track.get("kind") or "video")
        label = f"{kind.upper()} {track.get('id')} - {track.get('clip_count', 0)} clips"
        draw.text((38, y + 28), label, fill=(226, 232, 240), font=font_small)
        draw.rounded_rectangle((lane_left, y, lane_right, y + 78), radius=8, fill=(30, 41, 59), outline=(51, 65, 85))
        start = max(0, _as_int(track.get("start_ms"), 0))
        end = max(start + 1, _as_int(track.get("end_ms"), start + 1))
        x0 = lane_left + int(lane_width * (start / timeline_duration))
        x1 = lane_left + max(24, int(lane_width * (end / timeline_duration)))
        clip_box = (x0 + 8, y + 14, min(x1 - 4, lane_right - 8), y + 64)
        draw.rounded_rectangle(clip_box, radius=6, fill=colors.get(kind, (129, 140, 248)))
        if kind == "video" and thumb_image is not None:
            thumb = thumb_image.copy()
            thumb.thumbnail((max(1, clip_box[2] - clip_box[0]), max(1, clip_box[3] - clip_box[1])), Image.Resampling.LANCZOS)
            draw.rectangle(clip_box, fill=(6, 10, 18))
            tile_x = clip_box[0]
            while tile_x < clip_box[2]:
                crop_w = min(thumb.width, clip_box[2] - tile_x)
                if crop_w > 0 and thumb.height > 0:
                    image.paste(thumb.crop((0, 0, crop_w, thumb.height)), (tile_x, clip_box[1] + max(0, (clip_box[3] - clip_box[1] - thumb.height) // 2)))
                tile_x += max(1, thumb.width + 8)
            draw.rectangle(clip_box, outline=(56, 189, 248), width=2)
            draw.rectangle((clip_box[0], clip_box[1], min(clip_box[0] + 310, clip_box[2]), clip_box[1] + 50), fill=(6, 10, 18))
            draw.text((clip_box[0] + 14, clip_box[1] + 13), "YouTube sample - cut/filter/text", fill=(248, 250, 252), font=font_body)
        else:
            draw.text((x0 + 22, y + 28), "import - edit - finish", fill=(8, 47, 73), font=font_body)
        y += 112

    for marker in list(timeline.get("markers") or []):
        if not isinstance(marker, Mapping):
            continue
        ms = max(0, _as_int(marker.get("ms"), 0))
        x = lane_left + int(lane_width * (ms / timeline_duration))
        draw.polygon([(x, 180), (x - 9, 164), (x + 9, 164)], fill=(250, 204, 21))
        draw.line((x, 188, x, min(y - 28, 610)), fill=(250, 204, 21), width=2)
        label = str(marker.get("label") or "marker")
        draw.text((x + 10, 158), label[:26], fill=(254, 249, 195), font=font_small)

    panel_y = max(y + 16, 560)
    draw.rounded_rectangle((48, panel_y, width - 48, height - 48), radius=10, fill=(241, 245, 249))
    draw.text((78, panel_y + 28), "Automated operations represented", fill=(15, 23, 42), font=font_head)
    chips = [
        "media import",
        "timeline zoom",
        "split",
        "filter",
        "color grade",
        "node graph",
        "typography keyframes",
        "audio mix",
        "selection",
    ]
    x, chip_y = 78, panel_y + 76
    for chip in chips:
        chip_w = 34 + len(chip) * 11
        if x + chip_w > width - 90:
            x = 78
            chip_y += 46
        draw.rounded_rectangle((x, chip_y, x + chip_w, chip_y + 34), radius=17, fill=(30, 41, 59))
        draw.text((x + 16, chip_y + 8), chip, fill=(248, 250, 252), font=font_small)
        x += chip_w + 12
    if media_label:
        draw.text((78, height - 116), f"media: {media_label[:120]}", fill=(71, 85, 105), font=font_small)
    if warnings:
        draw.text((78, height - 88), f"warnings: {len(warnings)}", fill=(180, 83, 9), font=font_small)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path.exists()


def run_action_review_scenario(
    *,
    project_root: str | Path = ROOT,
    out_dir: str | Path,
    sample_manifest: str | Path = DEFAULT_REVIEW_SAMPLE_MANIFEST,
    scenario: str = "summary",
    force: bool = False,
) -> dict[str, Any]:
    root = Path(project_root)
    out = Path(out_dir)
    scenario_dir = out / "action_scenarios"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    scenario_id = _safe_scenario_id(scenario)
    sample_report = review_sample_resource_report(sample_manifest, root=root, create_default_if_missing=False)
    resources = _resources_by_id(sample_report)
    owner = _ReviewScenarioOwner()
    registry = build_default_action_registry(owner)
    steps: list[dict[str, Any]] = []
    warnings: list[str] = []

    def run(action: str, params: Mapping[str, Any] | None = None, *, confirm_destructive: bool = False) -> dict[str, Any]:
        result = registry.execute(action, params or {}, confirm_destructive=confirm_destructive).to_dict()
        error_text = str(result.get("error") or "")
        steps.append(
            {
                "index": len(steps),
                "action": action,
                "params": _json_safe(dict(params or {})),
                "ok": bool(result.get("ok")),
                "result": _json_safe(result.get("result")),
                "error": error_text,
                "warnings": list(result.get("warnings") or []),
            }
        )
        if not result.get("ok"):
            warnings.append(f"{action}: {error_text or 'failed'}")
        return result

    overview_row = resources.get("overview_screen_demo") or resources.get("screenstudio_cursor_demo")
    overview_path = _resolve_resource_path(overview_row, root=root)
    audio_row = resources.get("dialogue_cleanup_demo")
    audio_path = _resolve_resource_path(audio_row, root=root)

    thumbnail_path: Path | None = None
    media_label = ""
    if overview_path is None:
        warnings.append("overview video sample is missing; action scenario could not import video")
    else:
        media_label = overview_path.name
        thumbnail_path = _extract_video_frame(overview_path, scenario_dir / "action_scenario_youtube_frame.png")
        video_duration = _resource_duration_ms(overview_row, 6000)
        imported = run(
            "media.import_to_timeline",
            {
                "path": str(overview_path),
                "kind": "video",
                "at_ms": 0,
                "duration_ms": video_duration,
                "name": "Review overview",
            },
        )
        video_result = imported.get("result") if isinstance(imported.get("result"), Mapping) else {}
        track_id = _as_int(video_result.get("track_id"), 1)
        clip_id = _as_int(video_result.get("clip_id"), 1)
        split_at = max(1000, min(video_duration - 1000, video_duration // 2))
        run("timeline.set_zoom", {"px_per_sec": 260})
        run("timeline.marker.add", {"ms": split_at, "label": "AI planned cut", "color": "#FACC15"})
        split = run("timeline.split", {"track_id": track_id, "at_ms": split_at})
        right_clip_id = _as_int(((split.get("result") or {}) if isinstance(split.get("result"), Mapping) else {}).get("right_clip_id"), 0)
        run("clip.set_filter", {"track_id": track_id, "clip_id": clip_id, "params": {"enabled": True, "sharpen": 0.28, "vignette": 0.18}})
        run(
            "clip.set_color_grade",
            {
                "track_id": track_id,
                "clip_id": clip_id,
                "grade": {"exposure": 0.08, "contrast": 1.08, "saturation": 1.12, "temperature": 0.04},
            },
        )
        run(
            "node.add",
            {
                "track_id": track_id,
                "kind": "blur",
                "label": "Review focus blur",
                "x": -70,
                "y": -40,
                "params": {"radius": 6, "mix": 0.35},
            },
        )
        text = run(
            "text.add",
            {
                "track_id": track_id,
                "clip_id": clip_id,
                "text": "Tiger Studio",
                "start_ms": 200,
                "end_ms": min(2600, video_duration),
                "style": {"font_size": 54, "color": "#F8FAFC"},
                "animation": {"preset": "slide_up"},
            },
        )
        text_id = _as_int(((text.get("result") or {}) if isinstance(text.get("result"), Mapping) else {}).get("text_id"), 0)
        if text_id > 0:
            run(
                "text.set_keyframes",
                {
                    "track_id": track_id,
                    "clip_id": clip_id,
                    "text_id": text_id,
                    "keyframes": {
                        "opacity": [{"time_ms": 200, "value": 0.0}, {"time_ms": 700, "value": 1.0}, {"time_ms": 2300, "value": 1.0}, {"time_ms": 2600, "value": 0.0}],
                        "scale": [{"time_ms": 200, "value": 0.94}, {"time_ms": 700, "value": 1.0}],
                    },
                },
            )
        if right_clip_id > 0:
            run("clip.set_speed", {"track_id": track_id, "clip_id": right_clip_id, "speed": 1.35})
            run("clip.set_fade", {"track_id": track_id, "clip_id": right_clip_id, "fade_in_ms": 180, "fade_out_ms": 260})
        run("selection.set", {"kind": "video", "track_id": track_id, "clip_id": clip_id})

    if audio_path is None:
        warnings.append("dialogue audio sample is missing; action scenario skipped audio mix")
    else:
        audio_duration = _resource_duration_ms(audio_row, 7000)
        imported_audio = run(
            "media.import_to_timeline",
            {
                "path": str(audio_path),
                "kind": "audio",
                "at_ms": 0,
                "duration_ms": audio_duration,
                "name": "Dialogue cleanup",
            },
        )
        audio_result = imported_audio.get("result") if isinstance(imported_audio.get("result"), Mapping) else {}
        audio_track_id = _as_int(audio_result.get("track_id"), 1)
        audio_clip_id = _as_int(audio_result.get("clip_id"), 1)
        run("audio.track.set_mix", {"track_id": audio_track_id, "volume": 0.82, "pan": -0.05})
        run("audio.clip.set_gain", {"track_id": audio_track_id, "clip_id": audio_clip_id, "gain": 1.18})
        run("selection.set", {"kind": "audio", "track_id": audio_track_id, "clip_id": audio_clip_id})

    timeline_result = registry.execute("timeline.summary").to_dict()
    timeline = timeline_result.get("result") if isinstance(timeline_result.get("result"), Mapping) else {}
    evidence = {
        "kind": "review_action_scenario",
        "scenario": scenario_id,
        "ok": bool(not [step for step in steps if not step.get("ok")] and sample_report.get("ok")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_report": sample_report,
        "actions_executed": sum(1 for step in steps if step.get("ok")),
        "steps": steps,
        "timeline": _json_safe(timeline),
        "registered_changes": list(owner._registered_changes),
        "warnings": warnings,
        "force": bool(force),
    }
    evidence_path = scenario_dir / "action_scenario_report.json"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    scenario_specific_path = scenario_dir / f"{scenario_id}_action_scenario_report.json"
    if scenario_specific_path != evidence_path:
        scenario_specific_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    storyboard_path = scenario_dir / "action_scenario_timeline.png"
    storyboard_ok = bool(
        force
        or not storyboard_path.exists()
        or storyboard_path.stat().st_size == 0
    )
    if storyboard_ok:
        storyboard_ok = _draw_action_storyboard(
            storyboard_path,
            scenario=scenario_id,
            actions_executed=int(evidence["actions_executed"]),
            timeline=timeline,
            warnings=warnings,
            media_thumbnail=thumbnail_path,
            media_label=media_label,
        )
    else:
        storyboard_ok = storyboard_path.exists()
    evidence["storyboard_path"] = relpath(storyboard_path, root=root)
    evidence["storyboard_exists"] = bool(storyboard_ok and storyboard_path.exists())
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    if scenario_specific_path != evidence_path:
        scenario_specific_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": bool(evidence["ok"]),
        "scenario": scenario_id,
        "evidence_path": relpath(evidence_path, root=root),
        "storyboard_path": relpath(storyboard_path, root=root),
        "storyboard_exists": bool(evidence["storyboard_exists"]),
        "actions_executed": int(evidence["actions_executed"]),
        "timeline": _json_safe(timeline),
        "warnings": warnings,
    }
