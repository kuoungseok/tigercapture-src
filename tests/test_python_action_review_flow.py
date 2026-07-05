from __future__ import annotations

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_python_action_review_flow_runs_from_sample_media_dir(tmp_path):
    from tools.qa_python_action_review_flow import run_action_review_flow

    media_dir = tmp_path / "media"
    media_dir.mkdir()
    (media_dir / "sample.mp4").write_bytes(b"fake video")
    out_dir = tmp_path / "out"

    report = run_action_review_flow(media_dir=media_dir, out_dir=out_dir)

    assert report["ok"] is True
    assert report["registered_action_count"] >= 47
    assert report["action_count"] >= 8
    assert (out_dir / "action_review.png").exists()
    assert (out_dir / "action_review.gif").exists()
    assert (out_dir / "python_action_review_flow_qa.json").exists()
