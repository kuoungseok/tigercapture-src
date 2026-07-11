# TigerCapture Drum Sample Kits

Put durable local drum sample libraries here. `debugCapture` must not be used
for sample packs.

Supported kit entry files:

- `.sfz`
- `.dspreset` DecentSampler preset files
- `tigercapture_drumkit.json` or `drumkit.json` manifests

Sample audio files such as `.wav`, `.flac`, `.aif`, `.aiff`, and `.ogg` are
external assets and are ignored by Git. Keep the license/readme file from each
sample library next to the kit.

Recommended layout:

```text
external/assets/music/drum_kits/
  avl-drumkits/
    README.md
    LICENSE
    Black_Pearl_5pc.sfz
    Samples/
      ...
```

TigerCapture Music Lab sample-production rendering tries drum kits from this
folder before falling back to SoundFont/FluidSynth and then procedural synth
drums.

Local development note:

- AVL Drumkits can be installed at `external/assets/music/drum_kits/avl-drumkits`.
- The upstream project is `https://github.com/studiorack/avl-drumkits`.
- The upstream README describes the kit as 44.1 kHz / 16-bit mono recordings
  with 5 velocity layers per piece and CC-BY-SA 3.0 licensing.
