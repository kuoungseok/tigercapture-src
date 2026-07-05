"""Step-by-step live2d debug — print each step before executing."""
import sys, os, faulthandler, ctypes
from pathlib import Path
faulthandler.enable(file=sys.stderr)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL = PROJECT_ROOT / "resources" / "live2d_samples" / "azurlane" / "aierdeliqi_4" / "aierdeliqi_4.model3.json"

print("step 1: import glfw")
import glfw

print("step 2: import live2d.v3")
import live2d.v3 as l2d
print(f"  pyd: {l2d.__file__}")

print("step 3: glfw.init()")
assert glfw.init()

# Try compatibility profile (some SDK versions need it)
glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_COMPAT_PROFILE)
glfw.window_hint(glfw.VISIBLE, True)

print("step 4: create window")
win = glfw.create_window(200, 200, "test", None, None)
assert win, "window creation failed"
glfw.make_context_current(win)

print("step 5: l2d.init()")
l2d.init()
print("  init OK")

print("step 6: l2d.glInit()")
l2d.glInit()
print("  glInit OK")

print("step 7: LAppModel()")
m = l2d.LAppModel()
print("  LAppModel() OK:", m)

print("step 8: LoadModelJson (THIS IS WHERE IT USUALLY CRASHES)")
sys.stderr.flush(); sys.stdout.flush()
abs_path = os.path.abspath(str(MODEL))
print(f"  path bytes: {abs_path.encode()}")
m.LoadModelJson(abs_path)
print("  LoadModelJson OK !")

glfw.terminate()
print("ALL PASS")
