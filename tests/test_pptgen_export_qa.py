from __future__ import annotations

import json
from pathlib import Path


def test_ppt_export_qa_writes_core_artifacts(tmp_path):
    from app.pptgen.export_qa import run_ppt_export_qa

    manifest = run_ppt_export_qa(tmp_path, export_pdf=False, export_video=False, width=320, height=180)

    assert manifest["schema"] == "tigercapture.ppt.export_qa.v1"
    assert manifest["ok"] is True
    assert manifest["slide_count"] > 0
    assert Path(manifest["artifacts"]["pptx"]).is_file()
    assert Path(manifest["artifacts"]["contact_sheet"]).is_file()
    assert Path(manifest["artifacts"]["slides_dir"]).is_dir()
    assert manifest["checks"]["slide_png_count"] == manifest["slide_count"]

    saved = json.loads(Path(manifest["manifest_path"]).read_text(encoding="utf-8"))
    assert saved["schema"] == manifest["schema"]
    assert saved["checks"]["pptx_exists"] is True
