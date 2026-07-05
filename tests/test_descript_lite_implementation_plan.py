from __future__ import annotations

import json

from app.descript_lite_implementation_plan import (
    VIDEO_EDITOR_WINDOW_PATH,
    build_descript_lite_implementation_plan,
)


def test_descript_lite_implementation_plan_keeps_video_editor_window_thin() -> None:
    report = build_descript_lite_implementation_plan()

    assert report["kind"] == "descript_lite_implementation_plan"
    assert report["ok"] is True
    assert report["summary"]["video_editor_window_primary_touches"] == 0
    assert report["violations"] == []
    assert VIDEO_EDITOR_WINDOW_PATH in report["video_editor_window_policy"]["path"]
    assert all(VIDEO_EDITOR_WINDOW_PATH not in row["primary_modules"] for row in report["items"])


def test_descript_lite_implementation_plan_starts_with_core_text_editing() -> None:
    report = build_descript_lite_implementation_plan()
    items = report["items"]

    assert items[0]["id"] == "transcript_state_and_reflow"
    assert items[1]["id"] == "transcript_timeline_operations"
    assert items[2]["id"] == "selection_scoped_effects"
    assert [row["priority"] for row in items] == sorted(row["priority"] for row in items)
    assert any(row["id"] == "retake_and_mistake_cleanup" for row in items)
    assert any(row["phase"] == "post_descript_lite" for row in items)


def test_descript_lite_implementation_plan_cli_writes_report(tmp_path, monkeypatch, capsys) -> None:
    from tools import qa_descript_lite_implementation_plan

    out = tmp_path / "implementation_plan.json"
    monkeypatch.setattr("sys.argv", ["qa_descript_lite_implementation_plan.py", "--out", str(out)])

    assert qa_descript_lite_implementation_plan.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert stdout["video_editor_window_primary_touches"] == 0
