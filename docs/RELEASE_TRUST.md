# Release Trust Policy

This document is the release-facing trust checklist for Tiger Studio builds. It
keeps public packaging claims separate from feature-parity claims.

## Installer

- Windows releases are packaged as PyInstaller builds plus installer scripts.
- A release candidate must pass project QA, GPU/export parity QA, actor corpus
  QA, Screen Studio polish QA, Color/Audio checks, NLE readiness claim gates,
  and public positioning QA before being published.
- GPU/export parity is not release-ready while
  `debugCapture/gpu_export_parity_matrix_qa.json` has
  `release_ready=false`. Actor parity requires both export evidence and real
  preview visibility; Live2D preview coverage is currently expected to pass the
  GPU pixel-collision and export-parity matrix before any release claim.
- Public release pages should provide installers or packaged executables, not
  source archives.

## Code Signing

- Release notes must state whether the Windows installer is signed.
- Unsigned builds are allowed only for private or preview distribution and must
  be labeled as unsigned preview builds.
- A paid/public build should not be advertised as production-ready until the
  code signing status is explicit on the download page and in release notes.

## Auto-Update

- Tiger Studio does not silently self-update.
- Until a signed updater exists, updates are manual update installs from the
  release page or the configured internal distribution location.
- Release notes must tell users whether their build supports automatic updates,
  manual updates only, or no update channel.

## Crash Reports

- Crash reports stay local by default.
- The app may offer a repro bundle/export action so the user can choose what to
  send.
- Release notes should describe where crash reports are stored and how to remove
  or share them.

## Privacy / Local Processing

- Local AI, local media analysis, Live2D/Spine rendering, and AR/PBR preview
  paths should be described as local processing unless an optional external
  provider is explicitly selected by the user.
- Voice Lab subtitle-to-voice generation should be described as an optional
  local sidecar workflow. Style-Bert-VITS2 and user-trained voice models stay
  outside the closed TigerCapture editor build unless the user connects that
  local install.
- Optional providers such as Claude, Codex, upload/share providers, or future
  cloud integrations must be opt-in and labeled before use.

## Public Claim Boundary

- Say Screen Studio-inspired or CapCut-style when describing workflow polish.
- Say optional local Voice Lab sidecar when describing subtitle-to-voice.
- Do not claim full Screen Studio, CapCut, Resolve, Fairlight, Fusion, Descript,
  Premiere/Resolve-class professional NLE, or universal actor compatibility
  until the corresponding corpus, readiness, and parity gates pass.
