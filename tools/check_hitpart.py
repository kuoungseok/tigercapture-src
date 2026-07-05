"""Check which parts HitPart detects and where, on Haru model."""
import glfw, live2d.v3 as l2d, sys, collections
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL = PROJECT_ROOT / "resources" / "live2d_samples" / "CubismWebSamples" / "Samples" / "Resources" / "Haru" / "Haru.model3.json"

glfw.init()
win = glfw.create_window(640, 640, 't', None, None)
glfw.make_context_current(win)
l2d.init(); l2d.glInit()

m = l2d.LAppModel()
m.LoadModelJson(str(MODEL))
m.Resize(640, 640)

# Render a few frames so model transforms initialize
import OpenGL.GL as GL
for _ in range(5):
    GL.glClearColor(0,0,0,1)
    GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
    m.Update()
    m.Draw()
    glfw.swap_buffers(win)
    glfw.poll_events()

# Dense sampling: 80x80
W, H = 640, 640
STEPS = 80
part_hits = collections.defaultdict(list)

for yi in range(STEPS):
    for xi in range(STEPS):
        px = int(xi * W / STEPS + W / STEPS * 0.5)
        py = int(yi * H / STEPS + H / STEPS * 0.5)
        for pid in m.HitPart(px, py):
            part_hits[pid].append((px, py))

print("\n=== HitPart results (80x80 grid on 640x640) ===", file=sys.stderr)
for pid in m.GetPartIds():
    hits = part_hits.get(pid, [])
    if hits:
        xs = [p[0] for p in hits]
        ys = [p[1] for p in hits]
        print(f"  {pid:25s}  hits={len(hits):4d}  bbox=({min(xs)},{min(ys)})-({max(xs)},{max(ys)})", file=sys.stderr)
    else:
        print(f"  {pid:25s}  NO HITS", file=sys.stderr)

glfw.terminate()
