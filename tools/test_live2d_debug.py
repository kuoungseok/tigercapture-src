"""live2d debug — enable SDK logging, try path variations."""
import sys, os, faulthandler
from pathlib import Path
faulthandler.enable(file=sys.stderr)

import glfw
import live2d.v3 as l2d

print("Python:", sys.version)
print("live2d pyd:", l2d.__file__)

glfw.init()
glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_COMPAT_PROFILE)
win = glfw.create_window(200, 200, "test", None, None)
glfw.make_context_current(win)

l2d.init()
l2d.enableLog(True)
l2d.glInit()

# Try multiple path formats
PROJECT_ROOT = Path(__file__).resolve().parents[1]
model_dir = str(PROJECT_ROOT / "resources" / "live2d_samples" / "azurlane" / "aierdeliqi_4")
candidates = [
    os.path.join(model_dir, "aierdeliqi_4.model3.json"),
    model_dir.replace("\\", "/") + "/aierdeliqi_4.model3.json",
]

for path in candidates:
    print(f"\n--- trying: {path!r}")
    print(f"    exists: {os.path.exists(path)}")
    print(f"    moc3 exists: {os.path.exists(os.path.join(model_dir, 'aierdeliqi_4.moc3'))}")
    sys.stdout.flush(); sys.stderr.flush()
    m = l2d.LAppModel()
    m.LoadModelJson(path)
    print("    LOADED OK")
    break

glfw.terminate()
