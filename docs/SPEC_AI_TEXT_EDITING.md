# TigerCapture AI Script & One-Click Editing Plan

Last updated: 2026-07-05

This document describes the planned AI text-editing, AI script-editing, and
one-click recipe workflow for TigerCapture.
The goal is not to build a generic generative-video product. The goal is to
make TigerCapture projects editable through transcript text and natural-language
commands, while preserving deterministic timeline behavior, undo/redo,
preview/export parity, and local-first privacy.

## Product Position

TigerCapture AI Script & One-Click Editing should be:

> A script-driven editing cockpit for screen recordings, tutorials, creator
> videos, Live2D/Spine commentary, and post-production polish.

The feature should not replace the timeline. The timeline remains the precision
editing surface. Script Edit is the fast planning and rough-cut surface.
One-click recipes are packaged planning flows over the same `EditPlan` model,
not a second timeline engine.

The user-facing promise:

- Edit spoken video by editing text.
- Ask for common cleanup actions in natural language.
- Run one-click recipes such as clean tutorial, Shorts, product demo, devlog,
  and publish package.
- Review an edit plan before anything touches the timeline.
- Convert transcripts into captions, chapters, shorts, callouts, zooms, and
  actor commentary.
- Keep the local/offline workflow useful when a local LLM or local Whisper is
  installed.

## Descript-Lite Priority Ladder

The product gate for any Descript-lite positioning follows this order:

1. Text-based editing must become real timeline editing: transcript word or
   sentence deletion becomes actual video/audio ripple cut, sentence movement
   moves linked clips, selected text can target only that range for captions,
   zoom, or emphasis, and word-level timing, transcript reflow, undo, and redo
   stay correct.
2. Transcription quality must produce an immediately editable script from media:
   Whisper/WhisperX-grade word timestamps, diarization, punctuation and paragraph
   cleanup, mixed Korean/English handling, and game/broadcast glossary repair.
3. One-click cleanup must change the result, not only advise: filler removal,
   silence removal, retake removal, and repeated/mistake segment detection must
   produce reviewable, materialized edits.
4. Studio Sound-grade audio must include denoise, dereverb/room reduction,
   loudness leveling, EQ/compressor/de-esser presets, and speech enhancement
   with before/after QA.
5. AI voice/replacement recording must support TTS, sentence-level replacement
   after a text edit, later voice-clone consent/legal UI, and translation
   dubbing.
6. AI co-editor UX should accept natural commands such as "make a 30-second
   short" or "remove stutters", then show a change list, preview, and partial
   apply controls before mutation.
7. Collaboration/cloud is required for a full Descript replacement: share links,
   comments/review, version history, and team workspaces.

Claim gates:

- Priorities 1-3 must be `claim_ready` before TigerCapture can honestly use a
  Descript-lite claim.
- Priorities 1-5 must be `claim_ready` before a $149+ Descript-style value
  defense is safe.
- Priority 6 matches TigerCapture's safety philosophy: AI proposes, Review
  decides, and partial apply keeps the user in control.
- Priority 7 is outside local-first Descript-lite, but blocks any full Descript
  replacement claim.

Current implementation judgment:

- Transcript deletion can already become reviewed video/audio ripple cuts.
- P1 foundation services now exist outside `VideoEditorWindow`: transcript
  reflow after reviewed cuts, transcript sentence move -> linked clip-move
  intents, and selection-scoped caption/zoom/highlight plan generation.
- `ScriptEditPanelModel` now owns the first transcript edit surface API:
  range selection, selected-range deletion plans, scoped effects, sentence move
  preview, and post-cut transcript reflow.
- One-click cleanup now includes deterministic retake/repeated-line/false-start
  detection. `app.retake_detection` turns repeated takes and mistake phrases
  into reviewed `delete_time_range` operations, and `clean_tutorial` includes
  those operations alongside filler and silence cleanup.
