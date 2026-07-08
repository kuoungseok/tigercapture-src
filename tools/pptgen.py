from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pptgen.preview import render_contact_sheet, render_deck_pngs
from app.pptgen.pdf_export import export_deck_pdf
from app.pptgen.sample import create_sample_deck
from app.pptgen.video_export import export_deck_video
from app.pptgen.writer_python_pptx import write_pptx_compatible


def _export_sample(
    output_dir: Path,
    *,
    export_pdf: bool = False,
    pdf_backend: str = "auto",
    export_video: bool = False,
    video_fps: int = 12,
    video_size: tuple[int, int] = (1280, 720),
    video_audio: str = "",
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    deck = create_sample_deck()
    pptx = write_pptx_compatible(deck, output_dir / "pptgen_sample.pptx")
    pngs = render_deck_pngs(deck, output_dir / "slides")
    sheet = render_contact_sheet(deck, output_dir / "contact_sheet.png")
    result = {"pptx": str(pptx), "slides": str(len(pngs)), "contact_sheet": str(sheet)}
    if export_pdf:
        pdf = export_deck_pdf(deck, output_dir / "pptgen_sample.pdf", backend=pdf_backend, pptx_path=pptx)
        result["pdf"] = str(pdf.get("output_pdf") or "")
        result["pdf_ok"] = str(bool(pdf.get("ok")))
        result["pdf_backend"] = str(pdf.get("backend") or "")
        if not pdf.get("ok"):
            result["pdf_error"] = str(pdf.get("reason") or "PDF export failed")
    if export_video:
        video = export_deck_video(
            deck,
            output_dir / "pptgen_sample.mp4",
            fps=video_fps,
            size=video_size,
            audio_path=video_audio or None,
        )
        result["video"] = str(video.get("output_path") or "")
        result["video_ok"] = str(bool(video.get("ok")))
        result["video_frames"] = str(video.get("frames_written") or 0)
        result["video_transitions"] = str(video.get("transition_count") or 0)
        result["video_audio_muxed"] = str(bool(video.get("audio_muxed")))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch or export the TigerCapture PPT generator.")
    parser.add_argument("--export-sample", action="store_true", help="Export sample PPTX/PNGs without opening the UI.")
    parser.add_argument("--export-pdf", action="store_true", help="Also export a sample PDF when using --export-sample.")
    parser.add_argument("--export-video", action="store_true", help="Also export a sample MP4 presentation video when using --export-sample.")
    parser.add_argument("--pdf-backend", default="auto", choices=("auto", "libreoffice", "powerpoint", "powerpoint_com"), help="PDF backend for --export-pdf.")
    parser.add_argument("--video-fps", type=int, default=12, help="FPS for --export-video sample export.")
    parser.add_argument("--video-width", type=int, default=1280, help="Video width for --export-video sample export.")
    parser.add_argument("--video-height", type=int, default=720, help="Video height for --export-video sample export.")
    parser.add_argument("--video-audio", default="", help="Optional audio file to mux into --export-video output.")
    parser.add_argument("--out-dir", default="debugCapture/pptgen", help="Output directory for --export-sample.")
    args = parser.parse_args()
    if args.export_sample:
        result = _export_sample(
            Path(args.out_dir),
            export_pdf=bool(args.export_pdf),
            pdf_backend=args.pdf_backend,
            export_video=bool(args.export_video),
            video_fps=int(args.video_fps or 12),
            video_size=(int(args.video_width or 1280), int(args.video_height or 720)),
            video_audio=str(args.video_audio or ""),
        )
        print(result)
        return 0 if result.get("pdf_ok", "True") != "False" and result.get("video_ok", "True") != "False" else 2

    from PySide6.QtWidgets import QApplication
    from app.pptgen.ui.window import PptGeneratorWindow

    app = QApplication.instance() or QApplication(sys.argv)
    window = PptGeneratorWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
