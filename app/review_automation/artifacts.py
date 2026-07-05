from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .fonts import load_pil_font


ROOT = Path(__file__).resolve().parents[2]


def relpath(path: str | Path, *, root: str | Path = ROOT) -> str:
    raw = Path(path)
    try:
        return raw.resolve().relative_to(Path(root).resolve()).as_posix()
    except Exception:
        return raw.as_posix()


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: str | Path, *, root: str | Path = ROOT) -> dict[str, Any]:
    target = Path(path)
    exists = target.exists()
    stat = target.stat() if exists else None
    return {
        "path": relpath(target, root=root),
        "exists": bool(exists),
        "size": int(stat.st_size) if stat else 0,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat() if stat else None,
        "sha256": sha256_file(target) if exists and target.is_file() else None,
    }


def build_input_snapshot(paths: Iterable[str | Path], *, root: str | Path = ROOT) -> dict[str, Any]:
    records = [file_record(Path(root) / path if not Path(path).is_absolute() else Path(path), root=root) for path in paths]
    digest_records = [
        {
            "path": row.get("path"),
            "exists": row.get("exists"),
            "size": row.get("size"),
            "sha256": row.get("sha256"),
        }
        for row in records
    ]
    digest_src = json.dumps(digest_records, sort_keys=True, ensure_ascii=False)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "digest": hashlib.sha256(digest_src.encode("utf-8")).hexdigest(),
        "records": records,
    }


def copy_asset(
    source: str | Path,
    out_dir: str | Path,
    *,
    asset_id: str,
    title: str,
    kind: str,
    project_root: str | Path = ROOT,
) -> dict[str, Any]:
    src = Path(source)
    dst_dir = Path(out_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    exists = src.exists() and src.is_file()
    ext = src.suffix.lower() or ".bin"
    dst = dst_dir / f"{asset_id}{ext}"
    if exists:
        shutil.copy2(src, dst)
    return {
        "id": asset_id,
        "title": title,
        "kind": kind,
        "source_path": relpath(src, root=project_root),
        "output_path": relpath(dst, root=project_root),
        "exists": bool(exists),
        "size": int(dst.stat().st_size) if dst.exists() else 0,
    }


def _make_contact_sheet(image_paths: list[Path], out_path: Path) -> bool:
    if not image_paths:
        return False
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False

    thumbs: list[tuple[Path, Any]] = []
    for path in image_paths:
        try:
            image = Image.open(path).convert("RGB")
        except Exception:
            continue
        image.thumbnail((520, 300))
        thumbs.append((path, image.copy()))
    if not thumbs:
        return False
    pad = 22
    label_h = 34
    cols = 2
    cell_w = 580
    cell_h = 374
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w + pad, rows * cell_h + pad), (9, 12, 24))
    draw = ImageDraw.Draw(sheet)
    font = load_pil_font(18, bold=True)
    for idx, (path, image) in enumerate(thumbs):
        col = idx % cols
        row = idx // cols
        x = pad + col * cell_w
        y = pad + row * cell_h
        draw.rounded_rectangle((x, y, x + cell_w - pad, y + cell_h - pad), radius=18, fill=(18, 24, 44), outline=(68, 86, 142), width=2)
        draw.text((x + 18, y + 10), path.stem.replace("_", " "), fill=(240, 244, 255), font=font)
        px = x + (cell_w - pad - image.width) // 2
        py = y + label_h + (cell_h - pad - label_h - image.height) // 2
        sheet.paste(image, (px, py))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return True


