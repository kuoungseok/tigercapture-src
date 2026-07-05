# TigerCapture Release Positioning Guardrails

Last updated: 2026-07-05

This document is the public-claim guardrail for README, website, release notes,
pricing copy, and store text. It separates implemented behavior from parity
goals so product copy does not overclaim.

## Safe Positioning

- TigerCapture is a local-first Windows creator studio for polished screen
  recordings, creator-assist planning, Live2D/Spine/MMD actor overlays, and
  AR/PBR 3D compositing.
- Screen Studio comparison: "Screen Studio-inspired polish" or "similar polish
  direction" is acceptable. Do not claim full Screen Studio parity until the
  real recording corpus is interaction-ready.
- CapCut comparison: "CapCut-style creator assist" is acceptable for captions,
  Shorts planning, vertical reframe, publish package, and render handoff. Do not
  claim CapCut-scale template/AI ecosystem depth.
- Descript comparison: TigerCapture has an AI Script Edit workflow for
  transcript planning, review, safe apply, and local word-timestamp
  transcription. Descript-lite is currently claimable only in the gated
  priorities 1-3 sense; do not claim full Descript replacement, Studio
  Sound-class regeneration, voice replacement, or collaboration parity.
- Resolve/Fairlight/Fusion comparison: use "creator-grade professional
  foundations", "partial professional workflow", or "readiness diagnostics".
  Do not call TigerCapture a replacement for full professional color, DAW, VFX,
  collaboration, plugin, or hardware-console ecosystems.
- Professional NLE comparison: use "core NLE workflow/action surface" or "NLE
  readiness diagnostics". The current NLE readiness report is 79/100 with
  `professional_nle_claim_ok=false`, so Premiere/Resolve-class professional NLE
  claims remain blocked until real long-project footage, dedicated source/record
  and live multicam UI polish, and deeper conform/bin/proxy workflows are
  proven. Register real projects with
  `tools/register_nle_real_project.py` and validate them with
  `tools/qa_nle_real_project_corpus.py`; generated stress fixtures must not
  clear the real-world NLE corpus gate.
- Live2D/Spine comparison: say "large-corpus QA and actor-track support", not
  "all game resources compatible".
- MMD comparison: say "PMX/PMD + VMD actor timeline, preview, and export
  support" or "MMD actor workflow". Do not claim native MMD/Bullet parity,
  universal PMX compatibility, or perfect physics until native reference
  captures prove it.
- AR/PBR comparison: say "AR/PBR 3D object compositing" or "real-time 3D
  overlay workflow". Do not claim Marmoset, Blender, game-engine, or full 3D
  renderer replacement. Keep renderer claims tied to the current QA artifacts.
- VTuber/Broadcast comparison: say "OBS-free Program Output recording/RTMP
  foundation with optional OBS bridge" only as an alpha/beta capability. Do not
  claim OBS replacement, production broadcast suite, or commercial live
  streaming readiness.
- External engine bridge claims are out of scope for public positioning. Do not
  mention unsupported game-engine project/asset import in README, website,
  pricing, release notes, or store text.

## Current Evidence Snapshot

Latest local QA evidence as of 2026-07-05:

