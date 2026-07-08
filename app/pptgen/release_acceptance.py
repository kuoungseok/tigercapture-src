"""Release-acceptance QA for the user PPT generator.

This module intentionally stays Qt-free except for the editor workflow drag
simulation section, which uses the real ``SlideCanvas`` MIME ingestion path in
offscreen mode.
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops, ImageStat

from app.pptgen.actor_posters import ensure_deck_actor_posters
from app.pptgen.animations import animation_is_active
from app.pptgen.autosave import list_ppt_recovery_candidates, save_ppt_autosave
from app.pptgen.assets import add_deck_asset, insert_deck_asset_to_slide, list_deck_assets
from app.pptgen.history import PptHistoryStack, deck_from_history_snapshot
from app.pptgen.pdf_export import export_pptx_to_pdf
from app.pptgen.preview import render_deck_pngs, render_slide_image
from app.pptgen.product_readiness import _write_demo_image, build_product_readiness_decks
from app.pptgen.project_io import load_deck_project, save_deck_project
from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec
from app.pptgen.validation import validation_report
from app.pptgen.video_export import export_deck_video
from app.pptgen.writer_python_pptx import write_pptx_compatible


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def _count_expected(deck: DeckSpec, kind: str) -> int:
    return sum(1 for slide in deck.slides for element in slide.elements if element.kind == kind)


def inspect_pptx_package(pptx: str | Path, deck: DeckSpec) -> dict[str, Any]:
    target = Path(pptx)
    checks: dict[str, bool] = {
        "pptx_exists": target.is_file() and target.stat().st_size > 0,
        "zip_opened": False,
        "content_types": False,
        "presentation_xml": False,
        "slide_count_match": False,
        "rels_present": False,
        "chart_count_ok": False,
        "timing_xml_ok": False,
    }
    details: dict[str, Any] = {
        "path": str(target),
        "expected_slide_count": len(deck.slides),
        "expected_chart_count": _count_expected(deck, "chart"),
        "expected_animation_count": sum(
            1 for slide in deck.slides for element in slide.elements if animation_is_active(element.animation)
        ),
    }
    if not checks["pptx_exists"]:
        return {"schema": "tigercapture.ppt.pptx_static_inspection.v1", "ok": False, "checks": checks, "details": details}
    try:
        with zipfile.ZipFile(target, "r") as archive:
            names = set(archive.namelist())
            checks["zip_opened"] = True
            checks["content_types"] = "[Content_Types].xml" in names
            checks["presentation_xml"] = "ppt/presentation.xml" in names
            slide_names = sorted(
                name
                for name in names
                if name.startswith("ppt/slides/slide") and name.endswith(".xml") and "/_rels/" not in name
            )
            rel_names = [name for name in names if name.startswith("ppt/slides/_rels/slide") and name.endswith(".xml.rels")]
            chart_names = [name for name in names if name.startswith("ppt/charts/chart") and name.endswith(".xml")]
            slide_xml = [archive.read(name) for name in slide_names]
            checks["slide_count_match"] = len(slide_names) == len(deck.slides)
            checks["rels_present"] = len(rel_names) >= len(slide_names)
            checks["chart_count_ok"] = len(chart_names) >= int(details["expected_chart_count"])
            has_timing = any(b"<p:timing" in xml or b"<p:tnLst" in xml for xml in slide_xml)
            checks["timing_xml_ok"] = bool(has_timing) if int(details["expected_animation_count"]) else True
            details.update(
                {
                    "slide_xml_count": len(slide_names),
                    "slide_rels_count": len(rel_names),
                    "chart_part_count": len(chart_names),
                    "media_part_count": len([name for name in names if name.startswith("ppt/media/")]),
                    "has_timing_xml": has_timing,
                }
            )
            if checks["presentation_xml"]:
                root = ET.fromstring(archive.read("ppt/presentation.xml"))
                details["presentation_root"] = root.tag
    except Exception as exc:
        details["reason"] = str(exc)
    return {
        "schema": "tigercapture.ppt.pptx_static_inspection.v1",
        "ok": all(checks.values()),
        "checks": checks,
        "details": details,
    }


def run_office_compatibility_qa(
    output_dir: str | Path,
    *,
    host_backend: str = "auto",
    host_timeout_sec: int = 45,
    require_host: bool = False,
) -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for name, deck in build_product_readiness_decks(out_dir / "assets"):
        ensure_deck_actor_posters(deck, output_dir=out_dir / name / "actor_posters")
        pptx = write_pptx_compatible(deck, out_dir / name / f"{name}.pptx")
        static = inspect_pptx_package(pptx, deck)
        rows.append({"name": name, "pptx": str(pptx), "static": static, "ok": bool(static.get("ok"))})

    representative = rows[0] if rows else {}
    host_pdf = out_dir / "host_open_check.pdf"
    host_result: dict[str, Any] = {
        "requested_backend": host_backend,
        "required": bool(require_host),
        "ok": False,
        "status": "skipped",
        "reason": "no PPTX generated",
    }
    if representative.get("pptx"):
        host_result = export_pptx_to_pdf(representative["pptx"], host_pdf, backend=host_backend, timeout_sec=host_timeout_sec)
        host_result["required"] = bool(require_host)
        if not host_result.get("ok") and not require_host:
            host_result["status"] = "optional_failed"

    keynote = {
        "host": "keynote",
        "ok": False,
        "status": "skipped",
        "reason": "Keynote validation is macOS-only" if sys.platform != "darwin" else "Keynote automation not wired",
        "required": False,
    }
    checks = {
        "static_ok": all(bool(row.get("static", {}).get("ok")) for row in rows),
        "scenario_count": len(rows),
        "host_ok": bool(host_result.get("ok")) or not bool(require_host),
        "keynote_skipped": keynote["status"] == "skipped",
    }
    return {
        "schema": "tigercapture.ppt.office_compatibility_qa.v1",
        "ok": checks["static_ok"] and checks["scenario_count"] >= 5 and checks["host_ok"],
        "checks": checks,
        "host_result": host_result,
        "keynote": keynote,
        "scenarios": rows,
    }


def run_editor_workflow_qa(output_dir: str | Path) -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtWidgets import QApplication

    from app.pptgen.drag_payloads import PPT_TIMELINE_CLIP_MIME, PPT_TYPOGRAPHY_MIME, set_json_payload
    from app.pptgen.ui.window import SlideCanvas

    app = QApplication.instance() or QApplication([])
    assert app is not None

    image = _write_demo_image(out_dir / "workflow_image.png", label="Workflow")
    gltf = out_dir / "workflow_object.gltf"
    gltf.write_text('{"asset":{"version":"2.0"},"scenes":[{"nodes":[]}],"scene":0}', encoding="utf-8")
    clip = out_dir / "workflow_clip.mp4"
    clip_deck = DeckSpec(id="workflow-clip-source", title="Workflow Clip Source")
    clip_slide = SlideSpec(id="slide-001", title="Clip Source", duration_ms=1000, transition="cut")
    clip_slide.add_element(SlideElement.text_box("title", "Clip", x=0.20, y=0.35, w=0.60, h=0.16, font_size=32, bold=True))
    clip_deck.slides.append(clip_slide)
    export_deck_video(clip_deck, clip, fps=1, size=(160, 90))

    deck = DeckSpec(id="workflow-qa", title="Editor Workflow QA")
    slide = SlideSpec(id="slide-001", title="Canvas Drop QA")
    deck.slides.append(slide)
    canvas = SlideCanvas()
    canvas.resize(800, 450)
    canvas.set_slide(deck, slide)

    timeline_mime = QMimeData()
    set_json_payload(
        timeline_mime,
        PPT_TIMELINE_CLIP_MIME,
        {
            "schema": "tigercapture.ppt.timeline_clip_drag.v1",
            "track_id": 1,
            "clip_id": 10,
            "source_path": str(clip),
            "timeline_in_ms": 500,
            "duration_ms": 2500,
            "source_in_ms": 0,
            "source_out_ms": 2500,
        },
    )
    timeline_created = canvas._add_elements_from_mime(timeline_mime, 260, 190)

    typo_mime = QMimeData()
    set_json_payload(
        typo_mime,
        PPT_TYPOGRAPHY_MIME,
        {
            "schema": "tigercapture.ppt.typography_drag.v1",
            "text": "Dragged Typography",
            "duration_ms": 1800,
            "style": {"font_size": 42, "color": "#2F6FED", "alignment": "center"},
        },
    )
    typo_created = canvas._add_elements_from_mime(typo_mime, 420, 220)

    url_mime = QMimeData()
    url_mime.setUrls([QUrl.fromLocalFile(str(image)), QUrl.fromLocalFile(str(gltf))])
    file_created = canvas._add_elements_from_mime(url_mime, 340, 260)

    ensure_deck_actor_posters(deck, output_dir=out_dir / "actor_posters")
    project = save_deck_project(deck, out_dir / "workflow.tgppt")
    reloaded = load_deck_project(project)
    pptx = write_pptx_compatible(reloaded, out_dir / "workflow.pptx")
    validation = validation_report(reloaded)
    render_deck_pngs(reloaded, out_dir / "slides", size=(640, 360))

    kinds = [element.kind for element in reloaded.slides[0].elements]
    checks = {
        "timeline_drop": len(timeline_created) == 1 and timeline_created[0].kind == "video_actor",
        "typography_drop": len(typo_created) == 1 and typo_created[0].kind == "typography_actor",
        "file_drop_count": len(file_created) == 2,
        "image_drop": "image" in kinds,
        "ar_pbr_drop": "ar_pbr_actor" in kinds,
        "assets_registered": len(list_deck_assets(reloaded)) >= 2,
        "project_roundtrip": len(reloaded.slides[0].elements) == len(slide.elements),
        "validation_ok": bool(validation.get("ok")),
        "pptx_exists": pptx.is_file(),
    }
    return {
        "schema": "tigercapture.ppt.editor_workflow_qa.v1",
        "ok": all(checks.values()),
        "checks": checks,
        "element_kinds": kinds,
        "asset_count": len(list_deck_assets(reloaded)),
        "validation": validation,
        "manual_ui_checkpoints": [
            "Open PPT editor from Workbench entry button",
            "Drag media-pool video/image/3D assets onto the slide canvas",
            "Drag timeline clip and typography actor onto the slide canvas",
            "Save, reopen, undo/redo, then export PPTX/MP4",
        ],
        "artifacts": {"project": str(project), "pptx": str(pptx), "slides_dir": str(out_dir / "slides")},
    }


def run_long_session_stability_qa(
    output_dir: str | Path,
    *,
    iterations: int = 80,
) -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    deck = DeckSpec(id="long-session", title="Long Session QA")
    deck.slides.append(SlideSpec(id="slide-001", title="Long Session"))
    history = PptHistoryStack(max_undo_steps=64)
    history.reset(deck)
    autosave_root = out_dir / "autosave"
    saved_paths: list[str] = []

    for index in range(max(1, int(iterations))):
        slide = deck.slides[0]
        element = SlideElement.text_box(
            f"text-{index:03d}",
            f"Edit {index:03d}",
            x=0.06 + (index % 5) * 0.16,
            y=0.08 + (index % 6) * 0.10,
            w=0.14,
            h=0.06,
            font_size=14,
        )
        slide.add_element(element)
        history.push(deck, f"Add {index:03d}")
        if index % 10 == 0:
            saved_paths.append(str(save_ppt_autosave(deck, root=autosave_root)))
        if index % 17 == 0:
            saved = save_deck_project(deck, out_dir / f"checkpoint_{index:03d}.tgppt")
            loaded = load_deck_project(saved)
            if len(loaded.slides[0].elements) != len(deck.slides[0].elements):
                raise RuntimeError("Long-session checkpoint roundtrip failed")

    undo_snapshots = 0
    while history.can_undo() and undo_snapshots < 8:
        snapshot = history.undo()
        if snapshot is not None:
            deck_from_history_snapshot(snapshot)
            undo_snapshots += 1
    redo_snapshots = 0
    while history.can_redo() and redo_snapshots < 8:
        snapshot = history.redo()
        if snapshot is not None:
            deck_from_history_snapshot(snapshot)
            redo_snapshots += 1

    final_project = save_deck_project(deck, out_dir / "long_session_final.tgppt")
    final_deck = load_deck_project(final_project)
    validation = validation_report(final_deck)
    recovery = list_ppt_recovery_candidates(deck_id=deck.id, root=autosave_root, limit=20)
    checks = {
        "final_project_exists": final_project.is_file(),
        "final_roundtrip": len(final_deck.slides[0].elements) == max(1, int(iterations)),
        "history_depth_bounded": history.depth() <= 65,
        "undo_redo_roundtrip": undo_snapshots == 8 and redo_snapshots == 8,
        "autosave_written": len(saved_paths) >= max(1, int(iterations) // 12),
        "recovery_candidates_valid": bool(recovery) and all(bool(row.get("valid")) for row in recovery),
        "validation_ok": bool(validation.get("ok")),
    }
    return {
        "schema": "tigercapture.ppt.long_session_stability_qa.v1",
        "ok": all(checks.values()),
        "checks": checks,
        "iterations": max(1, int(iterations)),
        "history_depth": history.depth(),
        "autosave_count": len(saved_paths),
        "recovery_count": len(recovery),
        "validation": validation,
        "artifacts": {"project": str(final_project), "autosave_root": str(autosave_root)},
    }


def _first_video_frame(path: Path) -> Image.Image:
    import imageio.v3 as iio

    frame = iio.imread(path, index=0)
    return Image.fromarray(frame).convert("RGB")


def _mean_abs_difference(a: Image.Image, b: Image.Image) -> float:
    left = a.convert("RGB")
    right = b.convert("RGB").resize(left.size)
    diff = ImageChops.difference(left, right)
    stat = ImageStat.Stat(diff)
    return float(sum(stat.mean) / max(1, len(stat.mean)))


def run_output_parity_qa(
    output_dir: str | Path,
    *,
    fps: int = 6,
    width: int = 640,
    height: int = 360,
    max_mean_abs_diff: float = 9.0,
) -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    deck = next(deck for name, deck in build_product_readiness_decks(out_dir / "assets") if name == "media_and_actors")
    ensure_deck_actor_posters(deck, output_dir=out_dir / "actor_posters")
    size = (max(16, int(width)), max(16, int(height)))
    png = render_deck_pngs(deck, out_dir / "slides", size=size)[0]
    expected = render_slide_image(deck, deck.slides[0], size=size, playhead_ms=0).convert("RGB")
    video_result = export_deck_video(deck, out_dir / "parity.mp4", fps=max(1, int(fps)), size=size)
    first_frame = _first_video_frame(Path(video_result["output_path"]))
    frame_diff = _mean_abs_difference(expected, first_frame)
    pptx = write_pptx_compatible(deck, out_dir / "parity.pptx")
    static = inspect_pptx_package(pptx, deck)
    checks = {
        "png_exists": Path(png).is_file(),
        "video_ok": bool(video_result.get("ok")),
        "first_frame_diff_ok": frame_diff <= float(max_mean_abs_diff),
        "pptx_static_ok": bool(static.get("ok")),
    }
    return {
        "schema": "tigercapture.ppt.output_parity_qa.v1",
        "ok": all(checks.values()),
        "checks": checks,
        "mean_abs_diff": frame_diff,
        "max_mean_abs_diff": float(max_mean_abs_diff),
        "pptx_static": static,
        "video": video_result,
        "artifacts": {"png": str(png), "video": str(video_result.get("output_path")), "pptx": str(pptx)},
    }


def run_ppt_release_acceptance_qa(
    output_dir: str | Path,
    *,
    host_backend: str = "auto",
    host_timeout_sec: int = 45,
    require_office_host: bool = False,
    stability_iterations: int = 80,
    parity_fps: int = 6,
    width: int = 640,
    height: int = 360,
) -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    office = run_office_compatibility_qa(
        out_dir / "01_office_compatibility",
        host_backend=host_backend,
        host_timeout_sec=host_timeout_sec,
        require_host=require_office_host,
    )
    workflow = run_editor_workflow_qa(out_dir / "02_editor_workflow")
    stability = run_long_session_stability_qa(out_dir / "03_long_session", iterations=stability_iterations)
    parity = run_output_parity_qa(out_dir / "04_output_parity", fps=parity_fps, width=width, height=height)
    sections = {
        "office_compatibility": office,
        "editor_workflow": workflow,
        "long_session_stability": stability,
        "output_parity": parity,
    }
    checks = {name: bool(section.get("ok")) for name, section in sections.items()}
    manifest = {
        "schema": "tigercapture.ppt.release_acceptance.v1",
        "ok": all(checks.values()),
        "output_dir": str(out_dir),
        "checks": checks,
        "sections": sections,
    }
    manifest_path = out_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    return manifest


__all__ = [
    "inspect_pptx_package",
    "run_editor_workflow_qa",
    "run_long_session_stability_qa",
    "run_office_compatibility_qa",
    "run_output_parity_qa",
    "run_ppt_release_acceptance_qa",
]