- P2 transcription has a local-first contract layer: faster-whisper is called
  with `word_timestamps=True`, `app.transcription_providers` builds
  `TranscriptWord` rows and assigns speaker turns, and `app.transcript_cleanup`
  restores punctuation/paragraph metadata plus mixed Korean/English glossary
  terms such as OBS, FFmpeg, Live2D, VTuber, shader, and timeline.
  `app.transcription_settings` and
  `tools/configure_local_whisper_model.py` persist the local faster-whisper
  model path, while existing Systran faster-whisper snapshots in the local
  Hugging Face cache are discovered automatically.
- Claude direct corpus QA can back smart-edit planning on the current corpus.
- Descript-lite claim readiness now passes for priorities 1-3 when the local
  faster-whisper cache/model is available. $149+ Descript-style value defense
  also passes when the speech-enhance and sentence voice-replacement QA reports
  are current, but this remains a gated local workflow claim, not a full
  Descript replacement or collaboration claim.

## VideoEditorWindow Touch Policy

`app/video_editor_window.py` is a refactoring target, so Descript-lite work must
not add new feature logic there. New behavior should land in small modules first:

- transcript state and reflow: `app/transcript_document.py`,
  `app/transcript_reflow.py`
- transcript-to-timeline planning: `app/transcript_timeline_ops.py`
- selected-text scoped actions: `app/transcript_selection_actions.py`
- ASR/script cleanup providers: `app/transcription_providers.py`,
  `app/transcription_settings.py`, `app/transcript_cleanup.py`
- retake/mistake cleanup: `app/retake_detection.py`
- speech enhance: `app/speech_enhance.py`
- sentence voice replacement: `app/ai_voice_replacement.py`
- review grouping: `app/ai_review_model.py`

The only acceptable `VideoEditorWindow` change is a thin adapter: signal hookup,
dependency injection, or one call into a service/action that already has tests.
`tools/qa_descript_lite_implementation_plan.py` writes the implementation plan
and verifies that no planned item uses `VideoEditorWindow` as its primary module.
`tools/qa_descript_lite_p1_services.py` verifies the first P1 service layer:
reflow, sentence move intents, selection-scoped edit plans, and the
`ScriptEditPanelModel` transcript edit surface API. Rich visible word/sentence
controls can be added later in the panel while preserving this model boundary.
`tools/qa_descript_lite_p3_cleanup.py` verifies retake and mistake cleanup
without using `VideoEditorWindow`.
`tools/qa_descript_lite_p2_transcription.py` verifies the editable-script
contract and separately reports whether a real local ASR model is configured.
`tools/configure_local_whisper_model.py` saves an existing local faster-whisper
model path, and `tools/qa_transcription_runtime_setup.py` reports saved
settings, Hugging Face cache discoveries, candidate model paths, and next
actions when the model is missing.
`tools/qa_speech_enhance.py` verifies the local speech-enhance fallback and
before/after QA, and `tools/qa_ai_voice_replacement.py` verifies reviewed
sentence voice replacement plus explicit consent gating.

## One-Click Recipe Mode

One-click recipe mode is the scripted version of natural-language planning.
Instead of a freeform prompt, TigerCapture starts from a known recipe intent
and deterministic defaults, then produces the same reviewable `EditPlan`.

Initial recipes:

- `clean_tutorial`: remove long silences, remove Korean/English filler words,
  create tutorial captions, suggest chapters, and stage cursor zooms.
- `shorts`: propose Short candidates, 9:16 reframes, styled captions, hook
  cards, and render-queue jobs.
- `product_demo`: apply a product-demo preset, generate captions, suggest
  feature callouts, stage product-focused zooms, and create a review render.
- Future recipes: product devlog, Live2D/Spine commentary, podcast cleanup,
  publish package, and localization pass.

Recipe mode must stay inspectable. It should show the same plan preview,
operation list, warnings, affected durations, review cards, and quality scores
as a natural-language command.

### Recipe Plan Layering

