from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent / "ReviewAutomationWorkspace"
TEMPLATES = WORKSPACE / "source_assets" / "templates"
TMP = WORKSPACE / "tmp"
OUT = TMP / "catalog_deck_build" / "preview_pages"


def _font(size: int, *, mono: bool = False) -> ImageFont.ImageFont:
    paths = (
        [Path("C:/Windows/Fonts/consola.ttf"), Path("C:/Windows/Fonts/cour.ttf")]
        if mono
        else [Path("C:/Windows/Fonts/segoeui.ttf"), Path("C:/Windows/Fonts/arial.ttf")]
    )
    for path in paths:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = img.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def _contain(img: Image.Image, size: tuple[int, int], fill: str = "#111418") -> Image.Image:
    target_w, target_h = size
    src_w, src_h = img.size
    scale = min(target_w / src_w, target_h / src_h)
    resized = img.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    out = Image.new("RGB", size, fill)
    out.paste(resized, ((target_w - resized.width) // 2, (target_h - resized.height) // 2))
    return out


def _rounded_paste(base: Image.Image, img: Image.Image, box: tuple[int, int, int, int], radius: int = 6) -> None:
    x0, y0, x1, y1 = box
    crop = _cover(img.convert("RGB"), (x1 - x0, y1 - y0)).convert("RGBA")
    mask = Image.new("L", crop.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, crop.width, crop.height), radius=radius, fill=255)
    base.paste(crop, (x0, y0), mask)


def _label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str) -> None:
    x, y = xy
    font = _font(18, mono=True)
    pad_x, pad_y = 9, 5
    bbox = draw.textbbox((x, y), text, font=font)
    draw.rounded_rectangle(
        (x - pad_x, y - pad_y, bbox[2] + pad_x, bbox[3] + pad_y),
        radius=7,
        fill=(14, 17, 21, 210),
        outline=(65, 72, 82, 210),
        width=1,
    )
    draw.text((x, y), text, fill=(230, 232, 231, 255), font=font)


def _text_wrap(text: str, width: int, font: ImageFont.ImageFont) -> list[str]:
    lines: list[str] = []
    for raw in text.split("\n"):
        words = raw.split()
        line = ""
        for word in words:
            probe = word if not line else f"{line} {word}"
            if font.getlength(probe) <= width:
                line = probe
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines


