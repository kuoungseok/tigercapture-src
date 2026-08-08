from __future__ import annotations

import zipfile

from app.pptgen.preview import render_contact_sheet
from app.pptgen.overlays import set_header_footer
from app.pptgen.schema import DeckSpec, SlideElement
from app.pptgen.writer_ooxml import write_pptx


def test_ooxml_writer_creates_pptx_zip(tmp_path):
    deck = DeckSpec.sample()

    out = write_pptx(deck, tmp_path / "sample.pptx")

    assert out.is_file()
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
    assert "ppt/presentation.xml" in names
    assert "ppt/slides/slide1.xml" in names
    assert "ppt/slides/slide3.xml" in names


def test_ooxml_writer_uses_white_default_slide_background(tmp_path):
    deck = DeckSpec.sample()

    out = write_pptx(deck, tmp_path / "white.pptx")

    with zipfile.ZipFile(out) as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
    assert '<a:srgbClr val="FFFFFF"/>' in slide_xml


def test_ooxml_writer_preserves_text_font_style(tmp_path):
    deck = DeckSpec.sample()
    title = deck.slides[0].elements[0]
    title.style.font_family = "Georgia"
    title.style.italic = True
    title.style.underline = True
    title.style.line_height = 1.35

    out = write_pptx(deck, tmp_path / "styled.pptx")

    with zipfile.ZipFile(out) as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
    assert 'typeface="Georgia"' in slide_xml
    assert ' i="1"' in slide_xml
    assert ' u="sng"' in slide_xml
    assert '<a:spcPct val="135000"/>' in slide_xml


def test_ooxml_writer_exports_document_tool_elements(tmp_path):
    deck = DeckSpec.sample()
    slide = deck.slides[0]
    slide.add_element(SlideElement.table("table-1", x=0.1, y=0.2, w=0.4, h=0.3, rows=3, cols=2))
    slide.add_element(SlideElement.line("line-1", x=0.12, y=0.72, w=0.5, h=0.03))
    slide.add_element(SlideElement.chart("chart-1", x=0.5, y=0.2, w=0.3, h=0.3))

    out = write_pptx(deck, tmp_path / "document-tools.pptx")

    with zipfile.ZipFile(out) as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "<a:tbl>" in slide_xml
    assert 'prst="line"' in slide_xml
    assert "Bar 1" in slide_xml


def test_ooxml_writer_exports_header_footer_overlays(tmp_path):
    deck = DeckSpec.sample()
    set_header_footer(
        deck,
        show_header=True,
        header_text="Deck Header",
        show_footer=True,
        footer_text="Deck Footer",
        show_date=True,
        date_text="2026-07-06",
        show_slide_number=True,
    )

    out = write_pptx(deck, tmp_path / "header-footer.pptx")

    with zipfile.ZipFile(out) as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "Deck Header" in slide_xml
    assert "Deck Footer" in slide_xml
    assert "2026-07-06" in slide_xml
    assert "1 / 3" in slide_xml


def test_ooxml_writer_exports_element_animation_timing(tmp_path):
    deck = DeckSpec.sample()
    title = deck.slides[0].elements[0]
    title.animation.in_animation = "fade_in"
    title.animation.start_ms = 250
    title.animation.duration_ms = 650

    out = write_pptx(deck, tmp_path / "animated.pptx")

    with zipfile.ZipFile(out) as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "<p:timing>" in slide_xml
    assert '<p:animEffect transition="in" filter="fade">' in slide_xml
    assert 'delay="250"' in slide_xml
    assert 'dur="650"' in slide_xml


def test_ooxml_writer_exports_out_animation_when_no_entrance_exists(tmp_path):
    deck = DeckSpec.sample()
    title = deck.slides[0].elements[0]
    title.animation.in_animation = "none"
    title.animation.out_animation = "fade_out"
    title.animation.start_ms = 900
    title.animation.duration_ms = 350

    out = write_pptx(deck, tmp_path / "animated-out.pptx")

    with zipfile.ZipFile(out) as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "<p:timing>" in slide_xml
    assert '<p:animEffect transition="out" filter="fade">' in slide_xml
    assert 'delay="900"' in slide_xml
    assert 'dur="350"' in slide_xml


def test_preview_contact_sheet_is_written(tmp_path):
    deck = DeckSpec.sample()

    out = render_contact_sheet(deck, tmp_path / "sheet.png")

    assert out.is_file()
    assert out.stat().st_size > 0
