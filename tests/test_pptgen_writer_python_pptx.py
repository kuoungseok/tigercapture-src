from __future__ import annotations

import io
import zipfile


def test_python_pptx_writer_exports_powerpoint_package_with_timing(tmp_path):
    from app.pptgen.animation_qa import build_animation_qa_deck, inspect_pptx_animation_xml
    from app.pptgen.writer_python_pptx import write_pptx_compatible

    deck = build_animation_qa_deck()

    out = write_pptx_compatible(deck, tmp_path / "compatible.pptx")

    assert out.is_file()
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        slide1 = zf.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "ppt/presentation.xml" in names
    assert "ppt/slides/slide4.xml" in names
    assert "s1-title" in slide1
    assert "<p:timing>" in slide1
    checks = inspect_pptx_animation_xml(out)
    assert checks["slide_count"] == 4
    assert checks["slides_with_timing"] >= 3
    assert checks["anim_effect_count"] >= 5
    assert checks["on_click_count"] >= 2


def test_python_pptx_writer_exports_native_office_chart(tmp_path):
    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec
    from app.pptgen.writer_python_pptx import write_pptx_compatible

    deck = DeckSpec(id="deck-chart", title="Chart Deck")
    slide = SlideSpec(id="slide-001", title="Chart")
    chart = SlideElement.chart("chart-1", x=0.12, y=0.18, w=0.72, h=0.52)
    chart.name = "Revenue"
    chart.metadata["labels"] = ["A", "B"]
    chart.metadata["values"] = ["10", "=SUM(10,20)"]
    chart.metadata["chart_type"] = "bar"
    slide.add_element(chart)
    deck.slides.append(slide)

    out = write_pptx_compatible(deck, tmp_path / "chart.pptx")

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8", errors="replace")
        chart_xml = zf.read("ppt/charts/chart1.xml").decode("utf-8", errors="replace")
        embedded = [name for name in names if name.startswith("ppt/embeddings/") and name.endswith(".xlsx")]
        assert embedded
        workbook_bytes = zf.read(embedded[0])
    assert "ppt/charts/chart1.xml" in names
    assert "c:chart" in slide_xml
    assert "chart-1" in slide_xml
    assert "Revenue" in chart_xml
    with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as workbook:
        sheet_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8", errors="replace")
    assert "30" in sheet_xml


def test_python_pptx_writer_uses_actor_poster_as_picture(tmp_path):
    from PIL import Image

    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec
    from app.pptgen.writer_python_pptx import write_pptx_compatible

    poster = tmp_path / "poster.png"
    Image.new("RGB", (96, 54), (80, 160, 220)).save(poster)

    deck = DeckSpec(id="deck-actor", title="Actor Deck")
    slide = SlideSpec(id="slide-001", title="Actor")
    actor = SlideElement(
        id="actor-1",
        kind="ar_pbr_actor",
        name="Scene Actor",
        source_path="scene.gltf",
        x=0.2,
        y=0.2,
        w=0.4,
        h=0.35,
    )
    actor.metadata["poster_path"] = str(poster)
    slide.add_element(actor)
    deck.slides.append(slide)

    out = write_pptx_compatible(deck, tmp_path / "actor.pptx")

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8", errors="replace")
    assert any(name.startswith("ppt/media/image") for name in names)
    assert "actor-1" in slide_xml
