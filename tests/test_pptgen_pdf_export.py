from __future__ import annotations

from pathlib import Path


def test_pdf_export_skips_libreoffice_when_missing(monkeypatch, tmp_path):
    from app.pptgen import pdf_export

    monkeypatch.setattr(pdf_export, "find_libreoffice_executable", lambda: None)
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"fake")

    result = pdf_export.convert_pptx_to_pdf_with_libreoffice(pptx, tmp_path / "deck.pdf")

    assert result["host"] == "libreoffice"
    assert result["status"] == "skipped"
    assert result["ok"] is False
    assert "not found" in result["reason"]


def test_export_deck_pdf_writes_source_pptx_and_uses_converter(monkeypatch, tmp_path):
    from app.pptgen import pdf_export
    from app.pptgen.sample import create_sample_deck

    def fake_export_pptx_to_pdf(pptx, pdf_path, **kwargs):
        assert Path(pptx).is_file()
        Path(pdf_path).write_bytes(b"%PDF-1.4\n")
        return {
            "schema": pdf_export.PDF_EXPORT_SCHEMA,
            "requested_backend": kwargs.get("backend") or "auto",
            "backend": "fake",
            "ok": True,
            "status": "passed",
            "output_pdf": str(pdf_path),
            "attempts": [{"host": "fake", "status": "passed"}],
        }

    monkeypatch.setattr(pdf_export, "export_pptx_to_pdf", fake_export_pptx_to_pdf)

    out = tmp_path / "deck.pdf"
    result = pdf_export.export_deck_pdf(create_sample_deck(), out, backend="auto")

    assert result["ok"] is True
    assert result["backend"] == "fake"
    assert result["slide_count"] >= 1
    assert out.read_bytes().startswith(b"%PDF")


def test_export_pptx_to_pdf_unknown_backend_reports_error(tmp_path):
    from app.pptgen.pdf_export import export_pptx_to_pdf

    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"fake")

    result = export_pptx_to_pdf(pptx, tmp_path / "deck.pdf", backend="mystery")

    assert result["ok"] is False
    assert result["attempts"] == []
    assert "Unknown" in result["reason"]
