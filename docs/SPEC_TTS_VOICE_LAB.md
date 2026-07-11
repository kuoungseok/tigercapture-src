# TTS Voice Lab

Last updated: 2026-07-10

TigerCapture is moving toward a subculture media creator studio, so TTS is a
core product direction rather than a throwaway utility. The first provider is a
local Style-Bert-VITS2 sidecar, kept outside the editor process because it is
large, GPU/PyTorch-heavy, and AGPL-3.0 licensed.

## Product Role

Voice Lab should eventually cover:

- anime-style character narration
- subtitle-to-voice generation
- PPT narration
- VTuber/actor dialogue
- sentence-level voice replacement from transcript edits
- generated WAV registration into the Media Pool and audio timeline

## Current Boundary

- `app/tts_setup.py`: provider detection, install plan, setup instructions,
  sidecar command contract, CapCut voice-provider row.
- `app/tts_synthesis.py`: stdlib HTTP client for the optional `/voice` sidecar.
- `app/tts_subtitle_workflow.py`: subtitle row collection, model selection,
  deterministic generated-WAV paths, and batch synthesis planning.
- `app/tts_lab.py`: standalone Voice Lab page/window plus the `Subtitles -> Track`
  button.
- `app/actions/tts_namespace.py`: Python Action surface for AI/MCP/QA.
- `app/actions/editor_adapter_tts.py`: action adapter methods.
- `app/workbench_panel.py`: exposes Voice Lab as a Composer-adjacent tool in
  the Workbench Audio tab. Voice Lab must not be nested inside Sound Editor.
  Composer and Voice Lab are creation tools, so their dock buttons must remain
  visible even when the project has no audio track and no audio clip is
  selected.

## Reference Install

The current local reference install is:

```text
D:\TTS\sbv2\Style-Bert-VITS2
```

It is not a current editor runtime dependency, but it is a durable product
reference asset. Do not delete it just because the source tree has no direct
runtime import.

The reference install exposes:

- FastAPI `/voice`
- FastAPI `/models/info`
- local model assets under `model_assets`
- CUDA-ready torch environment on the user's machine

## UI/UX Contract

The user should see a friendly setup path instead of raw Python dependency
instructions:

- `Install`: show a safe install plan, estimated size, and AGPL sidecar notice.
- `Connect`: select an existing Style-Bert-VITS2 folder.
- `Start server`: start the connected local `server_fastapi.py` from the UI.
- `Guide`: open the local install/readme location.
- `Refresh`: re-detect provider status.
- `Voice`: choose one detected local model. If `zoe` exists, it is the default
  because it is the user's trained model in the current reference install.
- `Subtitles -> Track`: synthesize project subtitles into generated WAV files
  and place them on a dialogue audio track aligned to subtitle start times.
  This command must check whether the sidecar server is responding; if it is
  offline but the install is valid, Voice Lab starts `server_fastapi.py`, shows
  a clear waiting message, waits for `/status` or `/models/info`, then
  continues generation.
- Actor lip-sync: subtitle/TTS clip timing can be baked into a selected Live2D
  actor through renderable `parameter_keyframes`, using `ParamMouthOpenY` and
  `ParamMouthForm` by default. This is a timing-envelope bridge, not a full
  phoneme solver yet; future audio-energy or phoneme analysis should extend the
  same `tigercapture.tts_actor_lipsync.v1` payload instead of replacing the UI
  workflow.

Automatic install must remain user-initiated and explicit. AI/MCP actions
should return install plans and execution gates, not silently download or run a
multi-GB setup.

## Actions

Current setup actions:

- `tts.provider.status`
- `tts.setup.instructions`
- `tts.setup.view`
- `tts.install.plan`
- `tts.install.execution_gate`
- `tts.server.start_plan`
- `tts.server.ensure_running`
- `tts.connect_installed_sidecar`

Current synthesis/timeline actions:

- `tts.voice.list`
- `tts.subtitle.plan`
- `tts.subtitle.generate_to_timeline`
- `tts.subtitle.apply_actor_lipsync`

Generated audio should be ordinary WAV media so it can flow through existing
Media Pool, AudioClip, Sound Editor, mixer, export, and project-save systems.
The default generated-media root is `external/assets/tts/generated`, not
`debugCapture`, because generated voice clips may become project assets.
`tts.subtitle.generate_to_timeline` auto-starts the local sidecar by default;
automation can pass `auto_start_server=false` only when it intentionally wants
to fail fast or test timeline placement without launching the server.
The same generation action accepts `apply_actor_lipsync=true`,
`actor_track_id`, and `actor_clip_index` when the caller wants subtitle voice
generation and Live2D mouth-key baking as one operation.

## QA

- Unit QA must cover: missing install, partial install, server offline,
  sidecar start failure, startup timeout, successful server readiness, subtitle
  generation, and Live2D mouth-key baking.
- `tools/qa_tts_voice_lab.py` is the local preflight script. By default it does
  not launch the sidecar; pass `--auto-start` only when a human or release QA
  intentionally wants to start `server_fastapi.py`.
- The QA report is disposable evidence and writes to
  `debugCapture/voice_lab_sidecar_qa.json`.