Recipes are layered plans:

```text
recipe intent
-> transcript, audio, cursor, visual, and project context
-> deterministic operation proposals
-> optional LLM explanation or title/copy proposals
-> validated EditPlan JSON
-> review cards and quality scores
-> preview/diff
-> user-selected apply through normal timeline systems
```

Layers should be visible in plan metadata so QA can tell whether an operation
came from transcript selection, silence detection, filler detection, cursor
events, local visual tags, an explicit recipe, or future optional LLM metadata.

### Multimodal Inputs

AI Script & One-Click Editing may use multiple local-first input streams:

- Transcript segments and word timings.
- Imported SRT/VTT/manual transcript rows.
- Audio analysis, including silence intervals and loudness summaries.
- Cursor sidecars, clicks, drag events, and hotkeys.
- Local visual tags from `app/local_ml.py`.
- Project metadata, markers, clip names, render variants, and presets.
- Future user-provided images or references for thumbnails/callouts.

The MVP may implement only transcript and supplied silence interval inputs, but
the data model should leave room for multimodal provenance metadata on each
operation.

## Why This Fits TigerCapture

The current TigerCapture spec already has the required building blocks:

- Timeline model, clips, trims, cuts, markers, zoom actors, subtitles, and
  undo/redo.
- Screen Studio-style Auto Polish with cursor sidecars, click rings, hotkey
  badges, auto zoom, and export parity.
- CapCut-style Creator Assist with edit recipes, caption beat plans, hook score
  plans, render-queue jobs, publish variants, and package handoff.
- Local ML routing through `app/local_ml.py`, including optional local Whisper
  and visual analysis.
- Subtitles, styled caption presets, typography actors, and render/export
  support.
- Live2D and Spine actor lanes, including timeline/export integration.
- Command Palette and right-dock workflow panels.
- QA Dashboard and deterministic helper/report style.

AI Text Editing should reuse these systems. It should not create a second
timeline engine.

## Core Principle

The LLM must not directly mutate the project or execute code.

AI/LLM output may only be treated as untrusted JSON data. The only accepted AI
output shape is validated `EditPlan` JSON using allowed operation types. AI
output must never contain or trigger direct Python, shell, plugin commands,
timeline object mutation, project-file mutation, render execution, or arbitrary
callback execution.

The required flow is:

```text
User command or transcript edit
-> local/cloud planner
-> JSON EditPlan
-> schema validation
-> deterministic planning helpers
-> preview/diff
-> user applies selected operations
-> normal timeline/project mutation with undo savepoint
```

The LLM proposes. TigerCapture validates and applies.

This protects:

- Undo/redo.
- Save/load stability.
- Preview/export parity.
- QA reproducibility.
- User trust.

Malformed plans, unknown operation types, unknown top-level fields, direct
execution fields, and direct project mutation fields must be rejected before
preview or apply.

## Main Use Scenarios

### Scenario 1: Clean Up A Screen-Recording Tutorial

User records a 12-minute Blender, Photoshop, product, or app tutorial.

Flow:

1. User records or imports video.
2. Script Edit creates or imports a transcript.
3. User enters:

   ```text
   Remove long silences and filler words, then make this feel like a clean tutorial.
   ```

4. Local LLM returns an `EditPlan`.
5. TigerCapture previews:

   - 23 silence removals.
   - 17 filler-word removals.
   - 8 cursor/interaction zooms.
   - 5 hotkey badges.
   - 6 chapter markers.
   - 74 styled captions.

6. User applies all or selected operations.
7. User exports a YouTube/tutorial version.

### Scenario 2: Create Shorts From Long Footage

User imports a 30-minute game devlog or commentary video.

Flow:

1. Transcript and local visual tags are generated.
2. User enters:

   ```text
   Find three good Shorts from this video.
   ```

3. The planner proposes candidates with reasons:

   - Bug/reaction moment.
   - Finished result reveal.
   - Before/after comparison.

