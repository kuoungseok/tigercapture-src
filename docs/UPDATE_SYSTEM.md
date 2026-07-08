# TigerCapture Update System

Last updated: 2026-07-06

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

## Apply Flow

1. App calls `app.update.workflow.prepare_update_from_manifest(...)`.
2. The workflow checks `latest.json`, downloads the selected artifact, verifies
   SHA-256, writes an apply plan, and returns the updater command.
3. App launches the updater command and exits.
4. Updater waits for the app process, verifies SHA-256 again, backs up the
   install folder for portable zips, applies files or runs the silent installer,
   then restarts the app.

## Current Limitations

- The foundation is implemented, but the editor UI button/menu is not wired yet.
- SHA-256 is enforced; detached signature verification is reserved in the
  manifest contract and should be required before public auto-update claims.
- Differential patching is intentionally out of scope. Use full installer or
  full portable zip updates first.