| Gate | Current Result | Public Meaning |
|---|---:|---|
| Final Product Readiness | 99/100, `release_ready=false` | Screen Studio interaction, AI corpus, and Claude direct smart-edit gates now pass; commercial broadcast platform evidence still blocks full release-ready claims. |
| Preview Performance | `preview_perf_report.json` present, preview/GPU score 100 | Measured steady preview work is claimable with caveats. |
| Preview Scrub Readiness | 92/100, `release_scrub_claim_ready=true` | Current-corpus scrub readiness is claimable under strict clean-cache measurement; universal no-latency claims remain blocked. |
| AI Edit Corpus Quality | 99/100 with 20/20 automation-generated corpus cases, Claude direct successes 20/20, `safe_mvp_ready=true`, `smart_edit_claim_ready=true` | Smart-edit claim is locally evidence-backed for this corpus; do not imply human customer study or universal editing quality. |
| Descript-Lite Readiness | 90/100, `descript_lite_claim_ready=true`, `price_149_plus_defense_ready=true` | Priorities 1-5 now pass for a gated Descript-style AI value defense; do not turn this into a full Descript replacement or collaboration claim. |
| Product Gap Push | 98/100, `implementation_ready=true`, `claim_ready=true` | The ordered 3,4,5,1,2,6 gap report is locally claim-ready; public copy still must remain scoped to the specific evidence reports. |
| NLE Readiness | 79/100, `professional_nle_claim_ok=false` | Core NLE workflow only; no Premiere/Resolve-class claim. |
| CapCut Parity Next | 89.38/100, `parity_ready=false` | Strong CapCut-style workflow progress; not full parity. |
| Broadcast Readiness | 95/100, `alpha_ready=true`, `commercial_ready=false` | Alpha-ready broadcast foundation; not sale/commercial broadcast-ready. |
| Automation/MCP QA | 100/100, 241 registered actions | Strong automation surface claim is acceptable. |

Current release-blocking evidence gaps are intentionally explicit:
`debugCapture/screenstudio_real_recording_corpus_qa.json` reports valid videos
40/20 with cursor sidecars and interaction-ready sidecars 20/20, and
`debugCapture/ai_edit_corpus_quality_qa.json` reports real-case coverage 20/20.
Those newly counted Screen Studio and AI cases were generated by
`tools/build_automated_release_evidence_corpus.py` and are labeled
`automation_generated` with `counts_as_human_user_evidence=false`; do not
describe them as a human user study or external customer corpus.
`debugCapture/ai_edit_corpus_quality_qa.json` also reports Claude direct
provider success 20/20 with fallback 0/20. `debugCapture/broadcast_release_readiness_qa.json`
still needs two redacted real-platform checks. The generated collection aid
`debugCapture/release_evidence_sprint_qa.json` remains useful for collecting
human/operator evidence. The follow-up automation report
`debugCapture/release_evidence_automation_qa.json` can promote filled
sidecar/AI templates and refresh all release QA in one pass, but it still does
not fabricate platform receipts.

## Current Claim Status

| Area | May Claim | Must Not Claim Yet |
|---|---|---|
| Screen Studio | Auto Polish path, cursor sidecars, click/drag/hotkey metadata support, manual zoom tools, export handoff, local 20/20 interaction QA corpus | 100% parity, perfect default results, human user recording corpus |
| AI Script Edit | Bottom AI Command dock, Script Edit panel, SRT/VTT/local word-timestamp transcription path, rule-based prompt routing, Claude direct provider corpus pass, reviewed safe apply, transcript deletion to reviewed video/audio ripple cuts, one-click filler/silence/retake cleanup, reviewed speech-enhance and sentence voice-replacement contracts | Full Descript replacement, autonomous story edit, hidden cloud AI, collaboration parity, universal magic one-click editing |
| CapCut | Creator Assist recipes, Shorts planning, caption beat/publish package, vertical reframe, preset packs | CapCut-scale template marketplace, trend AI ecosystem, one-click magic for every video |
| Resolve/Fairlight/Fusion | Color/audio/VFX foundations, scopes/LUT/HDR intent, routing payloads, repair payloads, readiness cards | Real-time Resolve Color page, Fairlight DAW, Fusion compositor replacement |
| Professional NLE | Core timeline actions, 3-point edit foundations, NLE readiness diagnostics | Premiere/Resolve-class NLE, full multicam/conform/bin/proxy workflow, long-project proven stability |
| Preview Performance | Measured preview/cache paths, current steady preview report, and current-corpus scrub readiness | Universal no-latency scrubbing on all codecs/resolutions/machines; always-smooth claims beyond the measured corpus |
| Live2D/Spine | Dedicated actor tracks, preview/export baking, large compatibility QA | Universal compatibility with every Unity/game-exported rig |
| MMD | PMX/PMD actor tracks, VMD motion workflow, Toon preview/export path, local corpus QA | Native MMD/Bullet parity, universal PMX support, perfect physics |
| AR/PBR 3D | First-class 3D object tracks, GPU/packet/software preview-export paths, HDR environment/material/shadow/reflection QA | Marmoset/Blender/game-engine replacement, physically perfect renderer, universal 3D import |
| VTuber/Broadcast | Program Output recording/RTMP foundation, optional OBS bridge, broadcast readiness diagnostics | OBS replacement, commercial live-production suite, platform-proven broadcast release |
| Automation | 241 registered actions and MCP/local automation surface | Arbitrary Python execution for users, complete third-party integration coverage |
| Release Trust | Autosave/crash reports/relink/QA Dashboard exist | Signed installer, auto-update, privacy page, production crash pipeline complete |

