# TigerCapture Music Sample Assets

This folder is for optional user-installed music assets. TigerCapture must not
bundle third-party sample packs, models, or licensed instrument libraries.

Use these locations:

- `soundfonts/`: `.sf2`, `.sf3`, or all-in-one `.sfz` SoundFonts.
- `sfz/`: melodic SFZ instruments such as guitar, orchestra, or bass libraries.
- `drum_kits/`: SFZ, DecentSampler, DrumGizmo-style, or
  `tigercapture_drumkit.json` drum kits.

Keep each downloaded library's original `LICENSE`, `README`, or attribution
file beside the asset. Do not put sample libraries in `debugCapture`; that
folder is disposable scratch space.

Suggested external libraries to evaluate:

- AVL Drumkits: https://github.com/studiorack/avl-drumkits
- DrumGizmo DRSKit SFZ: https://github.com/sfzinstruments/DrumGizmo.DRSKit
- FreePats e-guitar FSBS dist2: https://github.com/freepats/e-guitar-FSBS-dist2
- VSCO 2 Community Edition: https://github.com/sgossner/VSCO-2-CE

After copying assets here, reopen Music Lab or use `music.render.backends` to
check discovery status.
