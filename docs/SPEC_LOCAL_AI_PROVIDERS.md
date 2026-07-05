# Tiger Studio Local AI Provider Plan

Last updated: 2026-06-25

This document defines the implementation contract for the default free local AI
planner and switchable Claude/Codex providers in Tiger Studio.

## Goal

Tiger Studio should ship with a useful AI editing path even when the user has no
paid API key. The default product path is:

```text
AI Command / Script Edit prompt
-> selected provider
-> untrusted EditPlan JSON
-> Tiger Studio schema validation
-> preview/review
-> user-selected apply through the existing timeline systems
```

The LLM must never mutate the project directly. It may only propose validated
`EditPlan` JSON.

## Default Provider Strategy

Use `Qwen3 1.7B GGUF` as the default free local AI profile. The current
official Hugging Face GGUF package used by the first-use helper is
`Qwen/Qwen3-1.7B-GGUF:Q8_0`; if a trusted Q4 artifact is pinned later, the
manifest can be revised without changing the stable provider id.

Implementation detail:

- The app must not commit model weights to Git.
- The installer may include the model later, but source builds should use a
  first-use download/install flow.
- The provider id should be stable: `qwen_local`.
- If the local Qwen model or runner is unavailable, fall back to `rule_based`.
- The user must always be able to switch to `rule_based`, `manual_json`,
  `codex_mcp`, or `claude_mcp`.

Recommended display order:

1. `qwen_local` - Default Free AI
2. `codex_mcp` - Codex
3. `claude_mcp` - Claude
4. `local_llm` - Custom Local Command
5. `manual_json` - Manual JSON
6. `rule_based` - Offline Rules

## Provider Responsibilities

### `qwen_local`

Purpose:

- Local natural-language-to-`EditPlan` generation.
- Offline-first after model installation.
- Suitable for Korean/English creator editing prompts.

Minimum implementation:

- Report manifest metadata for the default model:
  - model family: `Qwen3`
  - model size: `1.7B`
  - quantization: `Q8_0`
  - license: `Apache-2.0`
  - provider mode: `local_bundled_optional_download`
  - model ref: `Qwen/Qwen3-1.7B-GGUF:Q8_0`
- Check for:
  - configured runner command
  - local model file or model directory
  - optional OpenAI-compatible local endpoint
- If an OpenAI-compatible endpoint is configured, mark `qwen_local` executor as
  usable and call it before deterministic fallback.
- Do not flash console windows during install/startup helper actions.
- Do not commit downloaded model weights.
- Expose an explicit install/setup status for the UI.

Generation rules:

- The provider output must be parsed as JSON.
- The JSON must pass `validate_edit_plan_json`.
- Unknown fields and forbidden execution keys must remain rejected by
  `app.ai_edit_plan`.
- On malformed output, retrying is allowed only inside the provider boundary;
  final fallback is `rule_based`.
- Small local models may omit safe-baseline UI fields while rewriting JSON.
  The provider may repair only narrow baseline-matched omissions before strict
  validation: missing `operations[].type`/`target` copied from a same-id
  baseline operation, missing basic timing/text fields copied from the same
  baseline operation, and invalid optional `confidence`/`quality_score` metadata
  removed or restored from baseline. It must not invent operation semantics.

### `codex_mcp` and `claude_mcp`

Purpose:

- Use an external agent/provider when the user explicitly enables it.
- Let advanced users work with Codex or Claude through the Tiger Studio MCP
  bridge.
- Claude's default ready-state path is automatic direct `EditPlan` generation
  through `claude --print` and the same Review validation boundary. The terminal
  handoff remains available for setup, diagnostics, and manual agent work:
  Tiger Studio can open a PowerShell-backed Claude Code terminal in the project
  folder, verify/register the `tiger-studio` MCP server, write a startup
  Markdown brief, pass that brief as Claude's initial prompt, and copy the same
  brief to the clipboard as a fallback.

Minimum implementation:

- Show configured/unconfigured/available status.
- For Claude, provide an in-app setup action that finds the Claude Code CLI and
  opens a visible PowerShell Claude Code terminal from the Tiger Studio
  workspace. The terminal flow should run
  `claude mcp add --transport stdio tiger-studio -- <server command>` before
  starting Claude Code, then pass a Tiger Studio startup Markdown brief as the
  first Claude prompt and tell the user to check `/mcp`.
- Persist successful Claude MCP registration in app settings so the user does
  not need to set environment variables by hand.
- If the Claude Code CLI is available and `claude_mcp` is selected, the app
  automatically calls `claude --print` in no-session, no-tools mode to request
  an `EditPlan` JSON proposal. The result must pass the same validation boundary
  before Review/apply, so users do not need to know a hidden environment switch.
- `TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR=0` is an advanced debug/terminal-only
  override. Leaving it unset is the normal auto-direct behavior.
- Do not execute agent commands just to check readiness.
- Do not store API keys in project files.
- Preserve the same `EditPlan` validation boundary.
- Show that these providers may require network or external login.

### `local_llm`

Purpose:

- Keep the existing custom command escape hatch.
- The command must return `EditPlan` JSON or an OpenAI-compatible response that
  contains `EditPlan` JSON.
- When `TIGERCAPTURE_LOCAL_LLM_COMMAND` is available, Tiger Studio sends a JSON
  payload on stdin containing the user command, transcript summary, schema, and
  safe baseline plan. The command may also use `{payload_json}` or `{prompt}` in
  the configured command line. Stdout is parsed as raw `EditPlan` JSON or an
  OpenAI-compatible wrapper and then validated before Review/apply.

