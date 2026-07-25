# TigerCapture Update System

Last updated: 2026-07-25

TigerCapture now has the code structure needed for safe app updates. The app
process checks and stages an update; a separate updater process applies it after
the app exits.

## Boundaries

- Private source stays on `source` / `kuoungseok/tigercapture-src`.
- Public update metadata and artifacts may go to the distribution-safe remote
  only after packaging: installer, portable zip, manifest, release notes.
- Never publish source-tree branches, WIP source tags, raw debug folders, or
  private assets as update artifacts.

## Runtime Modules

- `app.update.manifest`
  Parses `tigerstudio.update_manifest.v1`, compares versions, filters channel
  and platform, and selects the matching artifact.
- `app.update.checker`
  Reads a manifest from a local path, `file://`, HTTPS, or HTTP, then returns an
  update-check result.
- `app.update.downloader`
  Downloads or copies the selected artifact into the per-user update cache.
- `app.update.verifier`
  Verifies artifact SHA-256. Detached signature fields are present in the
  manifest contract for the future code-signing step.
- `app.update.apply_plan`
  Creates a JSON apply plan for the separate updater process.
- `app.update.workflow`
  App-facing one-call preparation API: check manifest, download artifact,
  verify SHA-256, write apply plan, and return the updater command.
- `tools/tigercapture_updater.py`
  Applies a staged `portable_zip` or silent installer plan after the app exits.
- `TigerCapture.spec`
  Packages `TigerCaptureUpdater.exe` next to `TigerCapture.exe` and
  `TigerStudio.exe` so a running app can hand off file replacement to a
  separate process.
- `tools/build_portable_update_package.py`
  Zips `dist/TigerCapture` into a root `TigerCapture/` portable update package
  and can emit a matching `latest.json` manifest.
- `.github/workflows/windows-update-package.yml`
  Manual GitHub Actions workflow that builds the Windows portable update zip,
  writes `latest.json`, verifies SHA-256, and optionally attaches both files to
  a GitHub Release.

## Manifest Shape

```json
{
  "schema": "tigerstudio.update_manifest.v1",
  "app_id": "TigerCapture",
  "version": "1.4.3",
  "channel": "stable",
  "minimum_app_version": "1.4.0",
  "published_at": "2026-07-06T00:00:00Z",
  "release_notes_url": "https://example.com/tigercapture/releases/1.4.3",
  "signature_policy": "sha256-required",
  "artifacts": [
    {
      "url": "https://example.com/TigerCapture-Setup-1.4.3.exe",
      "sha256": "64 lowercase hex characters",
      "platform": "windows-x64",
      "kind": "installer",
      "filename": "TigerCapture-Setup-1.4.3.exe",
      "size": 123456789
    }
  ]
}
```

## Build A Manifest

```powershell
.\.venv\Scripts\python.exe tools\build_update_manifest.py `
  --artifact installer_output\TigerCapture-Setup-1.4.3.exe `
  --version 1.4.3 `
  --artifact-url https://updates.example/TigerCapture-Setup-1.4.3.exe `
  --release-notes-url https://updates.example/releases/1.4.3 `
  --output release\updates\stable\latest.json
```

Verify before publishing:

```powershell
.\.venv\Scripts\python.exe tools\verify_update_package.py `
  --manifest release\updates\stable\latest.json `
  --artifact installer_output\TigerCapture-Setup-1.4.3.exe `
  --current-version 1.4.2
```

Build a portable update package and manifest from a local PyInstaller build:

```powershell
.\build.ps1 -Clean -Version 1.4.3 -PortableUpdate `
  -UpdateArtifactUrl https://github.com/kuoungseok/tigercapture/releases/download/v1.4.3/TigerCapture-Portable-1.4.3.zip `
  -UpdateManifestOutput installer_output\latest.json `
  -UpdateReleaseNotesUrl https://github.com/kuoungseok/tigercapture/releases/tag/v1.4.3
```

The packaged app defaults to:

```text
https://github.com/kuoungseok/tigercapture/releases/latest/download/latest.json
```

Override it for staging or private QA with:

```powershell
$env:TIGERCAPTURE_UPDATE_MANIFEST_URL="file:///D:/path/to/latest.json"
```

## Apply Flow

1. App calls `app.update.workflow.prepare_update_from_default_manifest(...)`
   or `prepare_update_from_manifest(...)` with an explicit manifest URL.
2. The workflow checks `latest.json`, downloads the selected artifact, verifies
   SHA-256, writes an apply plan, and returns the updater command.
3. App launches the updater command and exits.
4. Updater waits for the app process, verifies SHA-256 again, backs up the
   install folder for portable zips, applies files or runs the silent installer,
   then restarts the app.

## GitHub Release Flow

1. Run **Windows update package** from GitHub Actions.
2. Enter the version, for example `1.4.3`.
3. Leave `publish_release=false` for a dry artifact build, or set it to `true`
   to upload `TigerCapture-Portable-1.4.3.zip` and `latest.json` to release tag
   `v1.4.3`.
4. The app reads GitHub's `latest` release manifest and stages the matching
   `portable_zip`.

## Current Limitations

- The foundation and packaging path are implemented, but the editor UI
  button/menu is not wired yet.
- SHA-256 is enforced; detached signature verification is reserved in the
  manifest contract and should be required before public auto-update claims.
- Differential patching is intentionally out of scope. Use full installer or
  full portable zip updates first.