def _soft_clear_text_area(base: Image.Image) -> None:
    """Remove baked copy from the template without leaving a hard card edge."""
    rect = (74, 300, 620, 672)
    fill = Image.new("RGBA", (rect[2] - rect[0], rect[3] - rect[1]), (248, 247, 244, 255))
    mask = Image.new("L", fill.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    inset = 18
    mask_draw.rectangle(
        (inset, inset, fill.width - inset, fill.height - inset),
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(20))
    base.paste(fill, rect[:2], mask)


def _draw_catalog_text(base: Image.Image, title: str, body: str, *, section: str = "POST PRODUCTION") -> None:
    draw = ImageDraw.Draw(base)
    _soft_clear_text_area(base)
    draw.text((115, 350), title, fill=(31, 32, 33, 255), font=_font(54), spacing=10)
    body_font = _font(20)
    y = 508
    for line in _text_wrap(body, 390, body_font):
        draw.text((118, y), line, fill=(92, 93, 90, 255), font=body_font)
        y += 30
    pager_font = _font(16, mono=True)
    draw.text((115, 607), "/  01  /  02  /  03", fill=(36, 37, 38, 255), font=pager_font)


def _load(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def _lamborghini_editor() -> Image.Image:
    editor = _load(TMP / "fresh_review_recapture" / "catalog_multimedia_lamborghini" / "editor_catalog_multimedia_lamborghini.png")
    frame = _load(TMP / "catalog_pretty_frames" / "lamborghini_driving_0126.png")
    # GPU viewer grabs can be black; replace only the actual viewer content with
    # a real frame from the same imported Lamborghini source.
    _rounded_paste(editor, frame, (206, 126, 890, 503), radius=10)
    return editor


def _node_editor() -> Image.Image:
    editor = _load(TMP / "fresh_review_recapture" / "node_color_tokyo" / "editor_workbench_node_graph_action.png")
    frame = _load(TMP / "catalog_pretty_frames" / "tokyo_tower_aerial_0223.png")
    _rounded_paste(editor, frame, (206, 126, 890, 503), radius=10)
    return editor


def _ai_editor() -> Image.Image:
    editor = _load(TMP / "fresh_first_slide_capture" / "center_ai" / "editor_ai_command_open_action.png")
    frame = _load(TMP / "catalog_pretty_frames" / "taichung_night_hero_0115.png")
    _rounded_paste(editor, frame, (206, 126, 890, 503), radius=10)
    return editor


def _best_ar_pbr_asset_capture() -> tuple[Image.Image, str]:
    candidates = (
        (
            TMP / "actual_3d_viewer_capture" / "nexus_rx_preview_action_zoom.png",
            "Nexus RX Preview",
        ),
        (
            TMP / "actual_3d_viewer_capture" / "alternates" / "angle_sweep" / "nexus_p10_y35.png",
            "Nexus RX GLTF",
        ),
        (
            TMP / "actual_3d_viewer_capture" / "alternates" / "police_sweep" / "police_p10_y35.png",
            "Police Car GLTF",
        ),
        (
            TMP / "actual_3d_viewer_capture" / "polyhaven_camera_3d_viewer_no_cubemap_actual.png",
            "3D Camera Scene",
        ),
    )
    for path, label in candidates:
        if path.exists():
            return _load(path), label
    return _load(TMP / "actual_3d_viewer_capture" / "polyhaven_camera_3d_viewer_no_cubemap_actual.png"), "3D Camera Scene"


def _make_left_monitor_screen(path: Path) -> None:
    screen = Image.new("RGB", (1440, 1000), "#0d1117")
    draw = ImageDraw.Draw(screen, "RGBA")
    ar_asset, ar_label = _best_ar_pbr_asset_capture()
    live2d = _load(TMP / "fresh_review_recapture" / "live2d_simple_bg" / "live2d_viewer_action.png")
    mmd = _load(TMP / "fresh_first_slide_capture" / "left_mmd" / "mmd_player_cantarella_fresh.png")
    _rounded_paste(screen, ar_asset, (28, 34, 850, 966), radius=18)
    _rounded_paste(screen, live2d, (880, 34, 1410, 490), radius=18)
    _rounded_paste(screen, mmd, (880, 520, 1410, 966), radius=18)
    _label(draw, (55, 58), ar_label)
    _label(draw, (908, 58), "Live2D Viewer")
    _label(draw, (908, 544), "MMD Player")
    screen.save(path)


def _make_right_monitor_screen(path: Path) -> None:
    screen = Image.new("RGB", (1440, 1000), "#0d1117")
    draw = ImageDraw.Draw(screen, "RGBA")
    node = _load(TMP / "fresh_review_recapture" / "node_color_tokyo" / "workbench_node_graph_action.png")
    sound = _load(TMP / "fresh_first_slide_capture" / "right_sound" / "sound_editor_graphs_contact_sheet.png")
    mixer = _load(TMP / "fresh_review_recapture" / "node_color_tokyo" / "editor_audio_mixer_action.png")
    _rounded_paste(screen, node, (24, 32, 1416, 570), radius=18)
    _rounded_paste(screen, sound, (24, 594, 782, 966), radius=18)
    _rounded_paste(screen, mixer, (806, 594, 1416, 966), radius=18)
    _label(draw, (54, 58), "Node Graph")
    _label(draw, (54, 620), "Sound Editor")
    _label(draw, (835, 620), "Audio Mixer")
    screen.save(path)


def _make_multi_monitor_page(out_path: Path) -> None:
    template = _load(TEMPLATES / "multi_monitor_front_facing_catalog_template_v2_tight_clean.png")
    screen_map = json.loads((TEMPLATES / "multi_monitor_front_facing_catalog_template_v2_tight_clean.screen-map.json").read_text(encoding="utf-8"))
    build_dir = out_path.parent / "screens"
    build_dir.mkdir(parents=True, exist_ok=True)
    left = build_dir / "overview_left_actor_3d_screen.png"
    center = build_dir / "overview_center_lamborghini_editor_screen.png"
    right = build_dir / "overview_right_node_sound_screen.png"
    _make_left_monitor_screen(left)
    _lamborghini_editor().save(center)
    _make_right_monitor_screen(right)
    sources = {"left_monitor": left, "center_monitor": center, "right_monitor": right}
    for region in screen_map["screen_regions"]:
        rect = region["rect"]
        img = _load(sources[region["id"]])
        fitted = _cover(img.convert("RGB"), (rect["width"], rect["height"])).convert("RGBA")
        template.paste(fitted, (rect["x"], rect["y"]))
    template.save(out_path)


def _paste_template_screens(base: Image.Image, screens: dict[str, Image.Image], map_path: Path) -> None:
    screen_map = json.loads(map_path.read_text(encoding="utf-8"))
    for key, spec in screen_map["screens"].items():
        img = screens[key]
        fitted = _cover(img.convert("RGB"), (spec["width"], spec["height"])).convert("RGBA")
        base.paste(fitted, (spec["x"], spec["y"]))


def _crop_ai_detail(editor: Image.Image) -> Image.Image:
    # AI dock and provider/command line area.
    return editor.crop((360, 520, 1480, 845))


def _make_laptop_ipad_page(out_path: Path, *, title: str, body: str, laptop: Image.Image, ipad: Image.Image) -> None:
    base = _load(TEMPLATES / "laptop_ipad_catalog_template_v4.png")
    _paste_template_screens(
        base,
        {"laptop_screen": laptop, "ipad_screen": ipad},
        TEMPLATES / "laptop_ipad_catalog_template_v4.screen-map.json",
    )
    _draw_catalog_text(base, title, body)
    base.save(out_path)


def build_preview_pages() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    p = OUT / "catalog_preview_01_multi_monitor_overview.png"
    _make_multi_monitor_page(p)
    outputs.append(p)

    ai = _ai_editor()
    p = OUT / "catalog_preview_02_ai_actions.png"
    _make_laptop_ipad_page(
        p,
        title="Claude-Connected\nEditor Actions",
        body="Use Claude, Codex, local LLMs, and registered actions to plan visible edits before applying them.",
        laptop=ai,
        ipad=_crop_ai_detail(ai),
    )
    outputs.append(p)

    node = _node_editor()
    p = OUT / "catalog_preview_03_node_and_fx.png"
    _make_laptop_ipad_page(
        p,
        title="Node Graph\nComposition",
        body="Connect blur, glow, grade, mask, and LUT nodes while the timeline keeps the edit readable.",
        laptop=node,
        ipad=_load(TMP / "fresh_review_recapture" / "node_color_tokyo" / "workbench_node_graph_action.png"),
    )
    outputs.append(p)

    ar, _ = _best_ar_pbr_asset_capture()
    p = OUT / "catalog_preview_04_ar_pbr_3d_asset.png"
    _make_laptop_ipad_page(
        p,
        title="AR/PBR\n3D Asset",
        body="Preview a real textured 3D asset with lighting, shadow, tone, and depth-aware placement controls.",
        laptop=ar,
        ipad=_contain(ar, (800, 560), fill="#111418"),
    )
    outputs.append(p)
    return outputs


def main() -> int:
    outputs = build_preview_pages()
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