## UI Contract

The AI Command dock and Script Edit panel should show a compact provider picker.

Required UI behavior:

- The current provider is visible before generation.
- A tooltip or status label explains why a provider is unavailable.
- If Qwen is not installed, the UI should say "Install default free AI" or
  equivalent, not "broken".
- The AI Command dock should expose a setup action:
  - Qwen: one-click install/server-start helper with a progress dialog and
    console output, model file selection, local endpoint save path, and automatic
    provider selection after the endpoint responds.
  - Claude: primary action opens a visible PowerShell Claude Code terminal in
    the Tiger Studio workspace, runs/prints the MCP registration step, writes
    `TIGER_STUDIO_CLAUDE_START.md`, passes it as Claude's initial prompt,
    copies it to the clipboard as a fallback, and tells the user to
    approve/check `tiger-studio` from Claude Code's `/mcp` screen. The older
    progress/log dialog remains available for MCP registration and status
    checks only.
  - Local LLM: primary action label is `로컬 LLM 실행`, not a generic send
    button. The tooltip should say the configured local command will run and
    must return validated `EditPlan` JSON for Review.
  - Codex: detailed MCP bridge instructions with command and env keys until a
    matching Codex auto-registration path is implemented.
- If the selected provider cannot generate, the app falls back to `rule_based`
  and clearly says so.
- If Qwen is connected and the endpoint responds, the provider label should say
  it is usable. If Claude MCP is available, the label should say Claude Code
  terminal mode is usable, not imply that in-app Review generation is the
  primary Claude workflow.
- Qwen endpoint configuration is not the same as a live server. If a direct
  request fails after an endpoint was saved, the provider remains retryable but
  is labelled as requiring attention (`확인 필요`) until a valid Qwen response
  clears the state.
- Provider status or connection questions entered in the AI Command dock are
  conversational checks, not editing requests. They should answer in the chat
  log and must not create temporary SRT rows, subtitle operations, or a Review
  plan.
- If Claude CLI print mode was available but the last direct invocation failed,
  the provider remains retryable but is labelled as requiring attention
  (`확인 필요`) until a valid Claude `EditPlan` response clears the state.
- Provider choice is app-level preference, not project content.

Required settings:

- `TIGERCAPTURE_AI_PROVIDER`
- `TIGERCAPTURE_QWEN_MODEL_PATH`
- `TIGERCAPTURE_QWEN_RUNNER_COMMAND`
- `TIGERCAPTURE_QWEN_ENDPOINT`
- `TIGERCAPTURE_LOCAL_LLM_COMMAND`
- existing MCP env flags for Codex/Claude remain supported.
- `TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR=0` optionally disables automatic Claude
  direct generation for diagnostics; unset or truthy values use auto-direct
  when Claude CLI is available.
- app settings `ai/claude_mcp/enabled` and `ai/claude_mcp/command` store the
  Claude auto-registration result.

## Safety Gates

All providers must satisfy these gates:

- Return JSON only after provider-specific cleanup.
- Validate through `validate_edit_plan_json`.
- Validate against `build_project_snapshot_from_editor` before apply.
- Use the existing preview/review/apply flow.
- Never accept fields such as `command`, `shell`, `python`, `exec`, `eval`,
  `mutation`, or `project_mutation`.
- Never run arbitrary provider-supplied commands.
- Log provider id, selected model profile, fallback reason, and validation
  result through the existing AI action log path.

## Acceptance Criteria

Implementation is complete for this stage when:

- `ai_provider_readiness({})` includes `qwen_local` and still includes existing
  providers.
- `default_ai_provider_id({})` prefers available `qwen_local`, then configured
  agent/local providers, then `rule_based`.
- Provider snapshot includes model manifest data for Qwen.
- Script Edit and AI Command UI expose provider selection/status/setup actions.
- Qwen endpoint execution sends the prompt, transcript, and deterministic
  baseline plan to an OpenAI-compatible `/chat/completions` endpoint, accepts
  only validated `EditPlan` JSON, and falls back safely on invalid output.
- Windows first-use startup prefers `llama-server.exe` and, when a Hugging Face
  cache already contains the Qwen GGUF blob, starts with `-m <cached model>`
  instead of forcing another `-hf` download path.
- Missing Qwen model produces a clear setup state and does not crash.
- Malformed provider output is rejected before preview/apply.
- Existing Script Edit tests still pass.
- New tests cover Qwen readiness, Claude saved MCP readiness, Claude CLI
  executor validation, local LLM command executor validation, provider
  preference, and fallback messaging.
- 2026-06-28 real local smoke: `llama-server.exe` loaded
  `Qwen3-1.7B-Q8_0.gguf` on `127.0.0.1:8080`; `qwen_local` generated validated
  EditPlans through the app provider path. Evidence files:
  `debugCapture/qwen_local_editplan_smoke.json` and
  `debugCapture/qwen_local_editplan_smoke_repaired.json`.

## Non-Goals For This Stage

- Committing the actual Qwen model weights.
- Building a full model downloader with resumable downloads.
- Shipping a production-grade llama.cpp binary.
- Letting Claude/Codex directly control the timeline.
- Claiming Descript/CapCut-level AI editing quality before real corpus QA.
