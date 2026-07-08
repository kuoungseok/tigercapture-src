from __future__ import annotations

from pathlib import Path


def test_pptx_static_inspection_detects_slides_charts_and_timing(tmp_path):
    from app.pptgen.product_readiness import build_product_readiness_decks
    from app.pptgen.release_acceptance import inspect_pptx_package
    from app.pptgen.writer_python_pptx import write_pptx_compatible

    decks = dict(build_product_readiness_decks(tmp_path / "assets"))

    document = decks["document_tools"]
    document_pptx = write_pptx_compatible(document, tmp_path / "document.pptx")
    document_report = inspect_pptx_package(document_pptx, document)
    assert document_report["ok"] is True
    assert document_report["details"]["chart_part_count"] >= 1

    animation = decks["animation_timeline"]
    animation_pptx = write_pptx_compatible(animation, tmp_path / "animation.pptx")
    animation_report = inspect_pptx_package(animation_pptx, animation)
    assert animation_report["ok"] is True
    assert animation_report["details"]["has_timing_xml"] is True


def test_release_acceptance_runs_all_four_sections(monkeypatch, tmp_path):
    import app.pptgen.release_acceptance as release_acceptance

    def fake_export_pptx_to_pdf(pptx, pdf_path, **_kwargs):
        Path(pdf_path).write_bytes(b"%PDF-1.4\n")
        return {
            "schema": "tigercapture.ppt.pdf_export.v1",
            "ok": True,
            "status": "passed",
            "backend": "fake",
            "output_pdf": str(pdf_path),
            "source_pptx": str(pptx),
            "attempts": [{"host": "fake", "status": "passed"}],
        }

    monkeypatch.setattr(release_acceptance, "export_pptx_to_pdf", fake_export_pptx_to_pdf)

    manifest = release_acceptance.run_ppt_release_acceptance_qa(
        tmp_path,
        stability_iterations=16,
        parity_fps=2,
        width=320,
        height=180,
    )

    assert manifest["schema"] == "tigercapture.ppt.release_acceptance.v1"
    assert manifest["ok"] is True
    assert manifest["checks"] == {
        "office_compatibility": True,
        "editor_workflow": True,
        "long_session_stability": True,
        "output_parity": True,
    }
    assert Path(manifest["manifest_path"]).is_file()
