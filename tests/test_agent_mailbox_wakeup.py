from __future__ import annotations

import json
from pathlib import Path


def test_agent_mailbox_wakeup_detects_new_message(tmp_path, capsys) -> None:
    from tools import agent_mailbox_wakeup

    inbox = tmp_path / ".agent_mailbox" / "inbox_from_claude"
    inbox.mkdir(parents=True)
    (inbox / "001.md").write_text("hello codex", encoding="utf-8")

    result = agent_mailbox_wakeup.main([
        "--repo-root",
        str(tmp_path),
        "--once",
        "--print-status",
    ])

    assert result == 0
    pending = tmp_path / ".agent_mailbox" / "CODEX_WAKE_PENDING.md"
    assert pending.exists()
    text = pending.read_text(encoding="utf-8")
    assert "메일함 읽어" in text
    assert "inbox_from_claude/001.md" in text
    state = json.loads((tmp_path / ".agent_mailbox" / "state.json").read_text(encoding="utf-8"))
    assert "inbox_from_claude/001.md" in state["seen"]
    status = json.loads(capsys.readouterr().out)
    assert status["should_wake"] is True
    assert status["new_message_count"] == 1


def test_agent_mailbox_wakeup_skips_unchanged_without_always(tmp_path, capsys) -> None:
    from tools import agent_mailbox_wakeup

    inbox = tmp_path / ".agent_mailbox" / "inbox_from_claude"
    inbox.mkdir(parents=True)
    (inbox / "001.md").write_text("hello codex", encoding="utf-8")

    assert agent_mailbox_wakeup.main(["--repo-root", str(tmp_path), "--once"]) == 0
    pending = tmp_path / ".agent_mailbox" / "CODEX_WAKE_PENDING.md"
    pending.unlink()

    result = agent_mailbox_wakeup.main([
        "--repo-root",
        str(tmp_path),
        "--once",
        "--print-status",
    ])

    assert result == 0
    assert not pending.exists()
    status = json.loads(capsys.readouterr().out)
    assert status["should_wake"] is False
    assert status["new_message_count"] == 0


def test_agent_mailbox_wakeup_always_writes_pending(tmp_path) -> None:
    from tools import agent_mailbox_wakeup

    result = agent_mailbox_wakeup.main([
        "--repo-root",
        str(tmp_path),
        "--once",
        "--always-wake",
    ])

    assert result == 0
    pending = tmp_path / ".agent_mailbox" / "CODEX_WAKE_PENDING.md"
    assert pending.exists()
    assert "scheduled mailbox check" in pending.read_text(encoding="utf-8")