4. TigerCapture creates review cards.
5. User chooses one or more candidates.
6. TigerCapture stages:

   - 9:16 reframe.
   - Hook title.
   - Styled captions.
   - Zoom/callouts.
   - Render Queue jobs.

### Scenario 3: Delete Text, Cut Video

User edits a transcript like a document.

Example transcript:

```text
00:01:12  Um... today I will explain material setup.
00:01:18  First, let's look at base color.
00:01:23  Wait, this is wrong. Let me restart.
00:01:28  Connect the base color node like this.
```

If the user deletes:

```text
Wait, this is wrong. Let me restart.
```

TigerCapture creates a ripple cut for that time range on the selected
video-linked-audio target.

The transcript is not the subtitle layer. It is an editable analysis document
that maps text ranges to source media time ranges.

### Scenario 4: Add Live2D/Spine Commentary

User imports gameplay or a rendered demo and adds a Live2D/Spine model.

Flow:

1. User enters:

   ```text
   Make this a game review. Let the character react at important moments.
   ```

2. The planner proposes:

   - Actor lane creation.
   - Short commentary lines.
   - Reaction timing.
   - Nameplate preset.
   - Dialogue subtitles.

3. User edits proposed dialogue text.
4. TigerCapture applies actor clips and subtitles.

This is a TigerCapture differentiator. General text-based editors do not
naturally combine transcript edits with Live2D/Spine actor lanes.

### Scenario 5: Finish External Render Output

User imports an external render output folder or manifest.

Flow:

1. TigerCapture builds the timeline from shots/renders.
2. User enters:

   ```text
   Turn this into a two-minute devlog. Add explanation captions and make one Short.
   ```

3. The planner proposes:

   - Shot order.
   - Chapter markers.
   - Explanation subtitle rows.
   - Before/after callouts.
   - Optional Live2D/Spine intro/outro.
   - YouTube and Shorts export jobs.

4. User applies the selected plan.

## Feature Surfaces

### Script Edit Panel

Right-dock panel for transcript and AI text-edit planning.

The panel should feel prompt-first, not like a subtitle utility.  The primary
entry point is an AI editing prompt such as "군더더기 빼고 자막 만들어줘" or
"쇼츠 후보 만들어줘".  When a local LLM is unavailable, the prompt is resolved
by a transparent local rule router into deterministic recipes such as
`clean_tutorial`, `shorts`, `product_demo`, or `transcript_to_captions`.

The main editor also exposes a compact bottom `AI Command` dock. The toolbar AI
button opens this dock instead of jumping directly to the right
Workbench/Inspector. It contains a visible `AI` badge, one-line prompt, `Plan`,
`Review`, pop-out, and hide controls. `Plan` now has two explicit paths:
clear timeline/editor commands such as "미디어 풀 영상을 타임라인에 올려",
"여기서 잘라", "마커 추가", or "2배속" are routed into the Python Action
Registry for dry-run review and execution; transcript, subtitle, cleanup,
shorts, and story prompts continue through Script Edit and validated `EditPlan`
review. The bottom dock can detach into a parented floating dialog and re-dock
without losing the current prompt or generated plan.

Suggested layout:

```text
Script Edit

[AI editing prompt]
Remove filler words and make this a clean tutorial.

[Transcript]
00:00:01 Today...
00:00:08 The important part is...
00:00:21 Um... let me explain again...

[Edit Plan Preview]
Delete: 12 ranges / 31.2 seconds
Captions: 48 rows
Zooms: 6 actors
Short candidates: 3
Render jobs: 2

[Preview Plan] [Apply Selected] [Apply All]
```

### Command Palette

Natural-language actions should also be available from `Ctrl+Shift+P`.

Example:

```text
Make captions and improve quiet dialogue.
```

Resolved plan:

- Generate transcript if missing.
- Create styled subtitles.
- Apply dialogue cleanup preset.
- Apply loudness target.

