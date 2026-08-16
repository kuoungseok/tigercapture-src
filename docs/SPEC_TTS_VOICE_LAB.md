# TTS Voice Lab

Last updated: 2026-08-15

TigerCapture is moving toward a subculture media creator studio, so TTS is a
core product direction rather than a throwaway utility. The first provider is a
local Style-Bert-VITS2 sidecar, kept outside the editor process because it is
large, GPU/PyTorch-heavy, and AGPL-3.0 licensed. Voice Lab also supports Kokoro
as an optional local fallback provider installed under `external/tools`, plus
GPT-SoVITS as an optional reference-voice sidecar for few-shot/voice-cloning
workflows, and Voicebox (`jamiepine/voicebox`, MIT) as an optional multi-engine
sidecar (Qwen3-TTS, LuxTTS, Chatterbox, HumeAI TADA, Kokoro, and more) that
exposes its own voice-profile system over a local FastAPI server.

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
  sidecar command contract, provider selection, CapCut voice-provider row.
- `app/tts_synthesis.py`: stdlib HTTP client for the optional `/voice` sidecar.
- `app/tts_kokoro.py`: Kokoro provider boundary. It detects the external
  runtime, exposes Kokoro voice presets, and calls the runtime through a
  subprocess instead of importing Kokoro into the editor process.
- `app/tts_gpt_sovits.py`: GPT-SoVITS provider boundary. It detects the
  optional external sidecar, exposes reference-voice preset JSON files, builds
  the `api_v2.py` start command, and posts to `/tts` without importing the
  heavy torch stack into the editor process.
- `app/tts_voicebox.py`: Voicebox provider boundary. It detects the optional
  external sidecar checkout (`backend/main.py`, `requirements.txt`), builds the
  `python -m backend.main` start command, lists voice profiles from the
  running server's `/profiles` endpoint, and posts to `/generate/stream` for
  synchronous WAV synthesis without importing any Voicebox backend code into
  the editor process.
- `app/tts_subtitle_workflow.py`: subtitle row collection, model selection,
  deterministic generated-WAV paths, and batch synthesis planning.
- `app/tts_model_training.py`: model-maker boundary for local Style-Bert-VITS2
  voice training. It prepares `Data/<model>/raw`, launches the upstream Dataset
  and Train Gradio tools, and validates completed `model_assets/<model>` assets
  without importing PyTorch or training code into the editor process.
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

Kokoro installs under:

```text
external\tools\tts\kokoro
```

The current editor venv is Python 3.13, while Kokoro 0.9.x requires Python
`<3.13`, so the Kokoro installer creates `external\tools\tts\kokoro\.venv`
with Python 3.12 via `uv`. Model/cache files stay under
`external\tools\tts\kokoro\hf_cache`. The editor calls
`tools/kokoro_synthesize.py` as a subprocess for synthesis.

GPT-SoVITS installs under:

```text
external\tools\tts\gpt-sovits
```

The installer only clones the official `RVC-Boss/GPT-SoVITS` repository and
writes a preset template. It does not bundle reference audio, trained weights,
or model caches. A usable voice must be declared as
`external\tools\tts\gpt-sovits\voice_presets\*.json` with an existing
`ref_audio_path`, `prompt_text`, `prompt_lang`, and `text_lang`. The server
contract is `api_v2.py` on `http://127.0.0.1:9880`, using the `/tts` endpoint.

Voicebox installs under:

```text
external\tools\tts\voicebox
```

`tools/install_voicebox.py` clones the official `jamiepine/voicebox`
repository (MIT-licensed) and, with `--install-deps`, creates
`external\tools\tts\voicebox\.venv` and installs `requirements.txt`
(Python 3.12+). It does not bundle voice profiles, samples, or model caches;
Voicebox's own engines (Qwen3-TTS, LuxTTS, Chatterbox, HumeAI TADA, Kokoro,
etc.) download their weights from Hugging Face on first use. The server
contract is `python -m backend.main` on `http://127.0.0.1:8000`. Unlike
GPT-SoVITS's local JSON presets, voices are "voice profiles" managed inside
Voicebox's own SQLite database; a profile must be created through
`http://127.0.0.1:8000/docs` (`POST /profiles`) before synthesis, and
synthesis calls the synchronous `/generate/stream` endpoint rather than
polling the async `/generate` + SSE status flow.

## UI/UX Contract

The user should see a friendly setup path instead of raw Python dependency
instructions:

- `Install`: show a safe install plan, estimated size, and AGPL sidecar notice.
- `Voice Library`: choose the active local TTS provider. Current providers are
  `Style-Bert-VITS2`, `Kokoro`, `GPT-SoVITS`, and `Voicebox`. The list must always show all
  known voice libraries, sort currently usable libraries first, and render
  unavailable libraries in muted gray rather than hiding them. Catalog-only
  planned entries are visible too, including Piper, Coqui XTTS, F5-TTS,
  CosyVoice, Fish Speech, OpenVoice, MeloTTS, ChatTTS, Bark, Edge TTS,
  ElevenLabs, and Azure Speech.
