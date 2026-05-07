# TigerCapture

A Windows screen-capture studio and professional video editor — record a region as a screenshot, GIF, or MP4, then jump into a full editor with **DaVinci-style color grading**, **AI-powered masking**, **node graph effects**, **kinetic typography**, **subtitles**, and a deep **sound editor**.

**Made by** [artmouse (KyoungSeok Ko)](https://github.com/kuoungseok)

---

## What's new in v1.4.0

- **DaVinci-style Color Page** — 4-wheel color grading panel with luma arc, hue ring, and interactive luminance dial; opens above the timeline when a Color node is selected
- **Node Graph** — non-destructive effects chain (Color → Blur → Out), with per-node thumbnails, parallel mixer, and Bezier connections
- **AI Masking** — SAM (Segment Anything) click-to-mask, GrabCut rotoscope, CSRT object tracker, Power Window, Qualifier
- **Performance** — background PrefetchDecoder thread (near-zero read latency), 720p preview downscale, DXVA2 hardware decode hint
- **New Project dialog** — choose aspect ratio (16:9 / 9:16 Shorts / 1:1 / 4:3 / 21:9), resolution, and FPS upfront
- **Video filters** — sharpen, vignette, denoise, chromatic aberration, glitch
- **Chroma key** — green/blue screen removal with spill suppression
- **Video stabilization** — LK optical flow
- **AI Background Removal** — MediaPipe selfie segmentation / rembg
- **Speed Ramp** — Bezier easing between speed segments
- **Batch export** — marker-based segment export queue
- **Audio Mixer** — VU meters, per-track pan (export), LUFS metering
- **Project save/load** — `.tgp` JSON format preserves full session state
- **UI Polish** — Segoe UI Variable font, consistent section headers, DaVinci-inspired dark theme

---

## Features

### Screen Capture
- **Three capture modes** — Screenshot, GIF, MP4
- Windows Graphics Capture (WGC) for GPU-composited windows
- MP4 streaming encode via ffmpeg pipe
- Cursor overlay, countdown, recording border indicator

### Pro Video Editor

Multi-track timeline with a professional editing workflow:

| Feature | Details |
|---|---|
| **Timeline editing** | Cut (B/C), Ripple trim, Roll edit, Speed segments, Fades, Markers |
| **Color grading** | 4-wheel (Lift/Gamma/Gain/Offset) + luma arc + node graph chain |
| **Node graph** | Color nodes, Blur nodes, Parallel mixer, Per-node masks |
| **AI masking** | SAM click-to-mask, Power Window, HSL Qualifier, Face/Body tracker |
| **Effects** | Blur (bokeh/hexagon/gaussian), Sharpen, Vignette, Chroma key, Stabilizer |
| **PIP** | Picture-in-Picture with keyframe animation |
| **Typography** | 80+ kinetic animations, speech bubbles, stickers |
| **Subtitles** | Timeline lane with AI auto-captions (Whisper) |
| **Export** | MP4 / WebM / MOV, 4K/1080p/720p/9:16/1:1, HDR10 passthrough |

### DaVinci-style Color Grading

- **4 color wheels** — Lift (Shadows), Gamma (Midtones), Gain (Highlights), Offset
- **Luma arc** — drag the outer ring on each wheel to adjust luminosity
- **Node graph** — non-destructive chain evaluated per-frame
- **Scopes** — Waveform, Vectorscope, Parade, Histogram (in color page)
- **Color page** — full-screen DaVinci-style layout (🎨 button)
- **LUT support** — .cube file loading with strength slider
- **8 presets** — Cinematic, Vintage, Cool, Warm, Faded, B&W, Punch, Mute

### Sound Editor

- **AI Master** — one-click presets for Suno v3/v4, Udio, ACE-Step AI music
- **Dynamics** — EQ, Compressor, Gate, De-esser, Reverb, Delay
- **Audio mixer** — Per-track volume/pan, VU meters, LUFS display
- **Waveform visualization** — stereo waveform + spectrum per clip

### Kinetic Typography

- 80+ kinetic animations (Basic / Kinetic / Folding / HOLD)
- IN × HOLD × OUT × modifier stacking
- 12 curated presets for J-MV / K-pop aesthetics

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | PySide6 (Qt 6), OpenGL preview |
| Video decode | cv2 + PrefetchDecoder thread, ffmpeg HDR tonemap |
| Color grading | CPU numpy pipeline + OpenGL shader passthrough |
| AI masking | SAM (facebook/segment-anything), MediaPipe, OpenCV |
| Audio | Qt QMediaPlayer + ffmpeg filter graph |
| Export | ffmpeg subprocess with concat demuxer |
| Packaging | PyInstaller |

---

## Requirements

- Windows 10 / 11 (64-bit)
- NVIDIA GPU recommended (DXVA2 hardware decode)
- Python 3.11+ (for source build)

---

## Installation

Download the latest release from [Releases](https://github.com/kuoungseok/tigercapture/releases) and extract `TigerCapture-vX.X.X-windows.zip`. Run `TigerCapture.exe` — no installation required.

---

## Building from source

```bash
git clone https://github.com/kuoungseok/tigercapture.git
cd tigercapture
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py                          # run from source
pyinstaller TigerCapture.spec --clean   # build exe
```

---

## License

All rights reserved. Source code is private. Binaries are provided for personal use.
