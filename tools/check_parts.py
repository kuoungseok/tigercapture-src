import glfw, live2d.v3 as l2d, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL = PROJECT_ROOT / "resources" / "live2d_samples" / "CubismWebSamples" / "Samples" / "Resources" / "Haru" / "Haru.model3.json"
glfw.init()
win = glfw.create_window(1,1,'t',None,None); glfw.make_context_current(win)
l2d.init(); l2d.glInit()
m = l2d.LAppModel()
m.LoadModelJson(str(MODEL))
ids = m.GetPartIds()
print(f"Part count: {m.GetPartCount()}", file=sys.stderr)
for i, pid in enumerate(ids):
    print(f"  [{i:2d}] {pid}", file=sys.stderr)
drawables = m.GetDrawableIds()
print(f"\nDrawable count: {len(drawables)}", file=sys.stderr)
glfw.terminate()
