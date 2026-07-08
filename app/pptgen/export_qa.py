"""Export QA runner for the user PPT generator."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.pptgen.actor_posters import ensure_deck_actor_posters
from app.pptgen.pdf_export import export_deck_pdf
from app.pptgen.preview import render_contact_sheet, render_deck_pngs
from app.pptgen.sample import create_sample_deck
from app.pptgen.validation import validation_report
from app.pptgen.video_export import export_deck_video
from app.pptgen.writer_python_pptx import write_pptx_compatible


def run_ppt_export_qa(
    output_dir: str | Path,
    *,
    export_pdf: bool = True,
    require_pdf: bool = False,
    pdf_backend: str = "auto",
    export_video: bool = True,
    video_fps: int = 12,
    width: int = 1280,
    height: int = 720,
) -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    deck = create_sample_deck()
    posters = ensure_deck_actor_posters(deck, output_dir=out_dir / "actor_posters")
    validation = validation_report(deck)

    pptx = write_pptx_compatible(deck, out_dir / "ppt_export_qa.pptx")
    slide_pngs = render_deck_pngs(deck, out_dir / "slides")
    contact_sheet = render_contact_sheet(deck, out_dir / "contact_sheet.png")

    pdf_result: dict[str, Any] = {"requested": bool(export_pdf), "ok": False, "skipped": not bool(export_pdf)}
    if export_pdf:
        pdf_result = export_deck_pdf(deck, out_dir / "ppt_export_qa.pdf", backend=pdf_backend, pptx_path=pptx)
        pdf_result["requested"] = True

    video_result: dict[str, Any] = {"requested": bool(export_video), "ok": False, "skipped": not bool(export_video)}
    if export_video:
        video_result = export_deck_video(
            deck,
            out_dir / "ppt_export_qa.mp4",
            fps=max(1, int(video_fps or 12)),
            size=(max(16, int(width or 1280)), max(16, int(height or 720))),
        )
        video_result["requested"] = True

    checks = {
        "pptx_exists": pptx.is_file(),
        "slide_png_count": len(slide_pngs),
        "contact_sheet_exists": contact_sheet.is_file(),
        "validation_ok": bool(validation.get("ok")),
        "video_ok": (not export_video) or bool(video_result.get("ok")),
        "pdf_ok": (not export_pdf) or bool(pdf_result.get("ok")) or not bool(require_pdf),
    }
    ok = all(bool(value) for value in checks.values())
    manifest = {
        "schema": "tigercapture.ppt.export_qa.v1",
        "ok": ok,
        "output_dir": str(out_dir),
        "deck_title": deck.title,
        "slide_count": len(deck.slides),
        "posters": posters,
        "validation": validation,
        "artifacts": {
            "pptx": str(pptx),
            "slides_dir": str(out_dir / "slides"),
            "contact_sheet": str(contact_sheet),
            "pdf": str(pdf_result.get("output_pdf") or out_dir / "ppt_export_qa.pdf"),
            "video": str(video_result.get("output_path") or out_dir / "ppt_export_qa.mp4"),
        },
        "pdf": pdf_result,
        "video": video_result,
        "checks": checks,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


__all__ = ["run_ppt_export_qa"]