### Creator Assist

Creator Assist should consume the same `EditPlan` model for Shorts,
multi-platform publishing, hook scoring, caption beats, and render queue
handoff.

### Subtitles Panel

Subtitles remain output graphics. Transcript text edits can generate subtitle
rows, but transcript and subtitle data must stay separate.

## Data Model

### TranscriptDocument

Proposed shape:

```json
{
  "id": "transcript_001",
  "source_media_id": "media_001",
  "language": "ko",
  "created_by": "local_whisper",
  "segments": [
    {
      "id": "seg_001",
      "start_ms": 1200,
      "end_ms": 5800,
      "speaker": "speaker_1",
      "text": "Today we will explain material setup.",
      "words": [
        {
          "text": "Today",
          "start_ms": 1200,
          "end_ms": 1500,
          "confidence": 0.94
        }
      ]
    }
  ]
}
```

### EditPlan

The LLM, deterministic planners, and one-click recipes should produce an
`EditPlan`.

Example:

```json
{
  "id": "plan_001",
  "intent": "tighten_tutorial",
  "summary": "Remove pauses, remove filler words, add captions, and add cursor zooms.",
  "operations": [
    {
      "type": "remove_silence",
      "min_duration_ms": 900,
      "target": "selected_video_linked_audio"
    },
    {
      "type": "remove_filler_words",
      "words": ["음", "어", "그", "그러니까"],
      "target": "selected_video_linked_audio"
    },
    {
      "type": "add_captions",
      "style": "caption-capcut-word-pop"
    },
    {
      "type": "add_auto_zoom",
      "source": "cursor_events"
    }
  ],
  "warnings": [],
  "requires_review": true,
  "review_cards": [
    {
      "id": "card_cleanup",
      "title": "Cleanup",
      "operation_ids": ["op_001", "op_002"],
      "quality_score": 86,
      "reason": "Silence and filler cuts are deterministic but destructive."
    }
  ],
  "quality_score": 84,
  "metadata": {
    "recipe_mode": "one_click_reviewable",
    "plan_layering": ["recipe_intent", "deterministic_operations", "review_cards", "apply_later"],
    "llm_provider": "disabled"
  }
}
```

Review cards summarize groups of operations for user review. Quality scores are
not a permission to apply automatically. They are review signals that help rank
cards, expose weak assumptions, and drive QA checks.

### Operation Types

Initial operation set:

- `delete_time_range`
- `keep_time_range`
- `ripple_cut_text_range`
- `remove_silence`
- `remove_filler_words`
- `create_subtitles`
- `restyle_subtitles`
- `add_marker`
- `add_chapter_markers`
- `add_auto_zoom`
- `add_callout`
- `apply_preset`
- `create_short_candidate`
- `set_reframe`
- `add_render_queue_job`
- `add_live2d_dialogue`
- `add_spine_dialogue`
- `create_publish_package`

Every operation must be validated before execution.

Allowed operation types are the only bridge from AI Script or recipe planning
to later timeline apply code. New operation types require a spec update,
validator update, QA coverage, and a preview/apply implementation.

## Local LLM Integration

Local LLM support should be optional and externally hosted at first.

Supported provider candidates:

- Disabled.
- Ollama.
- LM Studio.
- llama.cpp server.
- Custom OpenAI-compatible endpoint.

TigerCapture should not auto-download models.

Configuration:

```text
Provider: Disabled / Ollama / LM Studio / Custom
Endpoint: http://localhost:11434
Model: user-selected
Privacy: local only
Auto download: off
```

Suggested modules:

```text
app/local_llm.py
app/ai_edit_plan.py
app/ai_text_editing.py
tools/qa_local_llm_backend.py
```

### Local LLM Responsibilities

Good uses:

- Parse natural-language edit commands.
- Summarize transcript chunks.
- Generate chapter titles.
- Suggest Shorts candidates from transcript and local visual tags.
- Rewrite captions for readability.
- Translate or localize subtitle text.
- Generate Live2D/Spine commentary lines.
- Explain why an edit is recommended.

