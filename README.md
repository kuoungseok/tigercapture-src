# Tiger Studio

**Tiger Studio is a local-first Windows creator studio for polished screen
recordings, timeline editing, reviewable AI editing, Motion Designer, Painter,
UI design/prototyping, anime/game actor workflows, AR/PBR material helpers,
Figma exchange, and supported Unreal UMG handoff.**

Tiger Studio records screenshots, GIFs, and MP4 screen captures, then continues
into a full local editor with Screen Studio-style polish, CapCut-style creator
assistance, professional color/audio foundations, node-based effects,
subtitles, render queue delivery, Live2D/Spine/MMD/VRM-oriented actor tracks,
production drawing, Texture Lab/PBR support, and optional local Voice Lab
workflows. Painter also includes a UI Design workspace for artboards,
components, tokens, responsive layout, local prototypes, Figma exchange, and
supported Unreal UMG delivery.

Korean: Tiger Studio는 화면 녹화, 영상 편집, AI 보조 편집, 모션 그래픽,
Painter, UI 디자인/프로토타입, 캐릭터 액터, PBR 텍스처 보조, Figma 교환,
Unreal UMG 전달 흐름을 하나의 로컬 Windows 제작 환경으로 묶는 크리에이터
스튜디오입니다.

**Made by** [artmouse (KyoungSeok Ko)](https://github.com/kuoungseok)

TigerCapture may still appear in repository paths, build files, and historical
release metadata while the product surface is being renamed to Tiger Studio.

---

## Current Product Focus

Tiger Studio is built for creators who need more than a recorder, but do not
want to jump between a heavy NLE, drawing app, actor preview tool, texture
utility, and game UI pipeline for every project.

| Focus | What it means |
|---|---|
| **Polished screen recordings** | Record or import a screen video, apply Auto Polish, add cursor/click/hotkey emphasis, trim, and export. |
| **Timeline studio** | Edit clips, subtitles, effects, zooms, color, audio, masks, transitions, and render jobs in one local project. |
| **Reviewable AI editing** | Use Creator Assist and Script Edit to plan captions, cleanup edits, short ranges, vertical reframes, render jobs, publish copy, and platform variants before safe apply. |
| **Motion Designer** | Build 2.5D editorial motion, typography, paper/collage effects, particles, generators, replicators, templates, and reusable interactive button components. |
| **Painter** | Create game concept art, character/prop/background art, texture paint-over, video paint-over, and AI study passes with editable strokes. |
| **UI design and prototyping** | Author artboards, components, tokens, responsive variants, local prototypes, HTML preview packages, Figma exchange, and supported Unreal UMG output from Painter UI Design. |
| **Actor workflows** | Add Live2D, Spine/NIKKE, MMD, and VRM/VSeeFace-oriented actor workflows as timeline tracks or Program Output sources, then preview and bake supported outputs. |
| **AR/PBR and Texture Lab** | Generate and preview supported PBR maps, place 3D object tracks, inspect material/environment payloads, and keep preview/export diagnostics visible. |
| **Unreal UMG handoff** | Package supported Motion Designer/Painter content through a provider-neutral Tiger UMG document and generate supported Widget Blueprint output. |
| **Local-first workflow** | Local OpenCV/Pillow analysis is enabled by default; optional Whisper, SAM, Demucs, ONNX Runtime, Ultralytics, Style-Bert-VITS2, and other tools are detected locally when installed. |

---

## Highlights

### Screen Recording and Auto Polish

- Screenshot, GIF, and MP4 capture modes.
- Windows Graphics Capture support for GPU-composited windows.
- Clean screen video plates with separate cursor sidecar metadata.
- Auto Polish for cursor smoothing, scaling, static-cursor hiding, click rings,
  release feedback, drag trails, hotkey badges, wallpaper padding, rounded
  screen corners, and shadow framing.
- Auto Zoom generation from cursor samples, clicks, dwell points, and
  long-recording rhythm.
- Editable zoom candidates with crop overrides, easing styles, motion blur
  intent, and timeline `ZoomActor` output.
- Simple Mode for the record/import -> polish -> trim -> export workflow while
  keeping Media Pool and Workbench available.
- Screen Studio-style export handoff with readiness summaries and local share
  manifests.

### Creator Assist

- Right-dock Creator Assist panel inside the main editor.
- Bottom `AI Command` dock for prompt-first edit planning, with a full Script
  Edit review panel when the user wants to inspect and selectively apply
  operations.
- Local media analysis for subject detection, scene ranges, tags, and smart
  media summaries.
- Auto-caption styling and Subtitle-compatible caption rows.
- Long-video-to-Shorts candidate planning.
- Subject-aware vertical reframe keyframes.
- Hook score plan, caption beat plan, title suggestions, hashtags,
  thumbnail-frame choices, and publish checklist rows.
- Multi-platform publish variants for Shorts, TikTok, and Reels style outputs.
- Partial apply toggles for subtitles, short markers, export/reframe settings,
  and render-queue staging.
- Safe AI edit-plan boundary: deterministic local rule planning by default,
  optional local/agent provider readiness, validation before mutation, and
  registered-command automation/MCP surfaces instead of arbitrary code
  execution.

### Timeline and Editing

| Feature | Details |
|---|---|
| **Timeline editing** | Cut, split, duplicate, ripple/roll/slip/slide style operations, fades, markers, speed segments, zoom actors, and nested/multitrack project state. |
| **Media Pool** | Import, thumbnailing, proxy/health state, relink support, actor QA badges, preset/template browsing, and actor/resource classification. |
| **Workbench** | Node graph effects, masks, clip FX stack, metadata, and contextual inspector workflows. |
| **Presets/Templates** | Effect, title, transition, caption, sticker, motion, color, audio, actor, Screen Studio-style, CapCut-style, and Motion template workflows. |
| **Render Queue** | Persistent queue, retry/cancel/history, diagnostics, render failure assistant, delivery presets, and export readiness checks. |
| **Project format** | `.tgp` project save/load with timeline, subtitles, markers, project settings, actor tracks, and workflow sidecars. |

### Motion Designer

- 2.5D camera controls for depth, FOV, camera position, roll, and parallax.
- Renderer-neutral Replicator metadata for line, grid, and radial arrangements,
  count, offset/radius, rotation, scale, opacity falloff, deterministic jitter,
  and seed.
- Procedural Generator layers for solid color, linear gradients, checkerboard,
  grid, deterministic noise, and radial rays.
- Track mattes, per-layer motion blur, typography animator automation,
  directional blur, displacement, corner pin, mesh warp, paper fold, and paper
  paste composites.
- Deterministic paper crumple/unfold effects with animated amount, crease
  density, sharpness, depth, residual wrinkle, and matching CPU/GPU output.
- Direction presets such as headline slam, paper reveal, cutout collage,
  editorial camera push, and beat-synced montage.
- Interactive button components with Normal, Hover, Pressed, Disabled, and
  Focused states, pointer/focus triggers, hit padding, transition duration, and
  deterministic preview/export behavior.
- Template gallery with production-rendered thumbnails, search/category
  filters, aspect-ratio variants, learning templates, photo-led Studio
  Originals, product/ad/education packages, logo reveal samples, and visible
  demonstration media across the built-in catalog.

### Painter

- Standalone production drawing workspace for game concept art, character art,
  props, backgrounds, texture paint-over, and video paint-over.
- Photoshop-style document workflow with layers, channels, paths, selections,
  masks, tool options, brush library, reference board, and 3D blockout guides.
- Native `.tspaint` document format for background pixels, ordered layers/masks,
  editable strokes, tablet channels, Material Paint, Wet Canvas state,
  selections, channels, Work Paths, references, brush/PBR settings, and 3D
  blockout scene data.
- Brush catalog with basic, drawing, ink, water media, airbrush, concept,
  texture, FX, and Pro Oils presets.
- Tablet pressure, X/Y tilt, barrel rotation, and tangential pressure channels
  preserved through live preview, editable strokes, undo/redo, clipboard,
  save/load, actions, GPU cache signatures, and PNG/PBR rendering.
- Wet Canvas v1 with editable layer-owned RGB exchange, Mix/Bleed/Pickup
  controls, deterministic drying state, Dry Now, Undo/Redo, and PNG parity.
- 3D Place modes for Cube, Sphere, Cylinder, Cone, Plane, and Arch with an
  Unreal-style XYZ gizmo, Z-up floor, lighting, shadows, fog, and depth
  diagnostics.
- Provider-neutral AI study workflow for reference analysis, region
  segmentation, underpaint, editable stroke generation, render comparison,
  refinement, quality reporting, and real Painter-window timelapse capture.

### Painter UI Design and Prototyping

- Three-column UI Design workspace with Pages and Layers on the left, artboards
  in the center, and properties, Components, Tokens, Motion delivery, Publish,
  and inspection in the right inspector.
- Artboards, frames, groups, buttons, image objects, component definitions,
  instances, variants, typed properties, tokens, variables, styles, layout grid
  styles, and `.tsuilib` local design-system packages.
- Deterministic Auto Layout with Horizontal/Vertical flow, padding, gap,
  alignment, Wrap, Fixed/Hug/Fill sizing, constraints, responsive overrides,
  themes, high-contrast preview, safe areas, guides, and layout diagnostics.
- Image placement supports PNG, WebP, JPEG, and BMP with Fit, Fill, Stretch,
  Tile, and optional 9-slice rendering.
- Prototype authoring supports flow start points, object connection handles,
  click/navigation interactions, overlay/state/variant/variable behavior,
  Smart Animate inspection, inline Play/Reset debugging, and self-contained
  HTML prototype export.
- Production UI packages cover PNG/WebP/SVG, density variants, object slices,
  trim/padding, 9-slice, texture atlases, resource hashes, object-anchored
  comments, named checkpoints, revision diff, and offline review packages.
- `Publish > Figma` exchanges editable frames, text, fills, images,
  constraints, Auto Layout, local components/instances, variables, tokens,
  prototype links, and supported effects through the official REST/plugin
  boundary without claiming proprietary `.fig` archive support.
- Painter UI output uses the shared TigerStudioUMG backend through
  `paint.ui.umg.*`; no Painter-specific Unreal plugin exists.

### Actor, VTuber, and AR/PBR Tracks

- Live2D and Spine clips live on dedicated actor tracks instead of normal video
  clips.
- Drag/click actions can add actor clips to the timeline.
- Double-clicking an actor clip opens the bound actor editor.
- Spine/NIKKE support covers JSON and binary `.skel` parsing, atlas
  dependencies, weighted/linked mesh risks, clipping, constraints, multi-page
  atlases, skins, slots, and animation sweeps.
- Live2D support covers `.model3.json`, moc/texture dependency checks,
  non-ASCII runtime path handling, expressions, motions, physics/pose/display
  metadata, and render QA.
- MMD support covers PMX/PMD actor tracks, VMD motion workflow, toon
  preview/export paths, and local corpus QA.
- VRM/VSeeFace-oriented workflows expose internal fallback paths for Program
  Output and optional external-sidecar diagnostics.
- AR/PBR object workflows cover GLB/FBX-style intake, material/environment
  payloads, GPU/packet/software preview-export paths, and HDR/shadow/reflection
  diagnostics.
- Actor overlays are baked into final videos as transparent overlays.

### Texture Lab, PBR, Figma, and Unreal UMG

- Texture Lab generates supported BaseColor, Normal, AO, Roughness, Metallic,
  Height, Cavity, Curvature, packed ORM/ARM, Unreal ORM, glTF MR, and optional
  Substrate-oriented F0/F90 mask plans.
- GPU material preview includes Height-driven parallax occlusion mapping with
  adjustable strength/depth/step controls.
- Painter can use the shared Texture Lab map cache for in-memory PBR preview
  and export without forcing repeated 4K PNG round trips.
- Motion Designer and Painter can package supported content through a
  provider-neutral Tiger UMG document.
- The TigerStudioUMG workflow installs or updates the project plugin, generates
  supported Widget Blueprint content, compiles it, validates the generated
  asset, and reports the result.
- Painter UI Design can also package Figma exchange artifacts and
  self-contained HTML prototypes for supported local-review workflows.
- Unsupported UMG content must be reported as native, UI Material,
  deterministic bake, or blocked preflight; it must not be silently omitted.

### Voice Lab and Subtitle TTS

- Voice Lab is an optional local TTS workflow, not a bundled cloud voice
  service.
- The current local provider target is a connected Style-Bert-VITS2 sidecar.
- `Subtitles -> Track` can synthesize project subtitle rows into WAV clips and
  place them on an aligned dialogue audio track when the sidecar is ready.
- Model Maker prepares local model folders and validates completed assets
  without importing the AGPL training engine into the closed editor process.
- Generated TTS media is written under `external/assets/tts/generated`; the
  optional TTS engine and user-trained models stay outside the source tree.

### Color, Audio, and VFX/Post Foundations

Tiger Studio is not a full Resolve/Fairlight/Fusion replacement, but it tracks
partial professional post-production coverage through Health and Professional
Readiness diagnostics.

| Area | Current capability |
|---|---|
| **Color management** | Rec.709, sRGB, Rec.2020 HDR PQ/HLG, P3-D65, ACEScg/ACEScct intent, optional OCIO config path, input/creative/output LUT slots, FFmpeg color metadata, and export consistency checks. |
| **Advanced color** | HDR-zone controls, log-wheel offsets, Hue vs Hue/Sat/Luma curves, Color Warper payloads, qualifier/window masks, grade-local LUTs, and preview/export RGB bake path. |
| **Scopes and QA** | Waveform, vectorscope, parade, histogram, luma IRE, HDR nits estimate, clipping, gamut risk, skin-tone diagnostics, and ffprobe color metadata comparison. |
| **Audio workflow** | Timeline audio lanes, Sound Editor, AI Master presets, vocal/music separation with Demucs or FFmpeg mid/side fallback, LUFS display, true-peak/stereo warnings, routing payloads, sends, and loudness delivery checks. |
| **Masks/VFX repair** | SAM click-to-mask, GrabCut, arbitrary-region CSRT tracking, HSL qualifier, power windows, B-spline roto payloads, clean-plate bounds, planar-tracker intent, chroma key, stabilization, and background removal. |
| **Professional readiness** | Health and export preflight report long-project stability, GPU preview/export consistency, timeline integrity, color workflow depth, audio mix readiness, preset/template health, and Resolve/Fairlight/Fusion parity gaps. |

### Export, QA, and Performance

- MP4, WebM, and MOV export paths.
- 1080p, 4K, vertical, square, and roundtrip-style delivery presets.
- HDR10 passthrough path for supported exports.
- Raw pre-render fallback for preview-only effects that cannot be expressed
  safely in FFmpeg.
- Preview/export parity coverage for node graphs, masks, tracked masks, clip
  effects, nested sequences, typography, Spine, Live2D, chroma key, background
  removal, stabilizer, audio tracks, and color metadata.
- Color/Audio accuracy QA for LUT metadata, scopes, LUFS, true peak, stereo
  correlation, and dialogue cleanup.
- Actor compatibility/render QA for Live2D and Spine resources.
- Crash recovery, autosave, relink, startup trace, product QA dashboard, and
  public positioning QA support.
- Preview performance uses measured fast paths: OpenCV-native chroma key
  operations, optimized video filters, frame-cache decoding, GL/native Spine
  rendering, preview downsample paths, optional FFmpeg frame-server comparison,
  and optional native worker probes.

---

## Competitive Position

Tiger Studio is not trying to replace every professional editor. Its strongest
position is the intersection of polished screen recordings, local creator
assistance, anime/game actor workflows, production drawing, UI design,
Motion Designer, PBR helpers, Figma exchange, and Unreal UI handoff.

Current local QA snapshot as of 2026-07-31:

- Final Product Readiness: 99/100, with release still blocked by real broadcast
  platform evidence.
- Screen Studio-style interaction polish: claim-ready for the measured local
  interaction corpus.
- Descript-lite Readiness: 88/100, claim-ready for scoped AI script-edit value.
- NLE Readiness: 91/100, but not a Premiere/Resolve-class professional NLE
  until the real long-project corpus gate clears.
- CapCut Parity Next: 89.38/100, with cloud/mobile/collaboration still the
  largest gap.
- Broadcast Readiness: 95/100 alpha-ready, not commercial broadcast-ready.
- Latest documentation slice: Motion generators/templates/trend templates plus
  Painter UI Auto Layout, Figma exchange, Unreal UMG, and prototype export
  tests passed locally.

| Compared with | Tiger Studio position |
|---|---|
| **Screen Studio** | Screen Studio-style recording polish is a close scoped claim: cursor sidecars, click/drag/hotkey metadata, Auto Polish, zoom planning, and export handoff are evidence-backed for the measured corpus. Screen Studio remains simpler and more product-finished. |
| **CapCut** | Creator Assist covers captions, Shorts planning, vertical reframe, publish packages, render handoff, mobile-safe templates, and local asset packs. CapCut still wins on mobile/cloud collaboration, huge social/template scale, and trend ecosystem depth. |
| **Camtasia** | Strong overlap for tutorials and product demos. Tiger Studio adds local ML planning, actor overlays, Painter, and Motion Designer; Camtasia still has mature education/business trust. |
| **Descript** | Descript-lite positioning is evidence-backed for transcript planning, reviewed safe apply, cleanup, speech-enhance contracts, and sentence-level voice replacement contracts. Descript still wins on hosted collaboration, provider-direct coediting, share links, comments, version history, and team workspaces. |
| **Figma** | Painter UI Design now overlaps with artboards, components, Auto Layout, variables/tokens, local prototypes, comments, and Figma exchange. Figma still wins on real-time collaboration, mature design systems, community assets, browser-native review, Dev Mode, and platform trust. |
| **Rive** | Motion Designer and Painter prototype flows can author interactive states and motion handoff, but Rive remains stronger for runtime state machines, interactive animation runtimes, and app-embedded vector animation. |
| **Live2D / Spine tools** | Tiger Studio treats supported Live2D, Spine, MMD, and VRM-style assets as timeline actors and exportable overlays. It is not a Cubism, Spine Editor, or MMD authoring replacement. |
| **Clip Studio / Photoshop / Krita / Corel Painter** | Painter is now a scoped production drawing workspace with native documents, editable brushes, pressure/tilt, Wet Canvas v1, 3D blockout, and AI study automation. It is not a full replacement for mature dedicated paint packages. |
| **Substance / Marmoset / Blender** | Texture Lab and PBR workflows help generate maps, preview materials, and hand off supported data. They are not full mesh texturing, baking, lookdev, or DCC replacements. |
| **OBS** | Program Output recording/RTMP foundations and an optional OBS bridge exist, but OBS is still stronger for live streaming, scenes, plugins, and production broadcast ecosystems. |
| **Premiere / Resolve / Final Cut Pro** | Tiger Studio has a stronger NLE foundation with Source/Record, 3-point edit, Final Cut-style storyline, multicam, proxy, conform, and project-bin action surfaces. It is still not a Premiere/Resolve/Final Cut-class professional NLE until real long-project evidence clears. |
| **PowerPoint / presentation tools** | Tiger Studio can author timeline-native decks and export PPTX, PDF, or MP4 presentation videos. It should not be positioned as a full PowerPoint replacement or enterprise presentation collaboration tool. |
| **Unreal UI workflows** | Tiger Studio can generate supported UMG output through its project plugin path, including verified checkout-style Painter UI output. Unreal remains the runtime/editor authority; Tiger is the local authoring and handoff tool for supported UI content. |

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | PySide6 / Qt 6, Fusion style, OpenGL preview |
| Capture | Windows Graphics Capture, FFmpeg pipe encoding |
| Preview | OpenCV, NumPy, PySide6, OpenGL paths, prefetch/proxy/frame-server options |
| Export | FFmpeg subprocess, raw pre-render fallback for parity-sensitive effects |
| Color | CPU RGB pipeline, LUTs, optional PyOpenColorIO bridge, FFmpeg color metadata |
| Audio | Qt playback, FFmpeg audio graph, LUFS/true-peak helpers, Demucs optional |
| Painter | Qt canvas, editable stroke model, `.tspaint`, tablet channels, Wet Canvas v1, optional OpenGL-backed previews |
| UI Design | Painter UI document model, artboards, components, Auto Layout, variables/tokens, prototypes, `.tsuilib`, HTML preview, Figma exchange |
| Motion | Motion Designer render graph, 2.5D metadata, generators, replicators, templates, interactive button components |
| Texture/PBR | Texture Lab map generation, GPU material preview, Height/POM preview, shared Painter PBR actions |
| Unreal UMG | Provider-neutral Tiger UMG document, TigerStudioUMG project plugin, Widget Blueprint generation for supported Motion/Painter UI content |
| Voice Lab | Optional external Style-Bert-VITS2 sidecar, FastAPI `/voice` endpoint, generated WAV media |
| Local ML | OpenCV/Pillow baseline analysis, optional Whisper/SAM/Demucs/ONNX/Ultralytics |
| Actors | In-app Live2D runtime path, Spine parser/renderers, MMD/VRM-oriented workflows, OpenGL/software fallback |
| Native worker | Optional Rust JSON-lines subprocess for probing, thumbnails, waveform, and spectrum generation |
| Packaging | PyInstaller, Windows installer scripts |

---

## Requirements

- Windows 10 / 11, 64-bit.
- Python 3.11+ when running from source.
- FFmpeg available through the packaged app or development environment.
- GPU recommended for smoother preview, OpenGL actor rendering, Painter 3D
  blockout, Texture Lab preview, and larger projects.
- Optional local tools/models for advanced AI workflows: Whisper, SAM, Demucs,
  ONNX Runtime, Ultralytics, MediaPipe/rembg depending on feature use.
- Optional local Voice Lab workflow: connect an existing Style-Bert-VITS2
  sidecar and local voice models when subtitle-to-voice generation is needed.
  Tiger Studio does not bundle that AGPL engine into the closed editor build.
- Optional Unreal UMG workflow: Unreal Engine 5.8 project access is required
  when generating supported Widget Blueprint output.
- Optional Figma exchange workflow: a Figma file key or exported REST JSON is
  required for import; export creates a local development-plugin package for
  supported editable reconstruction.

---

## AI Editing Process Demo

The current demo shows Tiger Studio building a multi-track edit: importing
media, cutting on the timeline, layering inserts, opening the node graph,
adjusting color and blur parameters, using split compare, and playing the
finished edit to the closing shot.

Korean: 현재 데모는 Tiger Studio가 여러 미디어를 가져와 타임라인에 배치하고,
컷 편집, 인서트 레이어, 노드 그래프, 컬러/블러 조정, 분할 비교, 최종 재생까지
이어가는 과정을 보여줍니다.

<video src="resources/branding/captures/tigerstudio_ai_full_process_demo.mp4" controls poster="resources/branding/captures/tigerstudio_ai_full_process_demo_poster.png" width="100%"></video>

[Download the demo MP4](resources/branding/captures/tigerstudio_ai_full_process_demo.mp4)

---

## Download

**Not yet.** Public Windows downloads are temporarily paused while the current
build is being validated for packaging, signing, source-free distribution, and
release-readiness gates.

## Installation

Public installer downloads are not open yet. When the public build is ready,
this page will point to a packaged Windows executable or installer instead of
source archives.

Source code is private. Public release pages should provide binaries,
installers, release notes, and documentation, not source archives.

---

## Development Notes

The source tree is private. Public users should install Tiger Studio from the
released Windows installer or packaged executable.

For private development builds, the project can be run with the local Python
environment and helper batch files in the repository root.

Studio-wide AI/MCP automation is planned around a registered Python Action
System, not arbitrary Python execution. The design target and action catalog are
tracked in `docs/SPEC_PYTHON_ACTION_SYSTEM.md`.

---

## Building

Private release builds use PyInstaller plus the Windows installer scripts in
this repository, including the optional native worker and source-free bundled
Unreal plugin artifacts when available. Release builds should be validated with
project QA, professional readiness, export parity, actor corpus, Screen
Studio-style polish, color/audio checks, public positioning QA, packaging QA,
and the relevant Unreal UMG evidence before publishing.

---

## License

All rights reserved. Source code is private. Binaries are provided for personal
use unless a separate license says otherwise.
