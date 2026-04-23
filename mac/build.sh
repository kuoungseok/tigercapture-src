#!/usr/bin/env bash
# GifCam macOS build script.
#
# Usage (from repo root):
#   ./mac/build.sh                  # build GifCam.app only
#   ./mac/build.sh --dmg            # also build GifCam-<ver>.dmg
#   ./mac/build.sh --clean          # remove dist/ and build/ first
#   ./mac/build.sh --clean --dmg    # combine
#
# Requires:
#   - macOS 12.3+ with Xcode Command Line Tools (`xcode-select --install`)
#   - A Python venv at .venv with mac/requirements-mac.txt installed
#
# The app is **ad-hoc signed**. It will run locally but users on other
# Macs will see a Gatekeeper "cannot be opened" dialog on first launch
# — see README-mac.md for the right-click → Open workaround.

set -euo pipefail

# Resolve repo root from this script's location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

DO_DMG=0
DO_CLEAN=0
for arg in "$@"; do
    case "$arg" in
        --dmg) DO_DMG=1 ;;
        --clean) DO_CLEAN=1 ;;
        *) echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

PYTHON="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "error: python venv not found at $PYTHON" >&2
    echo "bootstrap:" >&2
    echo "  python3 -m venv .venv" >&2
    echo "  .venv/bin/pip install -r mac/requirements-mac.txt" >&2
    exit 1
fi

if (( DO_CLEAN )); then
    echo "[clean] removing dist/ build/"
    rm -rf "$REPO_ROOT/dist" "$REPO_ROOT/build"
fi

echo "[icns] regenerating mac/resources/gifcam.icns"
"$PYTHON" "$REPO_ROOT/mac/make_icns.py"

echo "[pyinstaller] building GifCam.app"
"$PYTHON" -m PyInstaller --noconfirm "$REPO_ROOT/mac/GifCam-mac.spec"

APP="$REPO_ROOT/dist/GifCam.app"
if [[ ! -d "$APP" ]]; then
    echo "error: $APP was not produced by PyInstaller" >&2
    exit 1
fi
echo "[pyinstaller] OK: $APP"

echo "[codesign] ad-hoc signing (no Developer ID)"
# --deep: sign every Mach-O inside the bundle; --force: replace existing
# signatures; identity "-" is the ad-hoc marker. This satisfies the
# "signed" requirement macOS now imposes on Apple Silicon but does NOT
# notarize. Gatekeeper will still warn on first launch from a different
# user account.
codesign --force --deep --sign - \
    --entitlements "$REPO_ROOT/mac/entitlements.plist" \
    --options runtime \
    "$APP"

echo "[codesign] verifying"
codesign --verify --deep --strict --verbose=2 "$APP" || {
    echo "warning: codesign verification reported issues" >&2
}

if (( DO_DMG )); then
    echo "[dmg] building GifCam-1.3.0.dmg"
    DMG_OUT="$REPO_ROOT/dist/GifCam-1.3.0.dmg"
    rm -f "$DMG_OUT"
    "$PYTHON" -m dmgbuild \
        -s "$REPO_ROOT/mac/dmg_settings.py" \
        -D app="$APP" \
        "GifCam 1.3.0" \
        "$DMG_OUT"
    echo "[dmg] OK: $DMG_OUT"
fi

echo "done."
