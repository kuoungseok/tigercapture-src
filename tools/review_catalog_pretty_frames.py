from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import cv2
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MEDIA_DIR = Path.home() / "Videos" / "TigerCapture" / "YouTube Imports"
DEFAULT_OUT_DIR = ROOT.parent / "ReviewAutomationWorkspace" / "tmp" / "catalog_pretty_frames"


@dataclass(frozen=True)
class PrettyFrame:
    frame_id: str
    glob: str
    seconds: float
    title: str
    usage: str


PRETTY_FRAMES: tuple[PrettyFrame, ...] = (
    PrettyFrame(
        "taichung_night_highway_0034",
        "*WTLcykcv-H0*.mp4",
        34.0,
        "Taichung night highway",
        "City/night skyline, color grading, media pool alternate",
    ),
    PrettyFrame(
        "taichung_night_city_grid_0100",
        "*WTLcykcv-H0*.mp4",
        60.0,
        "Taichung city grid",
        "City/night skyline, dense editor preview alternate",
    ),
    PrettyFrame(
        "taichung_night_hero_0115",
        "*WTLcykcv-H0*.mp4",
        75.0,
        "Taichung skyline hero",
        "Primary Taichung catalog frame when a strong night city image is needed",
    ),
    PrettyFrame(
        "tokyo_tower_aerial_0223",
        "*Ui4UpsZH4Jw*.mp4",
        143.0,
        "Tokyo tower aerial",
        "Node, compositing, effects, color page alternate",
    ),
    PrettyFrame(
        "fallingwater_walkway_0355",
        "*q8dcnh-4I6g*.mp4",
        235.0,
        "Fallingwater warm walkway",
        "Architecture, masking, depth-aware explanation",
    ),
    PrettyFrame(
        "fallingwater_exterior_1328",
        "*q8dcnh-4I6g*.mp4",
        808.0,
        "Fallingwater exterior",
        "Architecture, 3D/PBR context, calm Live2D alternate",
    ),
    PrettyFrame(
        "lamborghini_engine_0034",
        "*sitXeGjm4Mc*.mp4",
        34.0,
        "Lamborghini engine detail",
        "Automotive detail, cut/edit insert only",
    ),
    PrettyFrame(
        "lamborghini_driving_0126",
        "*sitXeGjm4Mc*.mp4",
        86.0,
        "Lamborghini tunnel driving",
        "First multi-monitor center preview and cutting workflow hero",
    ),
    PrettyFrame(
        "south_korea_bridge_0351",
        "*AA-sv3ilNBE*.mp4",
        231.0,
        "South Korea fog bridge",
        "Soft, bright overview/detail page alternate",
    ),
    PrettyFrame(
        "south_korea_songdo_0924",
        "*AA-sv3ilNBE*.mp4",
        564.0,
        "South Korea Songdo skyline",
        "Clean daytime city, media pool and export examples",
    ),
)


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _cover_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = img.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def _resolve_source(media_dir: Path, pattern: str) -> Path:
    matches = sorted(media_dir.glob(pattern))
    matches = [p for p in matches if "Le Mans" not in p.name and "FIA WEC" not in p.name]
    if not matches:
        raise FileNotFoundError(f"no media matches {pattern!r} in {media_dir}")
    return matches[0]


def _extract_frame(path: Path, seconds: float) -> Image.Image:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"failed to open video: {path}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        target = max(0, int(round(seconds * fps)))
        if frame_count:
            target = min(target, max(0, frame_count - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ok, frame = cap.read()
        if not ok or frame is None:
            cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000.0)
            ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError(f"failed to decode frame at {seconds:.2f}s: {path}")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)
    finally:
        cap.release()


def _make_contact_sheet(rows: Iterable[dict[str, object]], out_path: Path) -> None:
    rows = list(rows)
    thumb_size = (420, 236)
    gap = 22
    label_h = 72
    cols = 3
    sheet_w = cols * thumb_size[0] + (cols + 1) * gap
    sheet_h = ((len(rows) + cols - 1) // cols) * (thumb_size[1] + label_h + gap) + gap
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#f1f0ed")
    draw = ImageDraw.Draw(sheet)
    title_font = _font(22)
    meta_font = _font(15)
    for idx, row in enumerate(rows):
        col = idx % cols
        line = idx // cols
        x = gap + col * (thumb_size[0] + gap)
        y = gap + line * (thumb_size[1] + label_h + gap)
        img = Image.open(str(row["path"])).convert("RGB")
        img = _cover_resize(img, thumb_size)
        sheet.paste(img, (x, y))
        draw.rectangle((x, y, x + thumb_size[0], y + thumb_size[1]), outline="#d8d5cf", width=1)
        draw.text((x, y + thumb_size[1] + 12), str(row["title"]), fill="#202124", font=title_font)
        draw.text((x, y + thumb_size[1] + 42), str(row["timecode"]), fill="#777872", font=meta_font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def build_pretty_frames(media_dir: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for candidate in PRETTY_FRAMES:
        source = _resolve_source(media_dir, candidate.glob)
        img = _extract_frame(source, candidate.seconds)
        frame_path = out_dir / f"{candidate.frame_id}.png"
        img.save(frame_path)
        minutes = int(candidate.seconds // 60)
        seconds = int(candidate.seconds % 60)
        rows.append(
            {
                **asdict(candidate),
                "source": str(source),
                "path": str(frame_path),
                "timecode": f"{minutes:02d}:{seconds:02d}",
            }
        )
    contact_sheet = out_dir / "catalog_pretty_frames_contact_sheet.png"
    _make_contact_sheet(rows, contact_sheet)
    manifest = {
        "kind": "catalog_pretty_frame_manifest",
        "media_dir": str(media_dir),
        "out_dir": str(out_dir),
        "contact_sheet": str(contact_sheet),
        "frames": rows,
    }
    manifest_path = out_dir / "catalog_pretty_frames_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract approved catalog-worthy frames from YouTube Imports videos.")
    parser.add_argument("--media-dir", type=Path, default=DEFAULT_MEDIA_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    manifest = build_pretty_frames(args.media_dir, args.out_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