## Pricing Guardrails

- Safe early-access positioning: one-time USD $49-$99 or subscription USD
  $9-$15/month, explicitly labeled early access or beta while final readiness is
  below release-ready.
- Safer full-release target: one-time USD $149 or subscription USD $15-$19/month
  only after installer, docs, crash-free evidence, sample projects, and final
  readiness gates improve.
- A $149+ price may now be defended with the gated Descript-style AI workflow
  value only while `tools/qa_descript_lite_readiness.py` reports priorities 1-5
  claim-ready. Keep the copy tied to reviewed local workflow evidence, not
  full Descript replacement or collaboration parity.
- Do not price or describe TigerCapture as a Resolve/Premiere replacement.
  Resolve Studio's one-time price anchors the professional-suite market, so
  TigerCapture should be sold as a Windows creator capture/compositing tool with
  actor and local workflow strengths.

## Release Truth Gates

Before public paid positioning, verify:

1. `tools/qa_public_positioning.py` passes. It scans README, CHANGELOG,
   RELEASE_POSITIONING, RELEASE_TRUST, and optional landing/pricing/release-note
   copy for over-strong replacement, template-scale, suite-grade,
   universal-compatibility, and no-latency claims before they ship.
2. `tools/qa_screenstudio_real_recording_corpus.py` reports real interaction
   readiness, not only valid file count. Use
   `tools/register_screenstudio_real_recording.py --scan-root <folder>` with
   `--require-sidecar` when building the claim-ready corpus, otherwise old
   videos without cursor sidecars must stay positioned as intake candidates.
3. Final Product Readiness reports `release_ready=true` without hiding Screen
   Studio corpus, scrub/seek, Color/Audio, actor, or packaging advisories.
4. `tools/qa_preview_perf.py --clean --include-hires --include-hires-proxy`
   writes `debugCapture/preview_perf_report.json`, and
   `tools/qa_preview_scrub_readiness.py --auto-hires` reports
   `release_scrub_claim_ready=true` before any no-latency/smooth-scrubbing
   claim ships.
5. `tools/qa_nle_real_project_corpus.py` reports a claim-ready real corpus, and
   `tools/qa_nle_readiness.py` still blocks any full professional NLE claim
   unless `professional_nle_claim_ok=true`.
6. `tools/qa_gpu_export_parity_matrix.py` reports `release_ready=true`. If a
   future actor row regresses, public release notes must say actor
   preview/export parity is blocked rather than ready.
7. `tools/qa_ai_edit_corpus_quality.py --use-provider` exercises a wired local
   or agent provider on a real AI edit corpus before smart/magic AI editing
   claims ship.
8. `tools/qa_descript_lite_readiness.py` reports
   `descript_lite_claim_ready=true` before any Descript-lite copy ships, and
   `price_149_plus_defense_ready=true` before $149+ Descript-style AI value
   defense is used.
9. README, website, pricing, and release notes use the safe terms above.
10. Installer/code signing/auto-update/privacy/crash-report wording is explicit.
11. Public copy contains no unsupported external engine bridge or asset import
   claims.
