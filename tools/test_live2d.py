"""Minimal live2d-py + glfw test — no Qt dependency.

Tests:
  1. glfw window (no core-profile hint)
  2. live2d.v3 init + glInit
  3. LAppModel.LoadModelJson
  4. basic render loop (5 seconds then auto-exit)
"""
import sys, os, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL = PROJECT_ROOT / "resources" / "live2d_samples" / "azurlane" / "aierdeliqi_4" / "aierdeliqi_4.model3.json"

try:
    import glfw
except ImportError:
    print("glfw not installed"); sys.exit(1)

try:
    import live2d.v3 as l2d
except ImportError:
    print("live2d-py not installed"); sys.exit(1)

print("=== step 1: glfw.init()")
if not glfw.init():
    print("glfw.init() failed"); sys.exit(1)

# Do NOT request core profile — let the driver pick default context
# (Cubism SDK GL loader may not work with strict core profile)
glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 2)
glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
# no MSAA for now
print("=== step 2: create window")
window = glfw.create_window(700, 700, "live2d test", None, None)
if not window:
    glfw.terminate(); print("window creation failed"); sys.exit(1)

glfw.make_context_current(window)
glfw.swap_interval(1)

print("=== step 3: live2d init + glInit")
l2d.init()
l2d.glInit()
print("    glInit OK")

print("=== step 4: LoadModelJson")
model = l2d.LAppModel()
abs_path = os.path.abspath(str(MODEL))
print(f"    path: {abs_path}")
model.LoadModelJson(abs_path)
print("    LoadModelJson OK")

w, h = glfw.get_framebuffer_size(window)
model.Resize(w, h)
print(f"    Resize({w},{h}) OK")

print("=== step 5: render loop (5 s)")
t0 = time.time()
while not glfw.window_should_close(window) and time.time() - t0 < 5:
    glfw.poll_events()
    l2d.clearBuffer(0.12, 0.12, 0.18, 1.0)
    model.Update()
    model.Draw()
    glfw.swap_buffers(window)

print("=== cleanup")
model = None
l2d.dispose()
glfw.destroy_window(window)
glfw.terminate()
print("=== ALL PASS")