def _make_catalog_crop(
    source: Path,
    out_path: Path,
    *,
    aspect_ratio: float = 16 / 9,
    focus_y: float = 0.5,
    crop_box: tuple[int, int, int, int] | None = None,
) -> bool:
    if not source.exists():
        return False
    try:
        from PIL import Image
    except Exception:
        return False
    try:
        image = Image.open(source).convert("RGB")
    except Exception:
        return False

    width, height = image.size
    if crop_box is None:
        current = width / height if height else aspect_ratio
        if current > aspect_ratio:
            crop_w = int(height * aspect_ratio)
            left = max(0, (width - crop_w) // 2)
            box = (left, 0, left + crop_w, height)
        else:
            crop_h = int(width / aspect_ratio)
            focus_y = min(1.0, max(0.0, focus_y))
            top = int((height - crop_h) * focus_y)
            top = max(0, min(top, height - crop_h))
            box = (0, top, width, top + crop_h)
    else:
        left, top, right, bottom = crop_box
        left = max(0, min(int(left), width - 2))
        top = max(0, min(int(top), height - 2))
        right = max(left + 1, min(int(right), width))
        bottom = max(top + 1, min(int(bottom), height))
        box = (left, top, right, bottom)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.crop(box).save(out_path, quality=95)
    return out_path.exists()


def _sample_resource_path(sample_report: Mapping[str, Any], resource_id: str, root: Path) -> Path | None:
    for resource in list(sample_report.get("resources", []) or []):
        if not isinstance(resource, Mapping):
            continue
        if str(resource.get("id") or "") != resource_id:
            continue
        raw_path = Path(str(resource.get("path") or ""))
        return raw_path if raw_path.is_absolute() else root / raw_path
    return None


def _extract_video_frame(video: Path, out_path: Path, *, at_seconds: float = 0.35) -> bool:
    if not video.exists():
        return False
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except Exception:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        get_ffmpeg_exe(),
        "-y",
        "-ss",
        f"{at_seconds:.2f}",
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-vf",
        "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
        str(out_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return proc.returncode == 0 and out_path.exists()


def _cover_image(image: Any, size: tuple[int, int]) -> Any:
    from PIL import Image, ImageOps

    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    return ImageOps.fit(image, size, method=resample, centering=(0.5, 0.5))


def _draw_pill(
    draw: Any,
    box: tuple[int, int, int, int],
    text: str,
    *,
    font: Any,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int] | None = None,
    text_fill: tuple[int, int, int] = (244, 248, 255),
) -> None:
    draw.rounded_rectangle(box, radius=10, fill=fill, outline=outline, width=1 if outline else 0)
    draw.text((box[0] + 10, box[1] + 5), text, font=font, fill=text_fill)


def _make_active_catalog_surface(
    editor_source: Path,
    frame_source: Path,
    out_path: Path,
) -> bool:
    # Public review images must come from live editor captures, not composed mockups.
    return False
    if not editor_source.exists() or not frame_source.exists():
        return False
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return False
    try:
        editor = Image.open(editor_source).convert("RGB")
        frame = Image.open(frame_source).convert("RGB")
    except Exception:
        return False

    canvas_w, canvas_h = 1280, 720
    base = Image.new("RGB", (canvas_w, canvas_h), (12, 16, 28))
    editor = editor.crop((0, 0, min(editor.width, canvas_w), min(editor.height, canvas_h)))
    base.paste(editor, (0, 0))
    draw = ImageDraw.Draw(base)
    title_font = load_pil_font(22, bold=True)
    label_font = load_pil_font(15, bold=True)
    small_font = load_pil_font(13)
    tiny_font = load_pil_font(11)

    # The public catalog must show an active editing session, never a blank app shell.
    preview_box = (256, 98, 1108, 394)
    preview = _cover_image(frame, (preview_box[2] - preview_box[0], preview_box[3] - preview_box[1]))
    base.paste(preview, preview_box[:2])
    draw.rectangle(preview_box, outline=(232, 238, 250), width=2)
    draw.rectangle((preview_box[0], preview_box[3] - 34, preview_box[2], preview_box[3]), fill=(10, 12, 18))
    draw.text((preview_box[0] + 14, preview_box[3] - 27), "Preview: YouTube sample edit - 00:12:18", font=label_font, fill=(248, 252, 255))
    draw.text((preview_box[2] - 210, preview_box[3] - 27), "Color + Text + Cut", font=label_font, fill=(139, 255, 214))

    # Media bin: show imported real sample material instead of empty project chrome.
    bin_box = (24, 160, 220, 365)
    draw.rounded_rectangle(bin_box, radius=8, fill=(18, 24, 38), outline=(80, 100, 138), width=1)
    draw.text((bin_box[0] + 12, bin_box[1] + 10), "Media Pool", font=label_font, fill=(238, 243, 255))
    thumb = _cover_image(frame, (150, 84))
    base.paste(thumb, (bin_box[0] + 22, bin_box[1] + 42))
    draw.rectangle((bin_box[0] + 22, bin_box[1] + 42, bin_box[0] + 172, bin_box[1] + 126), outline=(139, 255, 214), width=2)
    draw.text((bin_box[0] + 22, bin_box[1] + 136), "youtube_import_01.mp4", font=tiny_font, fill=(237, 241, 248))
    draw.text((bin_box[0] + 22, bin_box[1] + 156), "1280x720 · selected", font=tiny_font, fill=(160, 174, 198))

    # Inspector: visible controls make the shot read like a working edit, not a launch screen.
    inspector_box = (1120, 104, 1262, 392)
    draw.rounded_rectangle(inspector_box, radius=8, fill=(17, 22, 34), outline=(73, 88, 119), width=1)
    draw.text((inspector_box[0] + 12, inspector_box[1] + 10), "Inspector", font=label_font, fill=(238, 243, 255))
    for idx, (name, value, color) in enumerate(
        [
            ("Scale", "118%", (139, 255, 214)),
            ("Position", "+42, -18", (255, 213, 128)),
            ("Opacity", "92%", (198, 171, 255)),
            ("Grade", "warm lift", (255, 151, 151)),
            ("Speed", "1.25x", (143, 188, 255)),
        ]
    ):
        y = inspector_box[1] + 48 + idx * 42
        draw.text((inspector_box[0] + 12, y), name, font=tiny_font, fill=(166, 178, 199))
        draw.rounded_rectangle((inspector_box[0] + 12, y + 17, inspector_box[2] - 12, y + 28), radius=5, fill=(34, 43, 62))
        fill_w = int((inspector_box[2] - inspector_box[0] - 24) * (0.48 + idx * 0.08))
        draw.rounded_rectangle((inspector_box[0] + 12, y + 17, inspector_box[0] + 12 + fill_w, y + 28), radius=5, fill=color)
        draw.text((inspector_box[2] - 66, y), value, font=tiny_font, fill=(239, 244, 255))

    toolbar_y = 414
    draw.rounded_rectangle((254, toolbar_y, 1110, toolbar_y + 44), radius=8, fill=(14, 18, 29), outline=(64, 76, 102), width=1)
    x = 274
    for text, color in [
        ("Cut", (54, 151, 255)),
        ("Erase", (255, 110, 110)),
        ("Color Grade", (139, 255, 214)),
        ("Typo Keyframes", (255, 213, 128)),
        ("Live2D Lane", (198, 171, 255)),
        ("Node FX", (255, 151, 205)),
    ]:
        width = 62 + len(text) * 5
        _draw_pill(draw, (x, toolbar_y + 9, x + width, toolbar_y + 34), text, font=tiny_font, fill=(24, 31, 47), outline=color)
        x += width + 10

    timeline_box = (250, 470, 1120, 682)
    draw.rounded_rectangle(timeline_box, radius=10, fill=(13, 17, 28), outline=(73, 88, 119), width=1)
    draw.text((timeline_box[0] + 16, timeline_box[1] + 12), "Timeline - active edit with cut, filter, text, audio and node lanes", font=label_font, fill=(242, 246, 255))
    for lane, (label, color) in enumerate(
        [
            ("V1  source", (54, 151, 255)),
            ("FX  grade", (139, 255, 214)),
            ("TXT caption", (255, 213, 128)),
            ("AUD voice", (198, 171, 255)),
        ]
    ):
        y = timeline_box[1] + 45 + lane * 36
        draw.text((timeline_box[0] + 16, y + 8), label, font=tiny_font, fill=(165, 178, 200))
        draw.line((timeline_box[0] + 96, y + 18, timeline_box[2] - 18, y + 18), fill=(34, 43, 62), width=1)
        clip_x = timeline_box[0] + 110 + lane * 18
        clip_w = 688 - lane * 22
        draw.rounded_rectangle((clip_x, y, clip_x + clip_w, y + 29), radius=6, fill=(22, 31, 48), outline=color, width=2)
        if lane == 0:
            mini = _cover_image(frame, (54, 29))
            for tx in range(clip_x + 4, clip_x + clip_w - 52, 58):
                base.paste(mini, (tx, y))
            draw.rectangle((clip_x, y, clip_x + clip_w, y + 29), outline=color, width=2)
        elif lane == 1:
            for gx in range(clip_x + 10, clip_x + clip_w - 10, 48):
                draw.ellipse((gx, y + 8, gx + 10, y + 18), fill=color)
        elif lane == 2:
            draw.text((clip_x + 14, y + 7), "타이거캡처 리뷰 자동화 / JP EN KO", font=tiny_font, fill=(255, 250, 230))
        else:
            for gx in range(clip_x + 8, clip_x + clip_w - 8, 16):
                h = 6 + (gx % 31)
                draw.line((gx, y + 24, gx, y + 24 - min(h, 22)), fill=color, width=2)

    playhead_x = 632
    draw.line((playhead_x, timeline_box[1] + 36, playhead_x, timeline_box[3] - 12), fill=(255, 82, 82), width=3)
    draw.polygon([(playhead_x - 8, timeline_box[1] + 35), (playhead_x + 8, timeline_box[1] + 35), (playhead_x, timeline_box[1] + 47)], fill=(255, 82, 82))
    draw.text((playhead_x + 10, timeline_box[1] + 42), "split + effect keyframe", font=tiny_font, fill=(255, 211, 211))

    draw.rectangle((0, 0, canvas_w, 42), fill=(8, 11, 18))
    draw.text((24, 10), "TigerCapture Studio", font=title_font, fill=(244, 248, 255))
    draw.text((1040, 13), "Review evidence capture", font=small_font, fill=(139, 255, 214))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.save(out_path, quality=95)
    return out_path.exists()


def _make_active_timeline_detail(surface: Path, out_path: Path) -> bool:
    if not surface.exists():
        return False
    try:
        from PIL import Image

        with Image.open(surface) as image:
            width, height = image.size
        if width > 0 and height > 0:
            crop_box = (
                int(width * 0.16),
                int(height * 0.54),
                int(width * 0.96),
                int(height * 0.96),
            )
            return _make_catalog_crop(surface, out_path, crop_box=crop_box)
    except Exception:
        pass
    return _make_catalog_crop(
        surface,
        out_path,
        crop_box=(230, 390, 1135, 700),
    )


def feature_editor_surface_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "id": "screen_recording",
            "title": "Screen Recording And Auto Polish",
            "subtitle": "cursor path, click emphasis, auto zoom",
            "chips": ("Auto zoom", "Click rings", "Cursor sidecar", "GIF capture"),
            "panel_title": "Capture polish",
            "panel_rows": ("cursor events: 62", "zoom keys: 4", "loop ready: yes"),
            "lanes": ("screen video", "cursor path", "click pulse", "zoom keys"),
            "accent": (105, 231, 214),
        },
        {
            "id": "creator_assist",
            "title": "Creator Assist And CapCut-Style Workflows",
            "subtitle": "prompt edits, shorts ranges, publish copy",
            "chips": ("Prompt edit", "Shorts plan", "Captions", "Publish copy"),
            "panel_title": "Creator Assist",
            "panel_rows": ("plan: 13 shorts", "captions: ready", "render jobs: 3"),
            "lanes": ("source cut", "short ranges", "captions", "publish notes"),
            "accent": (255, 95, 69),
        },
        {
            "id": "multilingual_localization",
            "title": "Multilingual UI And Localization QA",
            "subtitle": "runtime locale switch with CJK-safe output",
            "chips": ("KO", "EN", "JP", "ZH", "FR", "DE"),
            "panel_title": "Language QA",
            "panel_rows": ("languages: 6", "missing keys: 0", "mojibake: 0"),
            "lanes": ("source clip", "localized UI", "caption text", "font fallback"),
            "accent": (185, 255, 102),
        },
        {
            "id": "ai_script_edit",
            "title": "AI Script Edit And Local LLM",
            "subtitle": "text-driven cuts with explicit provider state",
            "chips": ("Transcript", "Edit plan", "Local LLM", "Safe apply"),
            "panel_title": "Script Edit",
            "panel_rows": ("provider: local/rule", "plan items: 19", "guardrail: on"),
            "lanes": ("dialogue video", "script beats", "planned cuts", "review apply"),
            "accent": (198, 171, 255),
        },
        {
            "id": "timeline_editing",
            "title": "Timeline, Media Pool, And Workbench",
            "subtitle": "cuts, speed, presets, node graph, inspector",
            "chips": ("Split", "Speed", "Markers", "Node FX", "Inspector"),
            "panel_title": "Workbench",
            "panel_rows": ("nodes: active", "preset: applied", "undo depth: 20"),
            "lanes": ("video clips", "markers", "node graph", "metadata"),
            "accent": (105, 231, 214),
        },
        {
            "id": "actors",
            "title": "Live2D, Spine, And NIKKE Actor Tracks",
            "subtitle": "actor lanes beside normal video",
            "chips": ("Live2D lane", "Transform keys", "Opacity", "Export bake"),
            "panel_title": "Actor Inspector",
            "panel_rows": ("lane: actor", "motion keys: 8", "spine claim: blocked"),
            "lanes": ("source video", "actor lane", "transform", "opacity keys"),
            "accent": (198, 171, 255),
        },
        {
            "id": "color_audio_vfx",
            "title": "Color, Audio, Masks, And VFX",
            "subtitle": "grade, scopes, sound editor, masks",
            "chips": ("Color grade", "LUT", "Mask", "Audio cleanup", "Scopes"),
            "panel_title": "Finishing",
            "panel_rows": ("grade: warm", "mask tracked", "true peak: ok"),
            "lanes": ("picture", "grade layer", "mask track", "audio cleanup"),
            "accent": (255, 209, 102),
        },
        {
            "id": "export_parity",
            "title": "Export, Render Queue, And Preview Parity",
            "subtitle": "preview/export parity and render jobs",
            "chips": ("Render queue", "Preview parity", "HDR metadata", "4K"),
            "panel_title": "Delivery",
            "panel_rows": ("jobs: 4", "formats: mp4/webm/mov", "parity: checked"),
            "lanes": ("timeline", "pre-render", "metadata", "render queue"),
            "accent": (143, 188, 255),
        },
        {
            "id": "ar_pbr_3d",
            "title": "AR/PBR 3D Compositor",
            "subtitle": "3D object, camera solve, editor composite",
            "chips": ("3D object", "Camera solve", "HDRI", "PBR"),
            "panel_title": "AR/PBR",
            "panel_rows": ("tracking: solved", "PBR: enabled", "camera scene: loaded"),
            "lanes": ("plate video", "camera solve", "3D object", "composite"),
            "accent": (255, 151, 205),
        },
        {
            "id": "performance_health",
            "title": "Performance, Health, And Native Worker",
            "subtitle": "health center, cache, worker boundary",
            "chips": ("Health Center", "Cache", "Native worker", "Crash status"),
            "panel_title": "Runtime Health",
            "panel_rows": ("qa rows: tracked", "cache: warm", "worker: optional"),
            "lanes": ("editor state", "cache events", "worker jobs", "health alerts"),
            "accent": (105, 231, 214),
        },
        {
            "id": "productization_release",
            "title": "Productization, Release Evidence, And Positioning",
            "subtitle": "release guardrails and evidence graph",
            "chips": ("Release gates", "Evidence graph", "Review deck", "Safe claims"),
            "panel_title": "Productization",
            "panel_rows": ("claims: gated", "evidence: linked", "deck modes: 3"),
            "lanes": ("feature", "evidence", "qa result", "release gate"),
            "accent": (185, 255, 102),
        },
    )


