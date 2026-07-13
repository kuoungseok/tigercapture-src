# TigerCapture

**TigerCapture is a local-first Windows creator studio for polished screen recordings, reviewable AI editing, actor overlays, AR/PBR compositing, optional local Voice Lab TTS, and alpha VTuber/Broadcast workflows.**

TigerCapture records screenshots, GIFs, and MP4 screen captures, then opens them in a full editor with Screen Studio-style polish, CapCut-style creator assistance, professional color/audio foundations, node-based effects, subtitles, render queue delivery, Live2D/Spine/MMD actor tracks, AR/PBR 3D object compositing, optional local subtitle-to-voice generation, and VTuber/Broadcast Program Output foundations.

Korean: TigerCapture는 화면 녹화와 가져온 영상을 로컬 편집 세션으로 이어서, 화면 녹화 보정, 검토 가능한 AI 편집, 배우/캐릭터 오버레이, AR/PBR 합성, 로컬 음성 생성, 렌더 큐까지 한 흐름에서 다루는 Windows 크리에이터 스튜디오입니다.

**Made by** [artmouse (KyoungSeok Ko)](https://github.com/kuoungseok)

---

## Current Product Focus

TigerCapture is designed for creators who need more than a recorder, but do not want a heavy broadcast/post-production suite for every screen video.

| Focus | What it means |
|---|---|
| **Polished screen recordings** | Record or import a screen video, apply Auto Polish, add cursor/click/hotkey emphasis, trim, and export. |
| **Reviewable AI editing** | Use Creator Assist and Script Edit to plan captions, cleanup edits, short ranges, vertical reframes, render jobs, publish copy, and platform variants before safe apply. |
| **Local-first workflow** | Local OpenCV/Pillow analysis is enabled by default; optional Whisper, SAM, Demucs, ONNX Runtime, and Ultralytics are detected locally. No cloud API is required by the core workflow and models are not auto-downloaded. |
| **Actor and VTuber overlays** | Add Live2D, Spine/NIKKE, MMD, and VRM/VSeeFace-oriented actor workflows as timeline tracks or Program Output sources, then preview and bake supported outputs. |
| **Voice Lab and creator audio** | Optional local Style-Bert-VITS2 sidecar support can turn subtitle rows into aligned dialogue audio, prefer the user's `zoe` model when present, and expose a Model Maker bridge for additional local voice models without bundling the AGPL engine into TigerCapture. |
| **AR/PBR compositing** | Place 3D object tracks with material, HDR environment, shadow/reflection, and preview/export parity diagnostics without claiming to replace a full 3D DCC or game engine. |
| **Creator-grade post tools** | Color management, LUTs, advanced color payloads, audio routing/loudness helpers, masks, rotoscope, keying, and render diagnostics are exposed without hiding the fast screen-recording path. |
| **Measured performance path** | Preview/cache bottlenecks are profiled first, then moved selectively into OpenCV, OpenGL, FFmpeg, proxy, or the optional Rust worker path. |

---

## Highlights

### Screen Recording and Auto Polish

- Screenshot, GIF, and MP4 capture modes.
- Windows Graphics Capture support for GPU-composited windows.
- Clean screen video plates with separate cursor sidecar metadata.
- Auto Polish for cursor smoothing, scaling, static-cursor hiding, click rings, release feedback, drag trails, hotkey badges, wallpaper padding, rounded screen corners, and shadow framing.
- Auto Zoom generation from cursor samples, clicks, dwell points, and long-recording rhythm.
- Editable zoom candidates with crop overrides, easing styles, motion blur intent, and timeline `ZoomActor` output.
- Simple Mode for the record/import -> polish -> trim -> export workflow while keeping Media Pool and Workbench available.
- Screen Studio-style export handoff with readiness summaries and local share manifests.

### Creator Assist

- Right-dock Creator Assist panel inside the main editor.
- Bottom `AI Command` dock for prompt-first edit planning, with a full Script Edit
  review panel when the user wants to inspect and selectively apply operations.
- Local media analysis for subject detection, scene ranges, tags, and smart media summaries.
- Auto-caption styling and Subtitle-compatible caption rows.
- Long-video-to-Shorts candidate planning.
- Subject-aware vertical reframe keyframes.
- Hook score plan, caption beat plan, title suggestions, hashtags, thumbnail-frame choices, and publish checklist rows.
- Multi-platform publish variants for Shorts, TikTok, and Reels style outputs.
- Partial apply toggles for subtitles, short markers, export/reframe settings, and render-queue staging.
- Render Queue handoff without opening the batch-export folder dialog.
- Safe AI edit-plan boundary: deterministic local rule planning by default,
  optional local/agent provider readiness, validation before mutation, and
  registered-command automation/MCP surfaces instead of arbitrary code execution.

### Voice Lab and Subtitle TTS

- Voice Lab is an optional local TTS workflow, not a bundled cloud voice service.
- The current local provider target is a connected Style-Bert-VITS2 sidecar.
- `Subtitles -> Track` can synthesize project subtitle rows into WAV clips and place them on an aligned dialogue audio track.
- If the connected sidecar install is valid but the FastAPI server is offline, the generation path and QA preflight can start `server_fastapi.py` and wait for readiness before synthesis.
- When multiple local models are detected, TigerCapture currently prefers the user's trained `zoe` model by default.
- Model Maker prepares `Data/<model>/raw`, opens the upstream Dataset and Train UIs, and validates completed `model_assets/<model>` folders without importing the AGPL training engine into the closed editor process.
- Generated TTS media is written under `external/assets/tts/generated`; the optional TTS engine and user-trained models stay outside the source tree.

### Timeline and Editing

| Feature | Details |
|---|---|
| **Timeline editing** | Cut, split, duplicate, ripple/roll/slip/slide style operations, fades, markers, speed segments, and zoom actors. |
| **Media Pool** | Import, thumbnailing, proxy/health state, relink support, actor QA badges, preset/template browsing. |
| **Workbench** | Node graph effects, masks, clip FX stack, metadata, and contextual inspector workflows. |
| **Presets/Templates** | Effect, title, transition, caption, sticker, motion, color, audio, actor, Screen Studio-style, and CapCut-style workflow presets. |
| **Render Queue** | Persistent queue, retry/cancel/history, diagnostics, render failure assistant, delivery presets, and export readiness checks. |
| **Project format** | `.tgp` project save/load with timeline, subtitles, markers, project settings, actor tracks, and workflow sidecars. |

### Actor, VTuber, and AR/PBR Tracks

- Live2D and Spine clips live on dedicated actor tracks instead of normal video clips.
- Drag/click actions can add actor clips to the timeline.
- Double-clicking an actor clip opens the bound actor editor.
- Spine/NIKKE support covers JSON and binary `.skel` parsing, atlas dependencies, weighted/linked mesh risks, clipping, constraints, multi-page atlases, skins, slots, and animation sweeps.
- Live2D support covers `.model3.json`, moc/texture dependency checks, non-ASCII runtime path handling, expressions, motions, physics/pose/display metadata, and render QA.
- MMD support covers PMX/PMD actor tracks, VMD motion workflow, toon preview/export paths, and local corpus QA; it does not claim native MMD/Bullet parity or universal PMX compatibility.
- AR/PBR object workflows cover GLB/FBX-style intake, material/environment payloads, GPU/packet/software preview-export paths, and HDR/shadow/reflection diagnostics.
- VTuber/Broadcast workflows expose Program Output recording/RTMP foundations, an optional OBS bridge, and VRM/VSeeFace bridge diagnostics as alpha/beta capabilities.
- Actor overlays are baked into final videos as transparent overlays.
- Local corpus QA validates actor sample sets and top-risk golden baselines on the development workstation, but public copy must stay tied to current QA evidence.

### Color, Audio, and VFX/Post Foundations

TigerCapture is not a full Resolve/Fairlight/Fusion replacement, but it now tracks partial professional post-production coverage through Health and Professional Readiness diagnostics.

| Area | Current capability |
|---|---|
| **Color management** | Rec.709, sRGB, Rec.2020 HDR PQ/HLG, P3-D65, ACEScg/ACEScct intent, optional OCIO config path, input/creative/output LUT slots, FFmpeg color metadata, and export consistency checks. |
| **Advanced color** | HDR-zone controls, log-wheel offsets, Hue vs Hue/Sat/Luma curves, Color Warper payloads, qualifier/window masks, grade-local LUTs, and preview/export RGB bake path. |
| **Scopes and QA** | Waveform, vectorscope, parade, histogram, luma IRE, HDR nits estimate, clipping, gamut risk, skin-tone diagnostics, and ffprobe color metadata comparison. |
| **Audio workflow** | Timeline audio lanes, Sound Editor, AI Master presets, vocal/music separation with Demucs or FFmpeg mid/side fallback, LUFS display, true-peak/stereo warnings, routing payloads, sends, and loudness delivery checks. |
| **Voice Lab** | Optional local subtitle-to-voice generation, Voice Lab sidecar readiness checks, `zoe` default-model preference when available, Model Maker bridge, and actor lip-sync timing from subtitle/TTS clips. |
| **Masks/VFX repair** | SAM click-to-mask, GrabCut, arbitrary-region CSRT tracking, HSL qualifier, power windows, B-spline roto payloads, clean-plate bounds, planar-tracker intent, chroma key, stabilization, and background removal. |
| **Professional readiness** | Health and export preflight report long-project stability, GPU preview/export consistency, timeline integrity, color workflow depth, audio mix readiness, preset/template health, and Resolve/Fairlight/Fusion parity gaps. |

### Export and QA

- MP4, WebM, and MOV export paths.
- 1080p, 4K, vertical, square, and roundtrip-style delivery presets.
- HDR10 passthrough path for supported exports.
- Raw pre-render fallback for preview-only effects that cannot be expressed safely in FFmpeg.
- Preview/export parity coverage for node graphs, masks, tracked masks, clip effects, nested sequences, typography, Spine, Live2D, chroma key, background removal, stabilizer, audio tracks, and color metadata.
- Color/Audio accuracy QA for LUT metadata, scopes, LUFS, true peak, stereo correlation, and dialogue cleanup.
- Actor compatibility/render QA for Live2D and Spine resources.
- Crash recovery, autosave, relink, startup trace, and product QA dashboard support.

### Performance, Health, and Native Worker

- Health Center summarizes crash status, QA failures, render queue failures/cancellations, current project media/proxy issues, and actor QA risk rows.
- Project QA / Professional Readiness reports long-project stability, GPU preview/export consistency, timeline integrity, color workflow depth, audio mix readiness, preset/template health, and advisory Resolve/Fairlight/Fusion parity scores.
- High-resolution proxy management is visible in the editor toolbar, with Original/Building/Ready/Stale/Active states and Media Pool proxy badges.
- Preview performance uses measured fast paths: OpenCV-native chroma key operations, optimized video filters, frame-cache decoding, GL/native Spine rendering, preview downsample paths, and optional FFmpeg frame-server comparison.
- Current preview evidence is split intentionally: `debugCapture/preview_perf_report.json` supports measured steady playback/performance work, and `debugCapture/preview_scrub_readiness_qa.json` now supports current-corpus scrub readiness under strict clean-cache measurement. Universal no-latency claims across every codec, machine, and project remain out of scope.
- The optional Rust worker in `native/tigercapture_worker` uses a JSON-lines protocol and can handle media probing, timeline thumbnails, audio waveform, and audio spectrum generation.
- Python/OpenCV/FFmpeg paths remain the fallback when the native worker is missing, incompatible, or disabled.

---

## Competitive Position

TigerCapture is not trying to replace every professional editor. Its strongest position is the intersection of polished screen recording, local creator assistance, and actor overlays.

Current local QA snapshot as of 2026-07-11:

- Final Product Readiness: 99/100, with release still blocked by real broadcast
  platform evidence.
- Screen Studio-style interaction polish: claim-ready for the measured local
  interaction corpus.
- Descript-lite Readiness: 88/100, claim-ready for scoped AI script-edit value.
- NLE Readiness: 91/100, but not a Premiere/Resolve-class professional NLE
  until the real long-project corpus gate clears.
- CapCut Parity Next: 89.38/100, with cloud/mobile/collaboration still the
  largest gap.
- Voice Lab Sidecar QA: ready on the local reference install with 7 detected
  models including `zoe`; the QA Dashboard runs the sidecar preflight with
  auto-start for project evaluation sessions.
- Broadcast Readiness: 95/100 alpha-ready, not commercial broadcast-ready.

| Compared with | TigerCapture position |
|---|---|
| **Screen Studio** | Screen Studio-style recording polish is now the closest competitive claim: cursor sidecars, click/drag/hotkey metadata, Auto Polish, zoom planning, and export handoff are evidence-backed for the measured corpus. Screen Studio remains simpler and more product-finished. |
| **CapCut** | Creator Assist covers captions, Shorts planning, vertical reframe, publish packages, render handoff, mobile-safe templates, and local asset packs. CapCut still wins on mobile/cloud collaboration, huge social/template scale, and trend ecosystem depth. |
| **Camtasia** | Strong overlap for tutorials and product demos. TigerCapture adds local ML planning and Live2D/Spine overlays; Camtasia still has mature education/business trust. |
| **Descript** | Descript-lite positioning is now evidence-backed for transcript planning, reviewed safe apply, cleanup, speech-enhance contracts, and sentence-level voice replacement contracts. Descript still wins on hosted collaboration, provider-direct coediting, share links, comments, version history, and team workspaces. |
| **Local TTS / voice tools** | Voice Lab can connect to a local Style-Bert-VITS2 sidecar for subtitle-to-voice generation and local model registration. It should be described as an optional local sidecar workflow, not a hosted TTS platform or universal voice-cloning product. |
| **OBS** | Program Output recording/RTMP foundations and an optional OBS bridge exist, but OBS is still stronger for live streaming, scenes, plugins, and production broadcast ecosystems. |
| **Premiere / Resolve / Final Cut Pro** | TigerCapture now has a stronger NLE foundation with Source/Record, 3-point edit, Final Cut-style storyline, multicam, proxy, conform, and project-bin action surfaces. It is still not a Premiere/Resolve/Final Cut-class professional NLE until real long-project evidence clears. |
| **PowerPoint / presentation tools** | TigerCapture can author timeline-native decks and export PPTX, PDF, or MP4 presentation videos. It should not be positioned as a full PowerPoint replacement or enterprise presentation collaboration tool. |

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | PySide6 / Qt 6, Fusion style, OpenGL preview |
| Capture | Windows Graphics Capture, ffmpeg pipe encoding |
| Preview | OpenCV, NumPy, PySide6, OpenGL paths, prefetch/proxy/frame-server options |
| Export | FFmpeg subprocess, raw pre-render fallback for parity-sensitive effects |
| Color | CPU RGB pipeline, LUTs, optional PyOpenColorIO bridge, FFmpeg color metadata |
| Audio | Qt playback, FFmpeg audio graph, LUFS/true-peak helpers, Demucs optional |
| Voice Lab | Optional external Style-Bert-VITS2 sidecar, FastAPI `/voice` endpoint, generated WAV media |
| Local ML | OpenCV/Pillow baseline analysis, optional Whisper/SAM/Demucs/ONNX/Ultralytics |
| Actors | In-app Live2D runtime path, Spine parser/renderers, OpenGL/software fallback |
| Native worker | Optional Rust JSON-lines subprocess for probing, thumbnails, waveform, and spectrum generation |
| Packaging | PyInstaller, Windows installer scripts |

---

## Requirements

- Windows 10 / 11, 64-bit.
- Python 3.11+ when running from source.
- FFmpeg available through the packaged app or development environment.
- GPU recommended for smoother preview, OpenGL actor rendering, and larger projects.
- Optional local tools/models for advanced AI workflows: Whisper, SAM, Demucs, ONNX Runtime, Ultralytics, MediaPipe/rembg depending on feature use.
- Optional local Voice Lab workflow: connect an existing Style-Bert-VITS2 sidecar and local voice models when subtitle-to-voice generation is needed. TigerCapture does not bundle that AGPL engine into the closed editor build.

---

## AI Editing Process Demo

The current demo shows Tiger Studio building a multi-track edit: importing media,
cutting on the timeline, layering inserts, opening the node graph, adjusting
color and blur parameters, using split compare, and playing the finished edit to
the closing shot.

Korean: AI가 여러 영상 클립을 불러와 타임라인에 배치하고, 컷/전환/속도/노드
이펙트/컬러 그레이딩/블러/스플릿 비교를 거쳐 완성 장면까지 재생하는 과정을
보여주는 데모입니다.

<video src="resources/branding/captures/tigerstudio_ai_full_process_demo.mp4" controls poster="resources/branding/captures/tigerstudio_ai_full_process_demo_poster.png" width="100%"></video>

[Download the demo MP4](resources/branding/captures/tigerstudio_ai_full_process_demo.mp4)

---

## Download

**Not yet.** Public Windows downloads are temporarily paused while the current
build is being validated for packaging, signing, and release-readiness gates.

## Installation

Public installer downloads are not open yet. When the public build is ready,
this page will point to a packaged Windows executable or installer instead of
source archives.

Source code is private. Public release pages should provide binaries/installers and documentation, not source archives.

---

## Development Notes

The source tree is private. Public users should install TigerCapture from the released Windows installer or packaged executable.

For private development builds, the project can be run with the local Python environment and helper batch files in the repository root.

Studio-wide AI/MCP automation is planned around a registered Python Action
System, not arbitrary Python execution. The design target and action catalog are
tracked in `docs/SPEC_PYTHON_ACTION_SYSTEM.md`.

---

## Building

Private release builds use PyInstaller plus the Windows installer scripts in this repository, including the optional native worker when available. Release builds should be validated with project QA, professional readiness, export parity, actor corpus, Screen Studio polish, and color/audio checks before publishing.

---

## License

All rights reserved. Source code is private. Binaries are provided for personal use unless a separate license says otherwise.