- Selecting an unavailable voice library should ask whether to install it. If
  the provider exposes an automatic install command, Voice Lab runs it in a
  background install thread and refreshes status when it finishes. If no safe
  command exists or the entry is catalog-only, Voice Lab falls back to the
  install plan/guide instead of pretending it can complete the setup
  automatically.
- Python Actions must expose the same catalog through
  `tts.voice_library.catalog`. AI/MCP callers should not have to scrape
  `tts.setup.view` just to discover available and planned voice libraries.
- `Install`: show a safe install plan for the selected provider. Kokoro installs
  into `external/tools/tts/kokoro`; Style-Bert-VITS2 remains an optional sidecar
  and must not be copied into the closed source tree. GPT-SoVITS installs into
  `external/tools/tts/gpt-sovits`; it is not synthesis-ready until at least one
  reference voice preset points to an existing local audio file. Voicebox
  installs into `external/tools/tts/voicebox`; it is not synthesis-ready until
  at least one voice profile is created through its own `/docs` Swagger UI.
- `Connect`: select an existing provider folder.
- `Start server`: start the connected local `server_fastapi.py` from the UI.
  Hide/disable this for providers such as Kokoro that do not need a server.
- `Guide`: open the local install/readme location.
- `Refresh`: re-detect provider status.
- `Voice`: choose one detected local model. If `koharune-ami` exists, it is the
  default dialogue voice in the current reference install. User-trained voices
  such as `zoe` remain selectable and win when explicitly requested.
- `Model Maker`: create another local voice model through the connected
  Style-Bert-VITS2 sidecar. The editor must stage the workspace and launch the
  upstream tools instead of hiding a long GPU training job behind one click:
  - `Prepare` creates `Data/<model>/raw` and can copy user-selected source audio
    files into that folder.
  - `Dataset UI` opens the upstream Gradio dataset tool for slicing and
    transcription.
  - `Train UI` opens the upstream Gradio training tool for preprocessing,
    BERT/style generation, TensorBoard, and training.
  - `Register` validates that `model_assets/<model>` contains `config.json` and
    model weights, then refreshes Voice Lab availability.
  - Training uses the external sidecar install. TigerCapture must not copy the
    AGPL training engine into the closed editor source tree.
- `Subtitles -> Track`: synthesize project subtitles into generated WAV files
  and place them on a dialogue audio track aligned to subtitle start times.
  This command follows the selected provider. For Style-Bert-VITS2 it must check
  whether the sidecar server is responding; if it is offline but the install is
  valid, Voice Lab starts `server_fastapi.py`, shows a clear waiting message,
  waits for `/status` or `/models/info`, then continues generation. For Kokoro,
  it skips server startup and runs the external venv subprocess. For GPT-SoVITS,
  it requires a selected reference preset and calls the local `/tts` API. For
  Voicebox, it requires a selected voice profile id and calls the local
  `/generate/stream` API for synchronous WAV synthesis.
- Bilingual dialogue rows: display captions and spoken TTS text may differ.
  Store the rendered caption in `subtitle_text` / `display_text` and the text
  sent to the voice model in `tts_text` / `spoken_text`. Project subtitles keep
  the on-screen text as `Subtitle.text`; alternate spoken text is persisted in
  `Subtitle.style["tts_text"]`. A plain dialogue line may use
  `Japanese => Korean`, `Japanese -> Korean`, `Japanese || Korean`, or a tab
  separator so the TTS sidecar receives Japanese while the video subtitle shows
  Korean.
- Actor lip-sync: subtitle/TTS clip timing can be baked into a selected Live2D
  actor through renderable `parameter_keyframes`, using `ParamMouthOpenY` and
  `ParamMouthForm` by default. It also writes natural deterministic blink
  tracks to `ParamEyeLOpen` and `ParamEyeROpen` by default so generated dialogue
  takes do not look frozen. This is a timing-envelope bridge, not a full phoneme
  solver yet; future audio-energy or phoneme analysis should extend the same
  `tigercapture.tts_actor_lipsync.v1` payload instead of replacing the UI
  workflow.
