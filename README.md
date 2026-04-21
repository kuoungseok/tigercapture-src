# GifCam

HoneyCam-style screen capture for Windows. Capture a region of your screen as a
screenshot, an animated GIF, or an MP4 video — then trim frames and export.

**Made by** [artmouse (KyoungSeok Ko)](https://github.com/kuoungseok)

---

## Highlights

- **Three capture modes** — Screenshot / GIF / Video, each with its own editor
- **Windows Graphics Capture** backend (DWM + GPU accelerated) — 60 fps on
  large regions, no black-frame issues on multi-monitor per-monitor-DPI setups
- **Frame-by-frame GIF editor** — scrubbable timeline, per-frame delete, live
  preview, estimated file size
- **Smart GIF encoder** — per-frame adaptive palette by default; auto-uses
  `gifski` if found in `bundled/` or on PATH; optional `gifsicle` post-pass
- **H.264 MP4 export** via bundled FFmpeg (`imageio-ffmpeg`)
- **Multi-language UI** — Korean / English / 日本語 / Deutsch, auto-detected
  from the Windows locale, switchable live from Settings
- **Keyboard shortcuts** — `Ctrl+Shift+N` new capture, `Ctrl+1/2/3` switch mode,
  `Ctrl+O` open folder, `Ctrl+,` settings
- **Windows 11 Snipping Tool–style UI**, native installer registers in
  *Apps & Features* for clean uninstall

## Screenshots

_Add screenshots / GIFs of the app here._

## Install

### Option 1 — Installer (recommended)

Download `GifCam-Setup-<version>.exe` from the
[Releases page](https://github.com/kuoungseok/gifcam/releases) and run it. No
administrator rights required; installs to `%LOCALAPPDATA%\GifCam` and
registers under **Settings → Apps → Installed apps** so it can be uninstalled
the normal Windows way.

### Option 2 — Portable

Download `GifCam-<version>-portable.zip`, unzip anywhere, run `GifCam.exe`.
Delete the folder to "uninstall". Captures stay in `~/Videos/GifCam`.

## System requirements

- Windows 10 1903 or newer (Windows Graphics Capture API)
- x64 architecture

## Development

### Setup

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Build

```powershell
.\build.ps1              # PyInstaller only  -> dist\GifCam\
.\build.ps1 -NSIS        # + NSIS installer  -> installer_output\
.\build.ps1 -Clean       # clean build artifacts first
```

The build script expects NSIS to be installed (available via `winget install
NSIS.NSIS`). It locates `makensis.exe` automatically in
`C:\Program Files (x86)\NSIS`.

### Optional external tools

Drop these in `bundled/` to improve GIF output — the app picks them up
automatically:

- **[gifski](https://gif.ski/)** (`bundled/gifski.exe`) — near-video-quality
  GIF encoder; preferred when present
- **[gifsicle](https://www.lcdf.org/gifsicle/)** (`bundled/gifsicle.exe`) —
  final lossy optimization pass

## Architecture

- `main.py` — entry point, wires i18n + controller + main window
- `app/main_window.py` — main UI (Win11 Snipping Tool–style)
- `app/controller.py` — coordinates region selection, recording, editor
- `app/region_selector.py` — per-monitor overlays for accurate selection on
  mixed-DPI multi-monitor setups
- `app/recorder.py` — WGC-backed frame recorder (main-thread QTimer drives
  fps, WGC thread crops + BGRA→RGB)
- `app/gif_editor_window.py` — frame timeline editor (GIF & Video)
- `app/exporter.py` — GIF (Pillow / gifski) and MP4 (imageio-ffmpeg) encoders
- `app/i18n.py` + `app/locales/` — minimal dict-based translation system

## License

MIT — see [LICENSE](LICENSE).

## Credits

Built with [PySide6](https://doc.qt.io/qtforpython/),
[Pillow](https://python-pillow.org/),
[imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg), and
[windows-capture](https://pypi.org/project/windows-capture/).
Installer packaged with [NSIS](https://nsis.sourceforge.io/).
