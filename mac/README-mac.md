# GifCam — macOS build

This directory contains everything needed to build and run GifCam on
macOS. The shared UI code in `../app/` is reused unchanged; only the
five platform-specific modules (`recorder`, `foreground_tracker`,
`quick_paste`, `cursor_overlay`, `paths`) are overlaid here.

## Requirements

- **macOS 12.3 Monterey or newer** (ScreenCaptureKit hard requirement)
- **Python 3.13** (recommended; 3.11+ should also work)
- **Xcode Command Line Tools** — `xcode-select --install`
- An Apple Developer account is **not** required. Builds are ad-hoc
  signed; see "Gatekeeper" below for the end-user consequence.

## Suggested workflow (edit on PC, build on Mac)

GifCam's UI code lives in `app/` and is edited on a PC. Use VS Code's
**Remote-SSH** extension to connect to the Mac — all file I/O, Python,
and `./mac/build.sh` run on the Mac, but the editor UI is on the PC.

On the Mac:
1. **System Settings → General → Sharing → Remote Login** on
2. Note `hostname.local` and your username

On the PC (VS Code):
1. Install the **Remote - SSH** extension
2. `Ctrl+Shift+P` → `Remote-SSH: Connect to Host...` → `user@hostname.local`
3. `File → Open Folder` → `/Users/you/Projects/GifCam`

For live UI testing, keep the Mac awake alongside the PC, or use
**System Settings → Sharing → Screen Sharing** to drive the Mac
desktop from the PC.

## First-time setup (on the Mac)

```bash
cd /path/to/GifCam
python3 -m venv .venv
.venv/bin/pip install -r mac/requirements-mac.txt
```

## Run from source

```bash
.venv/bin/python mac/main.py
```

First launch will trigger two permission prompts:

1. **Screen & System Audio Recording** — required. Grant via
   *System Settings → Privacy & Security → Screen Recording*. You'll
   need to quit and relaunch GifCam for the permission to take effect.
2. **Accessibility** — optional. Enables reading the frontmost
   window's title (for quick-paste labels) and simulating ⌘V when
   pasting a capture back into the previous app. Without it, GifCam
   still records and exports; only the quick-paste polish is lost.

## Build

```bash
./mac/build.sh            # -> dist/GifCam.app
./mac/build.sh --dmg      # -> dist/GifCam.app + dist/GifCam-1.3.0.dmg
./mac/build.sh --clean --dmg
```

The script:
1. Regenerates `mac/resources/gifcam.icns` from the same Pillow art
   used for the Windows `.ico`
2. Runs PyInstaller with `mac/GifCam-mac.spec`
3. Ad-hoc signs the bundle via `codesign --sign -`
4. (with `--dmg`) builds a drag-to-Applications DMG via `dmgbuild`

## Gatekeeper / first launch on other Macs

Without Apple notarization, a different user's Mac will show this on
first launch:

> `"GifCam.app" cannot be opened because Apple cannot check it for
> malicious software.`

The supported workaround (no Terminal needed):

1. In Finder, **right-click** `GifCam.app` → **Open**
2. Confirm in the dialog that appears

macOS remembers the exception, so subsequent launches work normally
(double-click, Launchpad, Spotlight). This is the standard cost of
not having an Apple Developer ID. If that gets painful enough to
justify the $99/year, see the "Upgrading to notarization" section
below.

## Architecture notes

- `mac/app/__init__.py` extends `__path__` to include the root `app/`.
  Python's package machinery then looks in `mac/app/` first and falls
  back to the repo's `app/`. This keeps the Windows code untouched
  while letting us shadow only the modules that need macOS impls.
- `mac/main.py` prepends `mac/` to `sys.path` before importing `app`,
  so the overlay is what gets picked up.
- ScreenCaptureKit's `SCStream` delivers frames on a dispatch queue;
  our `_StreamOutput` delegate is an `NSObject` subclass defined via
  PyObjC. A main-thread `QTimer` samples the latest frame at the
  target fps — same decoupled design as the Windows WGC recorder.

## Upgrading to notarization (optional, later)

If you enroll in the Apple Developer Program ($99/year):

1. Create a **Developer ID Application** certificate in Keychain
2. Replace `codesign --sign -` in `build.sh` with your identity:
   `codesign --sign "Developer ID Application: Your Name (TEAMID)"`
3. Submit for notarization via:
   ```bash
   xcrun notarytool submit dist/GifCam-1.3.0.dmg \
       --apple-id your@id.com --team-id TEAMID --wait
   xcrun stapler staple dist/GifCam-1.3.0.dmg
   ```
4. The Gatekeeper warning disappears for all users.

Keep the build script parameterized by an env var like
`GIFCAM_SIGNING_IDENTITY` so development builds stay ad-hoc.

## Troubleshooting

- **Black or empty frames**: Screen Recording permission missing.
  System Settings → Privacy & Security → Screen Recording, tick
  GifCam, then quit+relaunch.
- **"SCShareableContent returned nil"**: same as above, but the
  prompt was dismissed. Toggle the permission off and on again to
  reissue it, or add GifCam manually.
- **Quick-paste does nothing**: Accessibility permission missing.
  System Settings → Privacy & Security → Accessibility, tick GifCam.
- **`ModuleNotFoundError: ScreenCaptureKit`**: the pyobjc SCK module
  needs pyobjc 10.3+. Upgrade with
  `.venv/bin/pip install -U pyobjc-framework-ScreenCaptureKit`.
- **App crashes on launch after update**: stale PyInstaller cache.
  `./mac/build.sh --clean`.
