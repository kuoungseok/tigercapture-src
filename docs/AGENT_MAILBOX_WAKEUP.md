# Agent Mailbox Wakeup

This project can use a local file mailbox as a lightweight Claude/Codex handoff
channel. It does not require Gmail or a network mailbox.

## Mailbox Layout

Local mailbox state lives under `.agent_mailbox/`, which is intentionally
ignored by git.

```text
.agent_mailbox/
  inbox_from_claude/
  outbox_to_claude/
  processed/
  state.json
  CODEX_WAKE_PENDING.md
  wakeup_log.jsonl
```

Claude or another agent writes messages into:

```text
.agent_mailbox/inbox_from_claude/
```

Codex replies or handoff notes should be written into:

```text
.agent_mailbox/outbox_to_claude/
```

## Wakeup Contract

The watcher does not decide the work. It only emits this wake message:

```text
메일함 읽어.
Mailbox: <repo>/.agent_mailbox
Inbox: <repo>/.agent_mailbox/inbox_from_claude
Outbox: <repo>/.agent_mailbox/outbox_to_claude

새 메시지가 있으면 읽고, 필요한 답장을 outbox_to_claude에 남겨.
```

Codex should then read new inbox files, decide what matters, and write any reply
or status note to the outbox.

## Run Once

```powershell
.\.venv\Scripts\python.exe .\tools\agent_mailbox_wakeup.py --repo-root . --once --always-wake --print-status
```

## Continuous Polling

```powershell
.\.venv\Scripts\python.exe .\tools\agent_mailbox_wakeup.py --repo-root . --interval-seconds 300 --always-wake
```

## Windows Scheduled Task

Register a 5 minute scheduled wakeup task:

```powershell
.\tools\install_agent_mailbox_wakeup_task.ps1
```

The default task name is:

```text
TigerStudio-AgentMailboxWakeup
```

## Optional Real Codex Wake Command

If a future Codex task/thread API is available, set `CODEX_MAILBOX_WAKE_COMMAND`
or pass `-WakeCommand` to the scheduled-task installer.

The command receives:

- `CODEX_MAILBOX_ROOT`
- `CODEX_MAILBOX_WAKE_MESSAGE`
- `CODEX_MAILBOX_NEW_FILES`

Until that command is configured, the watcher writes
`.agent_mailbox/CODEX_WAKE_PENDING.md` so the next active Codex turn can see the
pending wake message.
