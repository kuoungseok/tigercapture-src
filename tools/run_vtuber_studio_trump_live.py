"""Open the real VTuber Studio window with live Trump -> VRM motion preview."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from capture_review_vtuber_studio import (  # noqa: E402
    DEFAULT_PROGRAM_BACKGROUND,
    DEFAULT_TRUMP_SOURCE,
    DEFAULT_VRM,
    _make_harness_editor,
    _make_mapping_monitor_frame,
    _make_program_output_frame,
    _qpixmap_from_pil,
    _video_frame,
)
from app.vtuber.internal_vrm_fallback import render_internal_vrm_fallback_frame  # noqa: E402
from app.vtuber.openseeface_motion import (  # noqa: E402
    load_openseeface_frame_size_csv,
    load_openseeface_motion_csv,
)
from app.vtuber.source_framing import estimate_upper_body_box_from_face_box  # noqa: E402
from app.vtuber.vrm_motion_mapping import source_pitch_to_vrm_pitch  # noqa: E402
from app.vtuber.vrm_renderer import VRM_RENDERER_GPU  # noqa: E402


DEFAULT_MOTION_CSV = ROOT / "debugCapture" / "vtuber_broadcast_trump_openseeface_crop.csv"
DEFAULT_OUT = ROOT / "debugCapture" / "vtuber_studio_trump_live_status.json"
DEFAULT_SCREENSHOT_OUT = ROOT / "debugCapture" / "vtuber_studio_trump_live_window.png"
DEFAULT_CACHED_SLOTS = ROOT / "debugCapture" / "vrm_local_preflight_slots_pitch_boost.png"
DEFAULT_BUSTUP_CACHE_GLOB = str(ROOT / "debugCapture" / "vtuber_bustup_seq_*.png")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open VTuber Studio with live Trump OpenSeeFace motion.")
    parser.add_argument("--trump-source", default=str(DEFAULT_TRUMP_SOURCE))
    parser.add_argument("--program-background", default=str(DEFAULT_PROGRAM_BACKGROUND))
    parser.add_argument("--vrm", default=str(DEFAULT_VRM))
    parser.add_argument("--motion-csv", default=str(DEFAULT_MOTION_CSV))
    parser.add_argument("--status-out", default=str(DEFAULT_OUT))
    parser.add_argument("--screenshot-out", default=str(DEFAULT_SCREENSHOT_OUT))
    parser.add_argument("--cached-slots", default=str(DEFAULT_CACHED_SLOTS))
    parser.add_argument("--bustup-cache-glob", default=DEFAULT_BUSTUP_CACHE_GLOB)
    parser.add_argument(
        "--frame-source",
        choices=("cached-bustup", "cached-slots", "live-render"),
        default="cached-bustup",
        help="cached-bustup uses real prerendered VRM/MToon RGBA frames. live-render is blocked unless --allow-slow-live-render is set.",
    )
    parser.add_argument(
        "--allow-slow-live-render",
        action="store_true",
        help="Intentionally run the one-shot VRM/MToon export helper for diagnostics; not for live preview.",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=920)
    parser.add_argument("--fps", type=float, default=8.0)
    parser.add_argument("--duration-ms", type=int, default=12_000)
    parser.add_argument("--quit-after-ms", type=int, default=0, help="Close the proof window automatically after this many ms.")
    args = parser.parse_args(argv)

    trump_source = Path(args.trump_source).resolve()
    program_background = Path(args.program_background).resolve()
    vrm_path = Path(args.vrm).resolve()
    motion_csv = Path(args.motion_csv).resolve()
    cached_slots = Path(args.cached_slots).resolve()
    bustup_cache_paths = sorted(Path().glob(str(args.bustup_cache_glob))) if not Path(str(args.bustup_cache_glob)).is_absolute() else sorted(Path(str(args.bustup_cache_glob)).parent.glob(Path(str(args.bustup_cache_glob)).name))
    required = [trump_source, program_background, vrm_path, motion_csv]
    if str(args.frame_source) == "cached-slots":
        required.append(cached_slots)
    if str(args.frame_source) == "cached-bustup" and not bustup_cache_paths:
        required.append(Path(str(args.bustup_cache_glob)))
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing VTuber Studio live preview input(s):\n" + "\n".join(missing))
    if str(args.frame_source) == "live-render" and not bool(args.allow_slow_live_render):
        raise RuntimeError(
            "--frame-source live-render calls the one-shot export helper and is too slow for Studio preview. "
            "Use cached-bustup for local UI proof, or pass --allow-slow-live-render only for a deliberate diagnostic."
        )

    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication
    from app.video_editor_popouts import VTuberBroadcastStudioWindow

    app = QApplication.instance() or QApplication(["tigercapture-vtuber-studio-trump-live"])
    controller = _LiveTrumpStudio(
        trump_source=trump_source,
        program_background=program_background,
        vrm_path=vrm_path,
        motion_csv=motion_csv,
        width=max(980, int(args.width)),
        height=max(700, int(args.height)),
        fps=max(0.25, float(args.fps)),
        duration_ms=max(1_000, int(args.duration_ms)),
        quit_after_ms=max(0, int(args.quit_after_ms)),
        status_out=Path(args.status_out).resolve(),
        screenshot_out=Path(args.screenshot_out).resolve(),
        cached_slots=cached_slots,
        bustup_cache_paths=tuple(path.resolve() for path in bustup_cache_paths),
        frame_source=str(args.frame_source),
    )
    controller.window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    controller.window.destroyed.connect(app.quit)
    controller.start(QTimer)
    return int(app.exec())


class _LiveTrumpStudio:
    def __init__(
        self,
        *,
        trump_source: Path,
        program_background: Path,
        vrm_path: Path,
        motion_csv: Path,
        width: int,
        height: int,
        fps: float,
        duration_ms: int,
        quit_after_ms: int,
        status_out: Path,
        screenshot_out: Path,
        cached_slots: Path,
        bustup_cache_paths: tuple[Path, ...],
        frame_source: str,
    ) -> None:
        from app.video_editor_popouts import VTuberBroadcastStudioWindow

        self.trump_source = trump_source
        self.program_background = program_background
        self.vrm_path = vrm_path
        self.motion_csv = motion_csv
        self.fps = fps
        self.duration_ms = duration_ms
        self.quit_after_ms = quit_after_ms
        self.status_out = status_out
        self.screenshot_out = screenshot_out
        self.cached_slots = cached_slots
        self.frame_source = frame_source
        self.motion_frames = load_openseeface_motion_csv(motion_csv)
        self.source_frame_size = load_openseeface_frame_size_csv(motion_csv) or (640, 360)
        self.last_source_crop: dict[str, Any] = {}
        self.cached_items = (
            _load_bustup_cache_frames(bustup_cache_paths)
            if frame_source == "cached-bustup"
            else _load_cached_slot_frames(cached_slots)
            if frame_source == "cached-slots"
            else []
        )
        self.started = time.monotonic()
        self.frame_index = 0
        self.last_diag: dict[str, Any] = {}
        self.window = VTuberBroadcastStudioWindow(None)
        self.window.setWindowTitle("VTuber Studio - Trump Motion Live Preview")
        self.window.resize(width, height)
        self.window._live_card.hide()
        self.window._evidence_card.hide()
        self.window._program_body.hide()
        self.window._source_body.hide()
        self.window._mapping_body.hide()
        self.window._program_body.setText("Live local Program Output: Trump OpenSeeFace CSV -> internal VRM fallback.")
        self.window._source_body.setText(f"Performance Source\n{self.trump_source}")
        self.window._mapping_body.setText(
            "Avatar: Milica_v1.3.vrm\n"
            "Type: VRM / internal fallback renderer\n"
            f"Motion CSV: {self.motion_csv.name}\n"
            f"Preview source: {self.frame_source}\n"
            "Route: Trump video -> OpenSeeFace CSV -> VRM head/blink/mouth/upper-body pose"
        )

    def start(self, timer_cls) -> None:
        if self.cached_items:
            first_avatar, first_diag = self.cached_items[0]
            first_program, first_placement = _make_cached_program_output_frame(
                self.program_background,
                first_avatar,
                time_ms=0,
                label=f"actual VRM render cache: {first_diag.get('slot_name', 'bust_up')}",
            )
        else:
            first_avatar = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
            first_diag = {"ok": False, "renderer_family": "vtuber_vrm", "render_profile": "vrm_mtoon"}
            first_program, first_placement = _make_program_output_frame(
                self.program_background,
                first_avatar,
                time_ms=0,
            )
        mapping = _make_avatar_mapping_frame(first_avatar, first_diag, vrm_name=self.vrm_path.name)
        editor = _make_harness_editor(
            trump_source=self.trump_source,
            program_background=self.program_background,
            vrm_path=self.vrm_path,
            program_pixmap=_qpixmap_from_pil(first_program),
            position_ms=0,
        )
        mapping_pixmap = _qpixmap_from_pil(mapping)
        editor._avatar_mapping_pixmap = mapping_pixmap
        editor._latest_avatar_mapping_pixmap = mapping_pixmap
        try:
            editor._project_settings["vseeface_bridge"]["motion_csv"] = str(self.motion_csv)
            editor._project_settings["vseeface_bridge"]["openseeface_csv"] = str(self.motion_csv)
        except Exception:
            pass
        self.window.update_from_editor(editor)
        self.window._set_preview_pixmap(self.window._program_preview, _qpixmap_from_pil(first_program), "Program Output preview unavailable")
        self.window._set_preview_pixmap(
            self.window._source_preview,
            _qpixmap_from_pil(self._make_source_tracking_frame(0)),
            "No Source Tracking frame",
        )
        self.window._set_preview_pixmap(self.window._mapping_preview, mapping_pixmap, "No Avatar Mapping preview")
        self._write_status(first_diag, placement=first_placement, state="started")
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

        self.timer = timer_cls(self.window)
        self.timer.timeout.connect(self._tick)
        self.timer.start(max(40, int(round(1000.0 / self.fps))))
        timer_cls.singleShot(50, self._tick)
        if self.quit_after_ms > 0:
            timer_cls.singleShot(self.quit_after_ms, self.window.close)

    def _tick(self) -> None:
        elapsed_ms = int((time.monotonic() - self.started) * 1000.0)
        time_ms = elapsed_ms % self.duration_ms
        if self.cached_items:
            index = self.frame_index % len(self.cached_items)
            avatar, diag = self.cached_items[index]
            program, placement = _make_cached_program_output_frame(
                self.program_background,
                avatar,
                time_ms=time_ms,
                label=f"actual VRM render cache: {diag.get('slot_name', 'bust_up')}",
            )
        else:
            avatar, diag = self._render_avatar(time_ms)
            program, placement = _make_program_output_frame(
                self.program_background,
                avatar,
                time_ms=time_ms,
            )
        self.window.update_program_output_frame(_qpixmap_from_pil(program))
        self.window._set_preview_pixmap(
            self.window._source_preview,
            _qpixmap_from_pil(self._make_source_tracking_frame(time_ms)),
            "No Source Tracking frame",
        )
        self.window._set_preview_pixmap(
            self.window._mapping_preview,
            _qpixmap_from_pil(_make_avatar_mapping_frame(avatar, diag, vrm_name=self.vrm_path.name)),
            "No Avatar Mapping preview",
        )
        self.window._mapping_body.setText(
            "Avatar: Milica_v1.3.vrm\n"
            "Type: VRM / internal fallback renderer\n"
            f"Preview source: {self.frame_source}\n"
            f"Motion: yaw {diag.get('selected_motion', {}).get('yaw_deg', 0.0):.1f}, "
            f"pitch {diag.get('selected_motion', {}).get('pitch_deg', 0.0):.1f}, "
            f"blink {max(float(diag.get('selected_motion', {}).get('blink_l', 0.0) or 0.0), float(diag.get('selected_motion', {}).get('blink_r', 0.0) or 0.0)):.2f}, "
            f"mouth {float(diag.get('selected_motion', {}).get('mouth_open', 0.0) or 0.0):.2f}\n"
            "Route: Trump video -> OpenSeeFace CSV -> VRM head/blink/mouth/upper-body pose"
        )
        self.frame_index += 1
        if self.frame_index % max(1, int(round(self.fps))) == 0:
            self._write_status(diag, placement=placement, state="running")

    def _make_source_tracking_frame(self, time_ms: int) -> Image.Image:
        frame = _video_frame(self.trump_source, time_ms=int(time_ms)).convert("RGB")
        motion = _closest_motion_frame(self.motion_frames, int(time_ms))
        box = getattr(motion, "face_box", None) if motion is not None else None
        if box:
            subject_box = estimate_upper_body_box_from_face_box(self.source_frame_size, box, preset="bust_up")
            crop_box_source, crop_diag = _expand_box_to_aspect(
                subject_box,
                self.source_frame_size,
                target_aspect=16.0 / 9.0,
            )
            crop_box = _scale_box(crop_box_source, self.source_frame_size, frame.size)
            frame = frame.crop(crop_box)
            self.last_source_crop = {
                **crop_diag,
                "subject_box": [int(v) for v in subject_box],
                "source_crop_box": [int(v) for v in crop_box_source],
                "face_box": [int(v) for v in box],
                "face_fully_visible": _box_contains_xywh(crop_box_source, box),
            }
        else:
            self.last_source_crop = {
                "source_crop_box": [0, 0, int(self.source_frame_size[0]), int(self.source_frame_size[1])],
                "crop_aspect": round(float(self.source_frame_size[0]) / float(max(1, self.source_frame_size[1])), 4),
                "face_fully_visible": False,
            }
        return frame.resize((1280, 720), Image.Resampling.LANCZOS).convert("RGBA")

    def _render_avatar(self, time_ms: int) -> tuple[Image.Image, dict[str, Any]]:
        started = time.perf_counter()
        frame, diag = render_internal_vrm_fallback_frame(
            {
                "id": "internal_vrm_fallback",
                "settings": {
                    "avatar_vrm": str(self.vrm_path),
                    "motion_csv": str(self.motion_csv),
                    "openseeface_csv": str(self.motion_csv),
                    "upper_body_mode": "seated",
                    "program_output": True,
                    "contact_preview_triangle_cap": 12000,
                    "texture_max_size": 512,
                    "enable_shadow_map": False,
                    "gpu_warmup_frames": 8,
                    "reuse_gpu_widget": True,
                },
            },
            time_ms=int(time_ms),
            width=1280,
            height=720,
            renderer=VRM_RENDERER_GPU,
        )
        diag = dict(diag)
        diag["render_elapsed_s"] = round(time.perf_counter() - started, 4)
        self.last_diag = dict(diag)
        return frame.convert("RGBA"), dict(diag)

    def _write_status(self, diag: dict[str, Any], *, placement: dict[str, Any] | None = None, state: str) -> None:
        self.status_out.parent.mkdir(parents=True, exist_ok=True)
        placement = dict(placement or {})
        selected_motion = diag.get("selected_motion") if isinstance(diag.get("selected_motion"), dict) else {}
        source_pitch = float(selected_motion.get("pitch_deg") or 0.0)
        render_rows = (diag.get("render") or {}).get("rows") if isinstance(diag.get("render"), dict) else []
        render_row = render_rows[0] if isinstance(render_rows, list) and render_rows and isinstance(render_rows[0], dict) else {}
        payload = {
            "schema": "tigercapture.vtuber_studio_trump_live.v1",
            "state": state,
            "frame_index": int(self.frame_index),
            "window": self.window.windowTitle(),
            "frame_source": self.frame_source,
            "trump_source": str(self.trump_source),
            "program_background": str(self.program_background),
            "vrm": str(self.vrm_path),
            "motion_csv": str(self.motion_csv),
            "visual_contract": {
                "source_tracking_fit": "openseeface_face_box_to_bust_up_cover_16x9",
                "program_output_fit": "broadcast_16x9_cover_background_plus_bust_up_vrm",
                "source_visibility_policy": "chest_or_bust_source_maps_to_vrm_bust_up",
                "program_avatar_height_ratio": placement.get("program_avatar_height_ratio") or _fit_height_ratio(diag.get("fit")),
                "program_avatar_bottom_gap_ratio": placement.get("program_avatar_bottom_gap_ratio"),
                "program_avatar_grounded": bool(placement.get("program_avatar_grounded")),
                "program_avatar_box": placement.get("program_avatar_box"),
                "source_tracking_crop": self.last_source_crop,
                "live_renderer_currently_too_slow": self.frame_source != "live-render"
                or _render_elapsed_s(diag) > (1.0 / max(0.1, float(self.fps))),
                "actual_renderer_elapsed_s": _render_elapsed_s(diag),
                "live_preview_triangle_cap": diag.get("live_preview_triangle_cap"),
                "render_timings": render_row.get("timings") if isinstance(render_row.get("timings"), dict) else {},
            },
            "render_ok": bool(diag.get("ok")),
            "renderer": diag.get("renderer"),
            "selected_motion_time_ms": diag.get("selected_motion_time_ms"),
            "selected_motion": selected_motion,
            "mapped_vrm_motion": {
                "pitch_deg": round(source_pitch_to_vrm_pitch(source_pitch), 4),
                "source_pitch_deg": round(source_pitch, 4),
                "mapping": "vrm_pitch = -source_pitch + rest_bias",
            },
            "errors": diag.get("errors") or [],
            "warnings": diag.get("warnings") or [],
        }
        self.status_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.screenshot_out.parent.mkdir(parents=True, exist_ok=True)
        self.window.grab().save(str(self.screenshot_out))
        proof_paths = {
            "window": self.screenshot_out,
            "program_output": self.screenshot_out.with_name(f"{self.screenshot_out.stem}_program_output.png"),
            "source_tracking": self.screenshot_out.with_name(f"{self.screenshot_out.stem}_source_tracking.png"),
            "avatar_mapping": self.screenshot_out.with_name(f"{self.screenshot_out.stem}_avatar_mapping.png"),
        }
        self.window._program_preview.grab().save(str(proof_paths["program_output"]))
        self.window._source_preview.grab().save(str(proof_paths["source_tracking"]))
        self.window._mapping_preview.grab().save(str(proof_paths["avatar_mapping"]))
        payload["proof_paths"] = {key: str(path) for key, path in proof_paths.items()}
        self.status_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_bustup_cache_frames(paths: tuple[Path, ...]) -> list[tuple[Image.Image, dict[str, Any]]]:
    report_path = ROOT / "debugCapture" / "vtuber_bustup_seq_report.json"
    reports: dict[int, dict[str, Any]] = {}
    if report_path.is_file():
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            for row in data.get("frames") or []:
                if isinstance(row, dict):
                    reports[int(row.get("i", len(reports)))] = row
        except Exception:
            reports = {}
    items: list[tuple[Image.Image, dict[str, Any]]] = []
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGBA")
        row = reports.get(index, {})
        motion = row.get("selected_motion") if isinstance(row.get("selected_motion"), dict) else {}
        diag = {
            "ok": True,
            "slot_name": f"bust_up_{index}",
            "renderer": "vrm_mtoon_gpu_prerender_cache",
            "renderer_family": "vtuber_vrm",
            "render_profile": "vrm_mtoon",
            "selected_motion_time_ms": row.get("time_ms"),
            "selected_motion": motion,
            "render_elapsed_s": row.get("elapsed_s"),
            "fit": row.get("fit") if isinstance(row.get("fit"), dict) else {},
            "errors": row.get("errors") or [],
            "warnings": ["actual_vrm_mtoon_gpu_prerender_cache_used_until_renderer_worker_is_fast_enough"],
        }
        items.append((image, diag))
    return items


def _load_cached_slot_frames(path: Path) -> list[tuple[Image.Image, dict[str, Any]]]:
    sheet = Image.open(path).convert("RGBA")
    sidecar = path.with_suffix(".json")
    slot_count = 5
    if sidecar.is_file():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            slots = data.get("slots") if isinstance(data, dict) else None
            if isinstance(slots, list) and slots:
                slot_count = max(1, int(len(slots)))
        except Exception:
            slot_count = 5
    panel_w = max(1, sheet.width // slot_count)
    frames: list[tuple[Image.Image, dict[str, Any]]] = []
    for index in range(slot_count):
        left = index * panel_w
        right = sheet.width if index == slot_count - 1 else min(sheet.width, left + panel_w)
        # Crop the actual VRM viewport area instead of the report header/footer.
        crop = sheet.crop((max(0, left + 120), 340, min(sheet.width, right - 120), min(sheet.height, 664)))
        frames.append((crop.convert("RGBA"), _cached_slot_diag(index)))
    return frames


def _cached_slot_diag(index: int) -> dict[str, Any]:
    slots = [
        ("neutral", 2.6, 1.3, 0.0, 0.0, 0.21),
        ("yaw", -14.2, 4.8, 0.0, 0.14, 0.22),
        ("pitch", -3.3, 6.0, 0.0, 0.30, 0.23),
        ("blink", 1.0, 1.3, 1.0, 0.47, 0.23),
        ("mouth", 6.0, -0.9, 0.0, 0.0, 0.24),
    ]
    name, yaw, pitch, blink_l, blink_r, mouth = slots[index % len(slots)]
    return {
        "ok": True,
        "slot_name": name,
        "renderer": "vrm_mtoon_gpu_cached_slot",
        "renderer_family": "vtuber_vrm",
        "render_profile": "vrm_mtoon",
        "selected_motion_time_ms": None,
        "selected_motion": {
            "yaw_deg": yaw,
            "pitch_deg": pitch,
            "roll_deg": 0.0,
            "blink_l": blink_l,
            "blink_r": blink_r,
            "mouth_open": mouth,
        },
        "errors": [],
        "warnings": ["cached_slot_preview_used_to_keep_real_qt_studio_responsive"],
    }


def _make_cached_program_output_frame(
    background_video: Path,
    slot_frame: Image.Image,
    *,
    time_ms: int,
    label: str,
) -> tuple[Image.Image, dict[str, Any]]:
    source_bg = _video_frame(background_video, time_ms=time_ms).convert("RGB")
    bg = ImageOps.fit(source_bg, (1280, 720), method=Image.Resampling.LANCZOS).convert("RGBA")
    avatar = _trim_alpha(slot_frame.convert("RGBA"), padding=0)
    target_h = int(bg.height * 0.96)
    scale = target_h / max(1, avatar.height)
    target_w = max(1, int(round(avatar.width * scale)))
    avatar = avatar.resize((target_w, target_h), Image.Resampling.LANCZOS)
    x = int(bg.width * 0.70 - avatar.width * 0.5)
    y = bg.height - avatar.height
    shadow = Image.new("RGBA", (avatar.width + 24, avatar.height + 24), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow, "RGBA")
    shadow_draw.ellipse((avatar.width * 0.18, avatar.height - 52, avatar.width * 0.82, avatar.height - 8), fill=(0, 0, 0, 110))
    bg.alpha_composite(shadow, (x - 12, y - 12))
    bg.alpha_composite(avatar, (x, y))
    draw = ImageDraw.Draw(bg, "RGBA")
    draw.rounded_rectangle((28, 26, 460, 78), radius=12, fill=(7, 10, 17, 210), outline=(114, 214, 180, 180))
    draw.text((46, 42), f"VTuber Studio Program Output | {label}", fill=(238, 240, 248, 255))
    placement = {
        "program_avatar_box": [int(x), int(y), int(x + avatar.width), int(y + avatar.height)],
        "program_avatar_size": [int(avatar.width), int(avatar.height)],
        "program_avatar_height_ratio": round(float(avatar.height) / float(bg.height), 4),
        "program_avatar_bottom_gap_px": 0,
        "program_avatar_bottom_gap_ratio": 0.0,
        "program_avatar_grounded": True,
        "program_avatar_trimmed_before_fit": True,
        "program_avatar_fit_rule": "trim_alpha_then_fill_height_bottom_anchor",
    }
    return bg, placement


def _make_avatar_mapping_frame(avatar_rgba: Image.Image, diag: dict[str, Any], *, vrm_name: str) -> Image.Image:
    width, height = 1280, 720
    canvas = Image.new("RGBA", (width, height), (7, 10, 17, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=28, fill=(15, 21, 34, 255), outline=(48, 60, 96, 255), width=2)
    draw.text((52, 44), "Avatar Mapping | actual VRM/MToon frame", fill=(238, 240, 248, 255))
    draw.text((52, 74), f"{vrm_name}  |  {diag.get('renderer') or 'vrm_mtoon_gpu'}", fill=(144, 190, 255, 255))
    for x in range(100, 760, 80):
        draw.line((x, 126, x, 668), fill=(28, 40, 62, 160), width=1)
    for y in range(150, 650, 80):
        draw.line((68, y, 796, y), fill=(28, 40, 62, 160), width=1)
    avatar = _trim_alpha(avatar_rgba.convert("RGBA"), padding=0)
    target_h = int(height * 0.86)
    scale = target_h / max(1, avatar.height)
    target_w = max(1, int(round(avatar.width * scale)))
    avatar = avatar.resize((target_w, target_h), Image.Resampling.LANCZOS)
    ax = int(420 - avatar.width * 0.5)
    ay = height - 44 - avatar.height
    canvas.alpha_composite(avatar, (ax, ay))

    motion = diag.get("selected_motion") if isinstance(diag.get("selected_motion"), dict) else {}
    source_pitch = float(motion.get("pitch_deg") or 0.0)
    vrm_pitch = source_pitch_to_vrm_pitch(source_pitch)
    rows = [
        ("Route", "Trump video -> OpenSeeFace -> VRM pose"),
        ("Yaw", f"{float(motion.get('yaw_deg') or 0.0):.1f} deg"),
        ("Source Pitch", f"{source_pitch:.1f} deg"),
        ("VRM Pitch", f"{vrm_pitch:.1f} deg"),
        ("Blink", f"{max(float(motion.get('blink_l') or 0.0), float(motion.get('blink_r') or 0.0)):.2f}"),
        ("Mouth", f"{float(motion.get('mouth_open') or 0.0):.2f}"),
        ("Preview", "live VRM/MToon GPU diagnostics"),
    ]
    x0, y0 = 830, 160
    draw.rounded_rectangle((790, 122, 1218, 626), radius=20, fill=(8, 12, 20, 235), outline=(40, 52, 80, 255), width=1)
    for key, value in rows:
        draw.text((x0, y0), key, fill=(124, 135, 158, 255))
        draw.text((x0 + 126, y0), value, fill=(232, 236, 248, 255))
        y0 += 58
    return canvas


def _trim_alpha(image: Image.Image, *, padding: int = 0) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
    if not bbox:
        return image
    left, top, right, bottom = bbox
    if padding:
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(image.width, right + padding)
        bottom = min(image.height, bottom + padding)
    return image.crop((left, top, right, bottom))


def _closest_motion_frame(frames: tuple[Any, ...], time_ms: int) -> Any | None:
    if not frames:
        return None
    return min(frames, key=lambda frame: abs(int(getattr(frame, "time_ms", 0)) - int(time_ms)))


def _scale_box(
    box: tuple[int, int, int, int],
    source_size: tuple[int, int],
    target_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    sx = target_size[0] / max(1, source_size[0])
    sy = target_size[1] / max(1, source_size[1])
    x, y, w, h = box
    left = max(0, int(round(x * sx)))
    top = max(0, int(round(y * sy)))
    right = min(target_size[0], int(round((x + w) * sx)))
    bottom = min(target_size[1], int(round((y + h) * sy)))
    if right <= left or bottom <= top:
        return (0, 0, target_size[0], target_size[1])
    return (left, top, right, bottom)


def _expand_box_to_aspect(
    box: tuple[int, int, int, int],
    frame_size: tuple[int, int],
    *,
    target_aspect: float,
) -> tuple[tuple[int, int, int, int], dict[str, Any]]:
    frame_w = max(1, int(frame_size[0]))
    frame_h = max(1, int(frame_size[1]))
    x, y, w, h = [float(v) for v in box]
    w = max(1.0, min(float(frame_w), w))
    h = max(1.0, min(float(frame_h), h))
    cx = min(max(x + w * 0.5, 0.0), float(frame_w))
    cy = min(max(y + h * 0.5, 0.0), float(frame_h))
    target_aspect = max(0.1, float(target_aspect))
    current_aspect = w / h
    if current_aspect < target_aspect:
        crop_w = h * target_aspect
        crop_h = h
    else:
        crop_w = w
        crop_h = w / target_aspect
    if crop_w > frame_w:
        crop_w = float(frame_w)
        crop_h = crop_w / target_aspect
    if crop_h > frame_h:
        crop_h = float(frame_h)
        crop_w = crop_h * target_aspect
    crop_w = min(float(frame_w), max(1.0, crop_w))
    crop_h = min(float(frame_h), max(1.0, crop_h))
    left = min(max(cx - crop_w * 0.5, 0.0), float(frame_w) - crop_w)
    top = min(max(cy - crop_h * 0.5, 0.0), float(frame_h) - crop_h)
    crop = (
        int(round(left)),
        int(round(top)),
        max(1, int(round(crop_w))),
        max(1, int(round(crop_h))),
    )
    # Keep the rounded crop inside the source frame.
    crop = (
        min(max(0, crop[0]), frame_w - 1),
        min(max(0, crop[1]), frame_h - 1),
        min(crop[2], frame_w - min(max(0, crop[0]), frame_w - 1)),
        min(crop[3], frame_h - min(max(0, crop[1]), frame_h - 1)),
    )
    diag = {
        "crop_aspect": round(float(crop[2]) / float(max(1, crop[3])), 4),
        "target_aspect": round(target_aspect, 4),
        "single_crop_then_resize": True,
        "clamped_to_source": bool(
            crop[0] <= 0
            or crop[1] <= 0
            or crop[0] + crop[2] >= frame_w
            or crop[1] + crop[3] >= frame_h
        ),
    }
    return crop, diag


def _box_contains_xywh(outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]) -> bool:
    ox, oy, ow, oh = [int(v) for v in outer]
    ix, iy, iw, ih = [int(v) for v in inner]
    return ix >= ox and iy >= oy and ix + iw <= ox + ow and iy + ih <= oy + oh


def _fit_height_ratio(fit: Any) -> float | None:
    if not isinstance(fit, dict):
        return None
    size = fit.get("output_size")
    if not isinstance(size, (list, tuple)) or len(size) < 2:
        return None
    try:
        return round(float(size[1]) / 720.0, 4)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _render_elapsed_s(diag: dict[str, Any]) -> float:
    try:
        return float(diag.get("render_elapsed_s") or 0.0)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