Bad uses:

- Directly mutating project files.
- Directly editing timeline objects.
- Returning code, shell commands, Python snippets, plugin invocations, or
  callbacks for TigerCapture to execute.
- Rendering video.
- Performing frame-level object generation.
- Making irreversible changes without a preview.

### Chunking Strategy

Long transcripts should be processed in chunks:

```text
transcript chunks
-> chunk summaries
-> global summary
-> edit intent
-> EditPlan
```

This avoids context overflow and keeps slow local models usable.

## Transcript Sources

Supported sources:

- Local Whisper through `app/local_ml.py`, if installed.
- Imported `.srt`.
- Imported `.vtt`.
- Manually typed transcript rows.
- Future external transcript import.

Recipe and AI Script planners can also consume non-transcript context when it
is already local and deterministic: silence intervals, cursor sidecars, local
visual tags, selected presets, marker names, render targets, and project
duration. This context should be referenced in operation metadata rather than
copied into executable instructions.

Transcript generation should never block the editor UI. It should run as a
background job with progress/cancel state.

## Editing Semantics

### Transcript And Subtitle Separation

Transcript:

- Analysis/editing document.
- Maps words and segments to source time.
- Can be deleted/reordered to propose cuts.

Subtitles:

- Rendered output graphics.
- Carry style, placement, animation, and export behavior.
- Can be generated from transcript but remain independent afterward.

### Track Targeting

Text edits must not blindly cut every track.

Default target:

- Selected video clip and linked audio.

Alternative targets:

- Active video track.
- Active audio track.
- Whole project ripple.
- Transcript-only edit.

The target must be visible in the plan preview.

### Apply Behavior

Applying an edit plan should:

- Create one undo savepoint.
- Apply deterministic operations in a stable order.
- Preserve manual subtitles and markers unless the user chooses replacement.
- Rebuild preview caches.
- Refresh the current preview frame.
- Store plan metadata in the project sidecar for audit/reapply where useful.

## MVP Scope

MVP should avoid broad generative AI. The first useful version is transcript
editing plus deterministic plans.

MVP features:

1. Script Edit right-dock panel.
2. Transcript import from SRT/VTT.
3. Optional local Whisper transcript generation through existing local ML
   status.
4. Transcript click seeks preview/timeline.
5. Text selection creates a candidate cut range.
6. Delete transcript range creates a reviewed ripple cut operation.
7. Silence removal plan.
8. Filler-word removal plan for Korean and English starter dictionaries.
9. Transcript-to-styled-subtitles plan.
10. Natural-language command to `EditPlan` through the built-in local rule
    router, with optional local LLM/provider routing only when explicitly
    configured.
11. Edit Plan Preview with operation counts, affected duration, warnings, and
    Apply Selected / Apply All.
12. QA fixture for transcript-to-edit-plan determinism.
13. One-click recipe helpers for clean tutorial, Shorts, and product demo that
    return validated `EditPlan` objects.
14. Review cards and quality scores in plan output.
15. Malformed AI/LLM plan rejection, including direct code execution and direct
    project mutation fields.

## Phase 2

Creator-focused automation:

1. Shorts candidate recommendation.
2. Hook score cards.
3. Caption beat planning.
4. Social reframe suggestions.
5. Cursor/Auto Polish suggestions from transcript plus cursor sidecars.
6. Chapter marker generation.
7. Publish package copy: title, description, hashtags, thumbnail candidate
   explanations.
8. Command Palette natural-language route.

## Phase 3

TigerCapture-specific advanced workflows:

1. Live2D/Spine commentary planner.
2. Product/render-output devlog planner.
3. Multi-speaker podcast/interview cleanup.
4. Translation and bilingual subtitle workflows.
5. Semantic search across Media Pool and transcripts.
6. Timeline question answering:

   ```text
   Where do I explain material instances?
   ```

