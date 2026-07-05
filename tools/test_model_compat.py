"""Test each Live2D model for SDK compatibility in isolated subprocess."""
import subprocess, sys, os, glob, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = str(PROJECT_ROOT / "resources" / "live2d_samples")
PYTHON  = sys.executable

PROBE = """
import sys, os
import glfw, live2d.v3 as l2d
glfw.init()
glfw.window_hint(glfw.VISIBLE, False)
win = glfw.create_window(1, 1, 'probe', None, None)
glfw.make_context_current(win)
l2d.init(); l2d.glInit()
m = l2d.LAppModel()
m.LoadModelJson(sys.argv[1])
glfw.terminate()
sys.exit(0)
"""

models = sorted(glob.glob(os.path.join(SAMPLES, "**", "*.model3.json"), recursive=True))

print(f"Testing {len(models)} models...\n")
ok, fail = [], []

for path in models:
    name = os.path.relpath(path, SAMPLES).replace("\\", "/")
    try:
        r = subprocess.run(
            [PYTHON, "-c", PROBE, path],
            timeout=10, capture_output=True
        )
        if r.returncode == 0:
            ok.append((name, path))
            print(f"  ✓  {name}")
        else:
            fail.append((name, path))
            print(f"  ✗  {name}  (exit {r.returncode})")
    except subprocess.TimeoutExpired:
        fail.append((name, path))
        print(f"  ✗  {name}  (timeout)")
    except Exception as e:
        fail.append((name, path))
        print(f"  ✗  {name}  ({e})")

print(f"\nOK: {len(ok)}  FAIL: {len(fail)}")
if fail:
    print("\nFailing models (will be removed):")
    for name, path in fail:
        print(f"  {path}")
    ans = input("\n위 모델들을 삭제할까요? (y/n): ")
    if ans.strip().lower() == 'y':
        for name, path in fail:
            folder = os.path.dirname(path)
            import shutil
            shutil.rmtree(folder, ignore_errors=True)
            print(f"  삭제: {folder}")
