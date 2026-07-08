"""Product-readiness QA scenarios for the user PPT generator."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.pptgen.actor_posters import ensure_deck_actor_posters
from app.pptgen.animations import set_element_animation
from app.pptgen.preview import render_contact_sheet, render_deck_pngs
from app.pptgen.project_io import load_deck_project, save_deck_project
from app.pptgen.prompt_deck import deck_from_prompt
from app.pptgen.schema import DeckSpec, ElementStyle, SlideElement, SlideSpec
from app.pptgen.templates import deck_from_template, slide_from_template
from app.pptgen.validation import validation_report
from app.pptgen.video_export import export_deck_video
from app.pptgen.writer_python_pptx import write_pptx_compatible


def _write_demo_image(path: Path, *, label: str) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (960, 540), "#DDEBFF")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 960, 540), fill="#DDEBFF")
    draw.rectangle((58, 58, 902, 482), outline="#2F6FED", width=8)
    draw.ellipse((680, 72, 850, 242), fill="#F6C453")
    draw.rectangle((95, 318, 370, 445), fill="#3A8F5A")
    draw.rectangle((410, 250, 650, 445), fill="#182033")
    try:
        font = ImageFont.truetype("arial.ttf", 56)
    except Exception:
        font = ImageFont.load_default()
    draw.text((96, 92), label, fill="#182033", font=font)
    image.save(path)
    return path


def _template_deck() -> DeckSpec:
    deck = deck_from_template("title", deck_id="qa-template", title="Template Authoring")
    deck.metadata["qa_scenario"] = "template_authoring"
    deck.slides[0].speaker_notes = "Cover slide generated from the title template."
    for index, template_id in enumerate(("two_column", "image_video_hero", "3d_showcase"), start=2):
        slide = slide_from_template(template_id, slide_id=f"slide-{index:03d}", title=f"Template {index}")
        slide.speaker_notes = f"Template coverage: {template_id}"
        deck.slides.append(slide)
    return deck


def _document_deck() -> DeckSpec:
    deck = DeckSpec(id="qa-document", title="Document Tools")
    slide = SlideSpec(id="slide-001", title="Document, Table, Chart", layout_id="document_report", duration_ms=6000)
    slide.add_element(
        SlideElement.text_box(
            "title",
            "Document Tools QA",
            x=0.07,
            y=0.06,
            w=0.72,
            h=0.09,
            font_size=38,
            bold=True,
        )
    )
    table = SlideElement.table("table", x=0.07, y=0.22, w=0.40, h=0.45, rows=4, cols=3)
    table.metadata["cells"] = [["Metric", "Now", "Goal"], ["Views", "120", "=B2*1.5"], ["CTR", "7", "10"], ["Total", "=SUM(B2:B3)", "=SUM(C2:C3)"]]
    chart = SlideElement.chart("chart", x=0.55, y=0.23, w=0.34, h=0.42)
    chart.metadata.update({"chart_type": "line", "labels": ["Q1", "Q2", "Q3", "Q4"], "values": [12, "=SUM(10,18)", 35, 44], "title": "Growth"})
    slide.add_element(table)
    slide.add_element(chart)
    slide.speaker_notes = "Table formulas and native chart export coverage."
    deck.slides.append(slide)
    deck.metadata["qa_scenario"] = "document_tools"
    return deck


def _prompt_deck() -> DeckSpec:
    prompt = "\n".join(
        [
            "Creator Launch Plan",
            "Audience problem",
            "Visual demo flow",
            "Timeline clips",
            "3D product beat",
            "Export checklist",
            "Follow-up automation",
            "Risk review",
            "Release package",
        ]
    )
    deck = deck_from_prompt(prompt, title="Prompt Deck", template_id="title_body", max_slides=3)
    deck.id = "qa-prompt"
    deck.metadata["qa_scenario"] = "prompt_deck"
    return deck


def _actor_deck(asset_dir: Path) -> DeckSpec:
    image_path = _write_demo_image(asset_dir / "demo_image.png", label="Media Pool")
    deck = DeckSpec(id="qa-actors", title="Media And 3D Actors")
    slide = SlideSpec(id="slide-001", title="Drag And Drop Actors", layout_id="media_actor_grid", duration_ms=6500)
    slide.add_element(
        SlideElement.text_box(
            "title",
            "Media Pool -> PPT Actors",
            x=0.06,
            y=0.06,
            w=0.72,
            h=0.08,
            font_size=34,
            bold=True,
        )
    )
    slide.add_element(SlideElement.image("image", image_path, x=0.06, y=0.22, w=0.27, h=0.34, kind="image", name="Image Asset"))
    video = SlideElement(
        id="video-actor",
        kind="video_actor",
        name="Timeline Video",
        x=0.38,
        y=0.22,
        w=0.25,
        h=0.34,
        style=ElementStyle(fill="#101722", stroke="#2F6FED", stroke_width=1.4, color="#EAF2FF", font_size=18, bold=True),
        metadata={"editable_actor": True, "source_path": "timeline://track/clip"},
    )
    ar = SlideElement(
        id="ar-actor",
        kind="ar_pbr_actor",
        name="AR/PBR Object",
        x=0.68,
        y=0.22,
        w=0.24,
        h=0.34,
        style=ElementStyle(fill="#F3F6FA", stroke="#3A8F5A", stroke_width=1.4, color="#182033", font_size=18, bold=True),
        metadata={"editable_actor": True, "source_path": "media://object.glb"},
    )
    slide.add_element(video)
    slide.add_element(ar)
    slide.speaker_notes = "Image, video actor, and AR/PBR actor poster fallback coverage."
    deck.slides.append(slide)
    deck.metadata["qa_scenario"] = "media_and_actors"
    return deck


def _animation_deck() -> DeckSpec:
    deck = DeckSpec(id="qa-animation", title="Animation And Timeline")
    slide = SlideSpec(id="slide-001", title="Animation Timeline", layout_id="animation_timeline", duration_ms=7000)
    title = SlideElement.text_box("title", "Animation Timing", x=0.08, y=0.09, w=0.70, h=0.10, font_size=42, bold=True)
    card = SlideElement(
        id="card",
        kind="shape",
        name="Motion Card",
        x=0.14,
        y=0.32,
        w=0.33,
        h=0.26,
        style=ElementStyle(fill="#F7F9FC", stroke="#2F6FED", stroke_width=1.2),
    )
    body = SlideElement.text_box("body", "Fade, move, click.", x=0.52, y=0.36, w=0.34, h=0.16, font_size=24, color="#354052")
    slide.add_element(title)
    slide.add_element(card)
    slide.add_element(body)
    deck.slides.append(slide)
    set_element_animation(deck, "title", in_animation="fade_in", start_ms=150, duration_ms=600)
    set_element_animation(deck, "card", in_animation="move", start_ms=800, duration_ms=800, motion_x=0.12)
    set_element_animation(deck, "body", in_animation="fade_in", trigger="on_click", click_index=1, start_ms=1200, duration_ms=600)
    deck.metadata["qa_scenario"] = "animation_timeline"
    return deck


def build_product_readiness_decks(asset_dir: str | Path) -> list[tuple[str, DeckSpec]]:
    asset_path = Path(asset_dir)
    return [
        ("template_authoring", _template_deck()),
        ("document_tools", _document_deck()),
        ("prompt_deck", _prompt_deck()),
        ("media_and_actors", _actor_deck(asset_path)),
        ("animation_timeline", _animation_deck()),
    ]


def _run_scenario(
    name: str,
    deck: DeckSpec,
    scenario_dir: Path,
    *,
    render_size: tuple[int, int],
    export_video: bool,
    video_fps: int,
    warning_budget: int,
) -> dict[str, Any]:
    scenario_dir.mkdir(parents=True, exist_ok=True)
    posters = ensure_deck_actor_posters(deck, output_dir=scenario_dir / "actor_posters")
    project = save_deck_project(deck, scenario_dir / f"{name}.tgppt")
    reloaded = load_deck_project(project)
    validation = validation_report(reloaded)
    pptx = write_pptx_compatible(reloaded, scenario_dir / f"{name}.pptx")
    slide_pngs = render_deck_pngs(reloaded, scenario_dir / "slides", size=render_size)
    contact_sheet = render_contact_sheet(reloaded, scenario_dir / "contact_sheet.png")
    video_result: dict[str, Any] = {"requested": bool(export_video), "ok": False, "skipped": not bool(export_video)}
    if export_video:
        video_result = export_deck_video(
            reloaded,
            scenario_dir / f"{name}.mp4",
            fps=max(1, int(video_fps or 8)),
            size=render_size,
        )
        video_result["requested"] = True
    checks = {
        "project_exists": project.is_file(),
        "project_roundtrip": reloaded.title == deck.title and len(reloaded.slides) == len(deck.slides),
        "validation_ok": bool(validation.get("ok")),
        "warning_budget_ok": int(validation.get("warning_count") or 0) <= int(warning_budget),
        "pptx_exists": pptx.is_file(),
        "slide_png_count_match": len(slide_pngs) == len(reloaded.slides),
        "contact_sheet_exists": contact_sheet.is_file(),
        "video_ok": (not export_video) or bool(video_result.get("ok")),
    }
    return {
        "name": name,
        "ok": all(bool(value) for value in checks.values()),
        "title": reloaded.title,
        "slide_count": len(reloaded.slides),
        "element_count": sum(len(slide.elements) for slide in reloaded.slides),
        "posters": posters,
        "validation": validation,
        "checks": checks,
        "artifacts": {
            "project": str(project),
            "pptx": str(pptx),
            "slides_dir": str(scenario_dir / "slides"),
            "contact_sheet": str(contact_sheet),
            "video": str(video_result.get("output_path") or scenario_dir / f"{name}.mp4"),
        },
        "video": video_result,
    }


def run_ppt_product_readiness_qa(
    output_dir: str | Path,
    *,
    export_video: bool = False,
    video_fps: int = 8,
    width: int = 960,
    height: int = 540,
    warning_budget: int = 6,
) -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    asset_dir = out_dir / "assets"
    render_size = (max(16, int(width or 960)), max(16, int(height or 540)))
    scenarios = [
        _run_scenario(
            name,
            deck,
            out_dir / name,
            render_size=render_size,
            export_video=bool(export_video),
            video_fps=int(video_fps or 8),
            warning_budget=int(warning_budget),
        )
        for name, deck in build_product_readiness_decks(asset_dir)
    ]
    checks = {
        "scenario_count": len(scenarios),
        "scenario_ok_count": sum(1 for row in scenarios if row.get("ok")),
        "all_scenarios_ok": all(bool(row.get("ok")) for row in scenarios),
    }
    manifest = {
        "schema": "tigercapture.ppt.product_readiness.v1",
        "ok": bool(checks["all_scenarios_ok"]) and checks["scenario_count"] >= 5,
        "output_dir": str(out_dir),
        "render_size": list(render_size),
        "export_video": bool(export_video),
        "warning_budget": int(warning_budget),
        "checks": checks,
        "scenarios": scenarios,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


__all__ = ["build_product_readiness_decks", "run_ppt_product_readiness_qa"]