7. Optional cloud provider support behind explicit user configuration.

## Non-Goals

Do not start with:

- Prompt-to-video generation.
- Voice cloning or speech regeneration.
- Talking-head lip regeneration.
- Full Descript clone.
- Direct timeline mutation by LLM.
- Auto-download of local models.
- Cloud calls hidden behind "local" UI.
- Multi-user cloud document collaboration.

## Safety And Trust

Required UX:

- Show the generated plan before applying it.
- Show affected time ranges.
- Show target tracks.
- Show destructive operations separately.
- Allow operation-level selection.
- Keep undo one action per plan apply.
- Store warnings when local LLM output is incomplete or low-confidence.
- Never treat LLM output as trusted code or trusted project data.

## QA Plan

Suggested QA entry points:

```text
tools/qa_ai_text_editing.py
tools/qa_ai_script_edit_integration.py
tools/qa_local_llm_backend.py
```

QA should cover:

- SRT/VTT import.
- Transcript click-to-seek mapping.
- Text range to timeline range conversion.
- Filler-word detection for Korean and English.
- Silence removal threshold planning.
- EditPlan schema validation.
- Operation preview counts.
- Apply/revert via undo.
- Save/load of transcript and plan sidecar metadata.
- Caption generation parity.
- Render/export after transcript-generated cuts.
- Local LLM disabled path.
- Malformed LLM JSON recovery.
- One-click recipe plan validation.
- Deterministic serialization of transcripts and EditPlans.
- Rejection of code execution, shell command, and project mutation fields in
  AI/LLM plan output.

## Success Criteria

MVP is successful when:

- A user can import or generate a transcript for a screen recording.
- Clicking a transcript sentence seeks to the correct time.
- Deleting a transcript sentence proposes a timeline cut.
- The user can remove silences and filler words through a reviewed plan.
- The user can generate styled subtitles from transcript text.
- A natural-language command can create a valid `EditPlan`.
- The user can preview and apply selected operations with one undo savepoint.
- Existing timeline, subtitle, render queue, and export paths still work.

## Current Judgment

AI Text Editing is a strong fit for TigerCapture if it is framed as a planning
and review layer, not a magical auto-editor.

## 2026-06-23 MVP Integration Status

- `app/ai_script_edit_panel.py` adds the first Script Edit panel/model for SRT
  and VTT transcript import, prompt-first local rule routing, deterministic plan
  generation, plan summaries, warnings, review cards, operation selection, and
  apply requests.
- `app/ai_edit_apply.py` converts validated `EditPlan` operations into safe
  subtitle rows, marker/short/render sidecars, compatible auto-zoom payloads,
  and review-only cut intents for normal apply.
- `app/video_editor_window.py` now exposes the workflow through a compact bottom
  `AI Command` dock, detachable AI command dialog, and full right-dock Script
  Edit review panel. MVP apply can materialize subtitles, markers, compatible
  render jobs, and compatible auto-zoom sidecars; destructive text/range cuts
  stay review-only during normal apply and require the explicit reviewed-cut
  apply path.
- `app/ai_action_command.py` routes clear prompt commands into registered
  Python Actions before Script Edit fallback. The dedicated AI Action Review
  dialog shows dry-run results and executes only through the safe Action
  Registry, keeping chat/status prompts and subtitle requests out of accidental
  timeline mutations.
- `tools/qa_ai_script_edit_integration.py` writes
  `debugCapture/ai_script_edit_integration_qa.json` for deterministic panel and
  apply-helper coverage.

The first version should feel like:

```text
Transcript + command input + reviewed EditPlan + deterministic apply
```

The differentiated later version should feel like:

```text
Text commands that can control cuts, captions, cursor polish, Shorts,
Live2D/Spine commentary, and post-production packages.
```

This preserves TigerCapture's identity instead of copying generic text-based
editors.
