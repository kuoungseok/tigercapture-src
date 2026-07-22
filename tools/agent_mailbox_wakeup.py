from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INTERVAL_SECONDS = 300
MAILBOX_DIRNAME = ".agent_mailbox"
INBOX_DIRNAME = "inbox_from_claude"
OUTBOX_DIRNAME = "outbox_to_claude"
PROCESSED_DIRNAME = "processed"
STATE_FILENAME = "state.json"
PENDING_FILENAME = "CODEX_WAKE_PENDING.md"
LOG_FILENAME = "wakeup_log.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mailbox_root(repo_root: Path) -> Path:
    return repo_root / MAILBOX_DIRNAME


def ensure_mailbox(root: Path) -> None:
    for name in (INBOX_DIRNAME, OUTBOX_DIRNAME, PROCESSED_DIRNAME):
        (root / name).mkdir(parents=True, exist_ok=True)


def load_state(root: Path) -> dict[str, Any]:
    path = root / STATE_FILENAME
    if not path.exists():
        return {"schema": "tigerstudio.agent_mailbox_wakeup.v1", "seen": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": "tigerstudio.agent_mailbox_wakeup.v1", "seen": {}}
    if not isinstance(data, dict):
        return {"schema": "tigerstudio.agent_mailbox_wakeup.v1", "seen": {}}
    if not isinstance(data.get("seen"), dict):
        data["seen"] = {}
    return data


def save_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    (root / STATE_FILENAME).write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def file_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "sha256": digest.hexdigest(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def list_inbox_files(root: Path) -> list[Path]:
    inbox = root / INBOX_DIRNAME
    if not inbox.exists():
        return []
    return sorted(
        path
        for path in inbox.iterdir()
        if path.is_file() and not path.name.startswith(".")
    )


def scan_new_messages(root: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    seen = state.setdefault("seen", {})
    new_messages: list[dict[str, Any]] = []
    for path in list_inbox_files(root):
        relative = path.relative_to(root).as_posix()
        fingerprint = file_fingerprint(path)
        previous = seen.get(relative)
        if previous != fingerprint:
            preview = ""
            try:
                preview = path.read_text(encoding="utf-8", errors="replace")[:2000]
            except Exception:
                preview = ""
            new_messages.append(
                {
                    "path": str(path),
                    "relative_path": relative,
                    "name": path.name,
                    "fingerprint": fingerprint,
                    "preview": preview,
                }
            )
        seen[relative] = fingerprint
    return new_messages


def build_wake_message(root: Path, new_messages: list[dict[str, Any]], *, always_wake: bool) -> str:
    lines = [
        "메일함 읽어.",
        f"Mailbox: {root}",
        f"Inbox: {root / INBOX_DIRNAME}",
        f"Outbox: {root / OUTBOX_DIRNAME}",
        "",
        "새 메시지가 있으면 읽고, 필요한 답장을 outbox_to_claude에 남겨.",
    ]
    if new_messages:
        lines.extend(["", "New or changed files:"])
        for item in new_messages:
            lines.append(f"- {item['relative_path']}")
    elif always_wake:
        lines.extend(["", "No new file fingerprint was detected. This is the scheduled mailbox check."])
    return "\n".join(lines).strip() + "\n"


def write_pending(root: Path, message: str, new_messages: list[dict[str, Any]]) -> Path:
    pending = root / PENDING_FILENAME
    payload = [
        "# Codex Wake Pending",
        "",
        f"- updated_at: {utc_now()}",
        f"- new_message_count: {len(new_messages)}",
        "",
        "## Wake Message",
        "",
        "```text",
        message.rstrip(),
        "```",
        "",
    ]
    pending.write_text("\n".join(payload), encoding="utf-8")
    return pending


def append_log(root: Path, event: dict[str, Any]) -> None:
    event = {"timestamp": utc_now(), **event}
    with (root / LOG_FILENAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def run_wake_command(command: str, root: Path, message: str, new_messages: list[dict[str, Any]]) -> dict[str, Any]:
    env = os.environ.copy()
    env["CODEX_MAILBOX_ROOT"] = str(root)
    env["CODEX_MAILBOX_WAKE_MESSAGE"] = message
    env["CODEX_MAILBOX_NEW_FILES"] = json.dumps(
        [item["relative_path"] for item in new_messages],
        ensure_ascii=False,
    )
    try:
        completed = subprocess.run(
            command,
            cwd=str(root.parent),
            env=env,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as exc:
        return {"status": "failed_to_start", "error": str(exc)}
    return {
        "status": "ok" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def tick(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    root = mailbox_root(repo_root)
    ensure_mailbox(root)
    state = load_state(root)
    new_messages = scan_new_messages(root, state)
    should_wake = bool(new_messages) or bool(args.always_wake)
    message = build_wake_message(root, new_messages, always_wake=bool(args.always_wake))
    pending_path: Path | None = None
    wake_result: dict[str, Any] | None = None
    if should_wake:
        pending_path = write_pending(root, message, new_messages)
        wake_command = args.wake_command or os.environ.get("CODEX_MAILBOX_WAKE_COMMAND", "")
        if wake_command:
            wake_result = run_wake_command(wake_command, root, message, new_messages)
    save_state(root, state)
    append_log(
        root,
        {
            "event": "tick",
            "should_wake": should_wake,
            "new_message_count": len(new_messages),
            "pending_path": str(pending_path) if pending_path else "",
            "wake_command_configured": bool(args.wake_command or os.environ.get("CODEX_MAILBOX_WAKE_COMMAND", "")),
            "wake_result": wake_result,
        },
    )
    if args.print_status:
        print(
            json.dumps(
                {
                    "mailbox": str(root),
                    "should_wake": should_wake,
                    "new_message_count": len(new_messages),
                    "pending_path": str(pending_path) if pending_path else "",
                    "wake_result": wake_result,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll a local Claude/Codex mailbox and emit a Codex wake message.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root containing .agent_mailbox.")
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--once", action="store_true", help="Run one scan and exit.")
    parser.add_argument(
        "--always-wake",
        action="store_true",
        help="Emit the wake message even when no new mailbox file changed.",
    )
    parser.add_argument(
        "--wake-command",
        default="",
        help="Optional command invoked when a wake message should be sent. Also supported via CODEX_MAILBOX_WAKE_COMMAND.",
    )
    parser.add_argument("--print-status", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or sys.argv[1:]))
    if args.once:
        return tick(args)
    while True:
        tick(args)
        time.sleep(max(5, int(args.interval_seconds)))


if __name__ == "__main__":
    raise SystemExit(main())