- One-shot dialogue take: AI/actions can pass dialogue text to
  `tts.dialogue.generate_actor_take` and get project subtitles, generated WAV
  clips, Live2D mouth/blink keys, bottom-edge placement, and a default
  natural acting layer in one operation. Unless the caller explicitly disables
  it, generated dialogue applies deterministic head/body/breath/arm parameter
  keys and prefers the model's authored idle motion so a 30-second take does
  not remain in a static A/T pose. When the selected `.model3.json` exposes
  multiple authored `.motion3.json` entries, the action applies an authored
  dialogue storyboard after TTS lip-sync: the actor clip is split into
  dialogue-line ranges, each range receives a suitable model motion
  (`Greeting`, `Talk`, `Happy`, etc. when labels are available), and sliced
  mouth/blink/parameter keys are preserved on those new clips. If a Live2D
  actor target is not specified, the first available Live2D actor clip is used.
  If no actor exists, the action still creates subtitles and audio and reports
  `actor_lipsync.reason=no_live2d_actor`.
- Dialogue take planning: `tts.dialogue.plan_actor_take` is the non-mutating
  choice surface for AI and UI. It returns Live2D target candidates, TTS voice
  candidates, placement presets, size presets, and recommended defaults. The UI
  can show these lists to the user, while AI can skip the prompt and use the
  recommended values.
- Dialogue placement: generated Live2D takes default to `bottom_right` with
  `auto_fit`. The placement helper renders/measures the visible alpha bounds of
  the Live2D frame when possible and fits that visible bbox to the preset safe
  area so half-body or cropped models still touch the lower output edge. If
  measurement fails, it falls back to deterministic preset coordinates and
  records diagnostics in `dialogue_placement_payload`.
- Dialogue TTS stability: Japanese dialogue or `*-jp` voice models default to
  `language=JP` with conservative Style-Bert-VITS2 noise/length values unless
  the caller explicitly overrides them. The default dialogue recommendation is
  `koharune-ami` when present; explicit user choices such as `zoe` are
  preserved. Kokoro voice names such as `af_heart` and `jf_alpha` map to Kokoro
  language codes and should stay selectable through the same Voice combo.

Automatic install must remain user-initiated and explicit. AI/MCP actions
should return install plans and execution gates, not silently download or run a
multi-GB setup.

## Actions

Current setup actions:

- `tts.provider.status`
- `tts.provider.select`
- `tts.setup.instructions`
- `tts.setup.view`
- `tts.install.plan`
- `tts.install.execution_gate`
- `tts.server.start_plan`
- `tts.server.ensure_running`
- `tts.connect_installed_sidecar`
- `tts.model.training.plan`
- `tts.model.training.execution_gate`
- `tts.model.training.prepare_workspace`
- `tts.model.training.launch_dataset`
- `tts.model.training.launch_train`
- `tts.model.training.register_result`

Current synthesis/timeline actions:

- `tts.voice.list`
- `tts.subtitle.plan`
- `tts.subtitle.generate_to_timeline`
- `tts.subtitle.apply_actor_lipsync`
- `tts.dialogue.plan_actor_take`
- `tts.dialogue.generate_actor_take`

Generated audio should be ordinary WAV media so it can flow through existing
Media Pool, AudioClip, Sound Editor, mixer, export, and project-save systems.
The default generated-media root is `external/assets/tts/generated`, not
`debugCapture`, because generated voice clips may become project assets.
`tts.subtitle.generate_to_timeline` auto-starts the local sidecar by default;
automation can pass `auto_start_server=false` only when it intentionally wants
to fail fast or test timeline placement without launching the server.
The same generation action accepts `apply_actor_lipsync=true`,
`actor_track_id`, and `actor_clip_index` when the caller wants subtitle voice
generation and Live2D mouth/blink-key baking as one operation.
`tts.dialogue.generate_actor_take` is the preferred AI-facing action when the
input is raw dialogue text rather than existing subtitle rows. It accepts
`actor_target_id`, `placement_preset`, `size_preset`, and
`apply_actor_placement`; `apply_actor_motion` is on by default for natural
head/body/breath/arm motion. `actor_target_id` may point to an existing timeline
Live2D actor or a Live2D model asset in the media pool, in which case the action
creates the actor clip before applying TTS, placement, and motion.

## QA

- Unit QA must cover: missing install, partial install, server offline,
  sidecar start failure, startup timeout, successful server readiness, subtitle
  generation, Live2D mouth/blink-key baking, one-shot dialogue actor takes,
  non-mutating dialogue take plans, Live2D alpha-bounds placement, natural
  dialogue motion keys, Japanese synthesis defaults, media-pool Live2D target
  creation, model-training plan contracts, workspace preparation, and completed
  model registration.
- `tools/qa_tts_voice_lab.py` is the local preflight script. By default it does
  not launch the sidecar; pass `--auto-start` only when a human or release QA
  intentionally wants to start `server_fastapi.py`.
- The in-app QA Dashboard exposes this as `Voice Lab Sidecar` and runs it with
  `--auto-start --wait-timeout 120` so video/subtitle/TTS project evaluation
  sessions recover from an offline-but-installed server before marking the
  workflow failed.
- The QA report is disposable evidence and writes to
  `debugCapture/voice_lab_sidecar_qa.json`.