def feature_editor_surface_artifact_id(topic_id: str) -> str:
    return f"feature_{topic_id}_editor_surface"


def _make_feature_editor_surface(
    editor_source: Path,
    frame_source: Path,
    out_path: Path,
    *,
    spec: Mapping[str, Any],
) -> bool:
    # Feature pages require live action captures. Missing captures stay pending.
    return False
    if not editor_source.exists() or not frame_source.exists():
        return False
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return False
    try:
        editor = Image.open(editor_source).convert("RGB")
        frame = Image.open(frame_source).convert("RGB")
    except Exception:
        return False

    canvas_w, canvas_h = 1280, 720
    base = Image.new("RGB", (canvas_w, canvas_h), (8, 11, 18))
    editor = editor.crop((0, 0, min(editor.width, canvas_w), min(editor.height, canvas_h)))
    base.paste(editor, (0, 0))
    overlay = Image.new("RGB", (canvas_w, canvas_h), (8, 11, 18))
    base = Image.blend(base, overlay, 0.18)
    draw = ImageDraw.Draw(base)

    title_font = load_pil_font(24, bold=True)
    sub_font = load_pil_font(14)
    label_font = load_pil_font(15, bold=True)
    small_font = load_pil_font(12)
    tiny_font = load_pil_font(10)
    accent = tuple(spec.get("accent") or (105, 231, 214))
    title = str(spec.get("title") or spec.get("id") or "Feature")
    subtitle = str(spec.get("subtitle") or "automated review capture")

    draw.rectangle((0, 0, canvas_w, 48), fill=(7, 9, 15))
    draw.text((24, 10), "TigerCapture Studio", font=title_font, fill=(246, 241, 232))
    draw.text((940, 16), "Automated feature review", font=sub_font, fill=accent)

    preview_box = (258, 88, 970, 362)
    preview = _cover_image(frame, (preview_box[2] - preview_box[0], preview_box[3] - preview_box[1]))
    base.paste(preview, preview_box[:2])
    draw.rectangle(preview_box, outline=(232, 238, 250), width=2)
    draw.rectangle((preview_box[0], preview_box[3] - 34, preview_box[2], preview_box[3]), fill=(9, 12, 19))
    draw.text((preview_box[0] + 14, preview_box[3] - 26), title, font=label_font, fill=(248, 252, 255))
    draw.text((preview_box[2] - 260, preview_box[3] - 26), subtitle, font=small_font, fill=accent)

    panel_box = (24, 128, 228, 540)
    draw.rounded_rectangle(panel_box, radius=8, fill=(16, 21, 34), outline=accent, width=2)
    draw.text((panel_box[0] + 14, panel_box[1] + 14), str(spec.get("panel_title") or "Feature"), font=label_font, fill=(246, 241, 232))
    thumb = _cover_image(frame, (158, 88))
    base.paste(thumb, (panel_box[0] + 23, panel_box[1] + 52))
    draw.rectangle((panel_box[0] + 23, panel_box[1] + 52, panel_box[0] + 181, panel_box[1] + 140), outline=(246, 241, 232), width=1)
    y = panel_box[1] + 160
    for row in tuple(spec.get("panel_rows") or ())[:5]:
        draw.text((panel_box[0] + 18, y), str(row), font=small_font, fill=(194, 204, 224))
        y += 27
    draw.text((panel_box[0] + 18, panel_box[3] - 38), "source: review sample", font=tiny_font, fill=(136, 149, 174))

    chips = tuple(spec.get("chips") or ())
    x = 258
    for chip in chips[:6]:
        width = max(76, 34 + len(str(chip)) * 7)
        _draw_pill(draw, (x, 386, min(x + width, 1110), 415), str(chip), font=tiny_font, fill=(20, 27, 42), outline=accent)
        x += width + 10
        if x > 1100:
            break

    inspector = (996, 88, 1254, 362)
    draw.rounded_rectangle(inspector, radius=8, fill=(17, 22, 34), outline=(73, 88, 119), width=1)
    draw.text((inspector[0] + 14, inspector[1] + 14), "Feature Inspector", font=label_font, fill=(246, 241, 232))
    for idx, chip in enumerate(chips[:5]):
        y = inspector[1] + 54 + idx * 38
        draw.text((inspector[0] + 14, y), str(chip), font=tiny_font, fill=(194, 204, 224))
        draw.rounded_rectangle((inspector[0] + 14, y + 17, inspector[2] - 18, y + 28), radius=5, fill=(34, 43, 62))
        fill_w = int((inspector[2] - inspector[0] - 32) * (0.45 + idx * 0.08))
        draw.rounded_rectangle((inspector[0] + 14, y + 17, inspector[0] + 14 + fill_w, y + 28), radius=5, fill=accent)

    timeline_box = (248, 444, 1248, 676)
    draw.rounded_rectangle(timeline_box, radius=10, fill=(13, 17, 28), outline=(73, 88, 119), width=1)
    draw.text((timeline_box[0] + 18, timeline_box[1] + 13), "Feature workflow timeline", font=label_font, fill=(246, 241, 232))
    mini = _cover_image(frame, (50, 28))
    lanes = tuple(spec.get("lanes") or ("source", "feature", "evidence", "qa"))
    for lane, label in enumerate(lanes[:4]):
        y = timeline_box[1] + 48 + lane * 39
        lane_color = accent if lane != 2 else (255, 209, 102)
        draw.text((timeline_box[0] + 18, y + 8), str(label), font=tiny_font, fill=(164, 177, 201))
        clip_x = timeline_box[0] + 132 + lane * 20
        clip_w = 700 - lane * 36
        draw.rounded_rectangle((clip_x, y, clip_x + clip_w, y + 30), radius=6, fill=(22, 31, 48), outline=lane_color, width=2)
        if lane == 0:
            for tx in range(clip_x + 4, clip_x + clip_w - 48, 54):
                base.paste(mini, (tx, y + 1))
        elif lane == 1:
            for gx in range(clip_x + 12, clip_x + clip_w - 12, 46):
                draw.ellipse((gx, y + 9, gx + 11, y + 20), fill=lane_color)
        elif lane == 2:
            draw.text((clip_x + 14, y + 8), "review action evidence", font=tiny_font, fill=(255, 248, 220))
        else:
            for gx in range(clip_x + 10, clip_x + clip_w - 10, 18):
                h = 7 + ((gx // 3) % 20)
                draw.line((gx, y + 24, gx, y + 24 - h), fill=lane_color, width=2)

    playhead_x = 690
    draw.line((playhead_x, timeline_box[1] + 36, playhead_x, timeline_box[3] - 12), fill=(255, 82, 82), width=3)
    draw.polygon([(playhead_x - 9, timeline_box[1] + 34), (playhead_x + 9, timeline_box[1] + 34), (playhead_x, timeline_box[1] + 48)], fill=(255, 82, 82))
    draw.text((playhead_x + 12, timeline_box[1] + 38), "captured step", font=tiny_font, fill=(255, 211, 211))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.save(out_path, quality=95)
    return out_path.exists()


def _feature_artifact_row(
    *,
    spec: Mapping[str, Any],
    source: Path,
    out_path: Path,
    project_root: Path,
    ok: bool,
    seeded_from_ui_renewal_index: bool = False,
    evidence_feature_area: str = "",
) -> dict[str, Any]:
    topic_id = str(spec.get("id") or "")
    return {
        "id": feature_editor_surface_artifact_id(topic_id),
        "title": f"{spec.get('title', topic_id)} editor review surface",
        "kind": "screenshot",
        "source_path": relpath(source, root=project_root),
        "output_path": relpath(out_path, root=project_root),
        "exists": bool(ok and out_path.exists()),
        "size": int(out_path.stat().st_size) if out_path.exists() else 0,
        "public": True,
        "feature_editor": True,
        "feature_topic_id": topic_id,
        "capture_method": "live_editor_action_capture",
        "action_scenario_id": f"feature_{topic_id}_action_review",
        "automation_contract": "feature_action_scenarios",
        "seeded_from_ui_renewal_index": bool(seeded_from_ui_renewal_index),
        "evidence_feature_area": evidence_feature_area,
    }


def _catalog_artifact_row(
    *,
    asset_id: str,
    title: str,
    source: Path,
    out_path: Path,
    project_root: Path,
    ok: bool,
    active_editor: bool = False,
) -> dict[str, Any]:
    return {
        "id": asset_id,
        "title": title,
        "kind": "screenshot",
        "source_path": relpath(source, root=project_root),
        "output_path": relpath(out_path, root=project_root),
        "exists": bool(ok and out_path.exists()),
        "size": int(out_path.stat().st_size) if out_path.exists() else 0,
        "public": True,
        "active_editor": bool(active_editor),
        "catalog_rule": "no_empty_editor" if active_editor else None,
    }


def _make_gif_from_video(video: Path, out_path: Path, *, seconds: float = 4.0) -> bool:
    if not video.exists():
        return False
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except Exception:
        return False
    ffmpeg = get_ffmpeg_exe()
    start_seconds = _find_nonblank_video_start(video, ffmpeg_path=ffmpeg, max_start=60.0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{start_seconds:.2f}",
        "-i",
        str(video),
        "-t",
        f"{seconds:.2f}",
        "-vf",
        "fps=10,scale=640:-1:flags=lanczos",
        str(out_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return proc.returncode == 0 and out_path.exists()


def _find_nonblank_video_start(video: Path, *, ffmpeg_path: str, max_start: float) -> float:
    """Pick a visually useful GIF start time from a real source video.

    Some imported YouTube clips have black leader frames. Review artifacts
    should still use the real video, but not the empty leader.
    """

    candidates = [0.0, 0.75, 1.5, 2.5, 3.5, 4.75, 5.5, 6.25]
    best: tuple[float, float] = (0.0, -1.0)
    for at in candidates:
        if at > max_start:
            continue
        score = _video_frame_detail_score(video, ffmpeg_path=ffmpeg_path, at_seconds=at)
        if score > best[1]:
            best = (at, score)
        if score >= 18.0:
            return at
    return best[0]


def _video_frame_detail_score(video: Path, *, ffmpeg_path: str, at_seconds: float) -> float:
    try:
        from PIL import Image, ImageStat
    except Exception:
        return 0.0
    with tempfile.TemporaryDirectory() as tmp:
        frame = Path(tmp) / "frame.png"
        proc = subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-ss",
                f"{at_seconds:.2f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                "scale=160:-1:flags=fast_bilinear",
                str(frame),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proc.returncode != 0 or not frame.exists():
            return 0.0
        image = Image.open(frame).convert("L")
        stat = ImageStat.Stat(image)
        mean = float(stat.mean[0]) if stat.mean else 0.0
        stddev = float(stat.stddev[0]) if stat.stddev else 0.0
        if mean < 4.0:
            return stddev * 0.25
        return mean * 0.25 + stddev


def collect_review_artifacts(
    *,
    project_root: str | Path = ROOT,
    out_dir: str | Path,
    sample_report: Mapping[str, Any],
    force: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    root = Path(project_root)
    assets_dir = Path(out_dir) / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    artifacts: list[dict[str, Any]] = []
    try:
        from .ui_evidence_index import preferred_catalog_editor_source, seed_feature_editor_surfaces_from_index
    except Exception:
        preferred_catalog_editor_source = None
        seed_feature_editor_surfaces_from_index = None

    evidence_catalog_record = (
        preferred_catalog_editor_source(project_root=root)
        if callable(preferred_catalog_editor_source)
        else None
    )
    evidence_catalog_source = (
        evidence_catalog_record.artifact
        if evidence_catalog_record is not None and getattr(evidence_catalog_record, "exists", False)
        else None
    )
    seeded_feature_sources = (
        seed_feature_editor_surfaces_from_index(project_root=root, assets_dir=assets_dir, force=force)
        if callable(seed_feature_editor_surfaces_from_index)
        else {}
    )

    fixed_sources = [
        (
            "editor_imported",
            "Editor imported timeline",
            "screenshot",
            evidence_catalog_source or root / "debugCapture/editor_e2e_smoke/editor_imported.png",
        ),
        ("editor_actor_project", "Actor lane project", "screenshot", root / "debugCapture/editor_e2e_smoke/editor_actor_project.png"),
        ("preview_popout", "Preview popout", "screenshot", root / "debugCapture/editor_e2e_smoke/preview_popout.png"),
        ("editor_contact_sheet", "Editor E2E contact sheet", "contact_sheet", root / "debugCapture/editor_e2e_smoke/editor_e2e_smoke_contact_sheet.png"),
    ]
    for asset_id, title, kind, source in fixed_sources:
        row = copy_asset(source, assets_dir, asset_id=asset_id, title=title, kind=kind, project_root=root)
        artifacts.append(row)
        if not row["exists"]:
            warnings.append(f"missing artifact source: {row['source_path']}")

    editor_imported = evidence_catalog_source or root / "debugCapture/editor_e2e_smoke/editor_imported.png"
    catalog_surface = assets_dir / "catalog_editor_surface.png"
    scenario_frame = Path(out_dir) / "action_scenarios/action_scenario_youtube_frame.png"
    extracted_frame = assets_dir / "catalog_active_video_frame.png"
    overview_video = _sample_resource_path(sample_report, "overview_screen_demo", root)
    active_frame = scenario_frame if scenario_frame.exists() else extracted_frame
    if not active_frame.exists() and overview_video is not None:
        _extract_video_frame(overview_video, extracted_frame)
    catalog_surface_ok = _make_catalog_crop(editor_imported, catalog_surface, focus_y=0.52)
    artifacts.append(
        _catalog_artifact_row(
            asset_id="catalog_editor_surface",
            title="Public catalog imported editor surface",
            source=editor_imported,
            out_path=catalog_surface,
            project_root=root,
            ok=catalog_surface_ok,
            active_editor=True,
        )
    )
    if not catalog_surface_ok:
        warnings.append("failed to build public catalog imported editor surface; live YouTube import capture is required")

    timeline_detail = assets_dir / "catalog_timeline_detail.png"
    timeline_detail_ok = _make_active_timeline_detail(catalog_surface, timeline_detail)
    artifacts.append(
        _catalog_artifact_row(
            asset_id="catalog_timeline_detail",
            title="Public catalog active timeline detail",
            source=catalog_surface,
            out_path=timeline_detail,
            project_root=root,
            ok=timeline_detail_ok,
            active_editor=True,
        )
    )
    if not timeline_detail_ok:
        warnings.append("failed to build public catalog active timeline detail; empty editor fallback is forbidden")

    scenario_dir = Path(out_dir) / "action_scenarios"
    live_by_topic: dict[str, Mapping[str, Any]] = {}
    live_report_path = scenario_dir / "feature_action_scenarios_live.json"
    if live_report_path.exists():
        try:
            live_payload = json.loads(live_report_path.read_text(encoding="utf-8"))
        except Exception:
            live_payload = {}
        if isinstance(live_payload, Mapping):
            live_by_topic = {
                str(row.get("topic_id") or ""): row
                for row in list(live_payload.get("scenarios", []) or [])
                if isinstance(row, Mapping) and row.get("topic_id")
            }

    for spec in feature_editor_surface_specs():
        topic_id = str(spec.get("id") or "")
        if not topic_id:
            continue
        feature_surface = assets_dir / f"{feature_editor_surface_artifact_id(topic_id)}.png"
        seeded_record = seeded_feature_sources.get(topic_id) if isinstance(seeded_feature_sources, Mapping) else None
        source_surface = (
            seeded_record.artifact
            if seeded_record is not None and getattr(seeded_record, "exists", False)
            else feature_surface
        )
        live_row = live_by_topic.get(topic_id)
        live_validation = live_row.get("live_validation") if isinstance(live_row, Mapping) and isinstance(live_row.get("live_validation"), Mapping) else {}
        live_validation_ok = bool(live_validation.get("ok", True))
        feature_ok = feature_surface.exists() and live_validation_ok
        artifacts.append(
            _feature_artifact_row(
                spec=spec,
                source=source_surface,
                out_path=feature_surface,
                project_root=root,
                ok=feature_ok,
                seeded_from_ui_renewal_index=seeded_record is not None,
                evidence_feature_area=str(getattr(seeded_record, "feature_area", "") or ""),
            )
        )
        if not feature_ok:
            if feature_surface.exists() and not live_validation_ok:
                warnings.append(f"live feature editor capture failed visual validation: {topic_id} ({live_validation.get('status', 'unknown')})")
            else:
                warnings.append(f"missing live feature editor capture: {topic_id}")

    for resource in list(sample_report.get("resources", []) or []):
        if not isinstance(resource, Mapping):
            continue
        resource_id = str(resource.get("id") or "")
        if not resource_id:
            continue
        source = root / str(resource.get("path") or "")
        row = copy_asset(
            source,
            assets_dir,
            asset_id=resource_id,
            title=str(resource.get("title") or resource_id),
            kind=str(resource.get("kind") or "file"),
            project_root=root,
        )
        artifacts.append(row)
        if not row["exists"]:
            warnings.append(f"missing sample resource: {row['source_path']}")

    for asset_id, title, kind, source in (
        (
            "action_scenario_timeline",
            "Action automation timeline storyboard",
            "screenshot",
            scenario_dir / "action_scenario_timeline.png",
        ),
        (
            "action_scenario_report",
            "Action automation scenario report",
            "json",
            scenario_dir / "action_scenario_report.json",
        ),
        (
            "action_scenario_youtube_frame",
            "Action scenario YouTube sample frame",
            "image",
            scenario_dir / "action_scenario_youtube_frame.png",
        ),
    ):
        if not source.exists():
            continue
        artifacts.append(
            {
                "id": asset_id,
                "title": title,
                "kind": kind,
                "source_path": relpath(source, root=root),
                "output_path": relpath(source, root=root),
                "exists": True,
                "size": int(source.stat().st_size),
            }
        )

    image_outputs = [
        root / row["output_path"]
        for row in artifacts
        if row.get("exists") and str(row.get("kind")) in {"screenshot", "image", "contact_sheet"}
    ]
    contact_sheet = assets_dir / "review_contact_sheet.png"
    if force or not contact_sheet.exists():
        if not _make_contact_sheet(image_outputs[:8], contact_sheet):
            warnings.append("failed to build review contact sheet")
    artifacts.append(
        {
            "id": "review_contact_sheet",
            "title": "Review automation contact sheet",
            "kind": "contact_sheet",
            "source_path": "",
            "output_path": relpath(contact_sheet, root=root),
            "exists": contact_sheet.exists(),
            "size": int(contact_sheet.stat().st_size) if contact_sheet.exists() else 0,
        }
    )

    cursor_video: Path | None = None
    for resource in list(sample_report.get("resources", []) or []):
        if not isinstance(resource, Mapping):
            continue
        if resource.get("id") != "screenstudio_cursor_demo":
            continue
        raw_path = Path(str(resource.get("path") or ""))
        cursor_video = raw_path if raw_path.is_absolute() else root / raw_path
        break
    if cursor_video is None:
        cursor_video = assets_dir / "_missing_screenstudio_cursor_demo.mp4"
    cursor_gif = assets_dir / "screenstudio_cursor_demo.gif"
    if force or not cursor_gif.exists():
        if not _make_gif_from_video(cursor_video, cursor_gif):
            warnings.append("failed to build Screen Studio cursor GIF")
    artifacts.append(
        {
            "id": "screenstudio_cursor_gif",
            "title": "Screen Studio cursor GIF",
            "kind": "gif",
            "source_path": relpath(cursor_video, root=root),
            "output_path": relpath(cursor_gif, root=root),
            "exists": cursor_gif.exists(),
            "size": int(cursor_gif.stat().st_size) if cursor_gif.exists() else 0,
        }
    )
    return artifacts, warnings
