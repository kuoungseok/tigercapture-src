import glfw, live2d.v3 as l2d, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL = PROJECT_ROOT / "resources" / "live2d_samples" / "CubismWebSamples" / "Samples" / "Resources" / "Haru" / "Haru.model3.json"
glfw.init()
win = glfw.create_window(1,1,'t',None,None); glfw.make_context_current(win)
l2d.init(); l2d.glInit()
m = l2d.LAppModel()
m.LoadModelJson(str(MODEL))
p = m.GetParameter(0)
print('DIR:', [x for x in dir(p) if not x.startswith('_')], file=sys.stderr)
for i in range(m.GetParameterCount()):
    p = m.GetParameter(i)
    print(p.id, p.min, p.max, p.value, file=sys.stderr)
glfw.terminate()
