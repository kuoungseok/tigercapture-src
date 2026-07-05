import subprocess, sys, os, glob, shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = str(PROJECT_ROOT / "resources" / "live2d_samples")
PYTHON  = sys.executable
OUT     = str(PROJECT_ROOT / "tools" / "compat_results.txt")

PROBE = (
    "import sys,glfw,live2d.v3 as l2d;"
    "glfw.init();"
    "glfw.window_hint(glfw.VISIBLE,False);"
    "w=glfw.create_window(1,1,'p',None,None);"
    "glfw.make_context_current(w);"
    "l2d.init();l2d.glInit();"
    "m=l2d.LAppModel();"
    "m.LoadModelJson(sys.argv[1]);"
    "glfw.terminate();sys.exit(0)"
)

models = sorted(glob.glob(os.path.join(SAMPLES, "**", "*.model3.json"), recursive=True))
fail_dirs = []

with open(OUT, "w", encoding="utf-8") as f:
    for path in models:
        name = os.path.relpath(path, SAMPLES)
        try:
            r = subprocess.run([PYTHON, "-c", PROBE, path], timeout=10, capture_output=True)
            status = "OK" if r.returncode == 0 else f"FAIL({r.returncode})"
            if r.returncode != 0:
                fail_dirs.append(os.path.dirname(path))
        except subprocess.TimeoutExpired:
            status = "TIMEOUT"
            fail_dirs.append(os.path.dirname(path))
        f.write(f"{status}\t{name}\n")
        f.flush()

    # Remove failing model folders
    f.write(f"\n--- Removing {len(fail_dirs)} failing models ---\n")
    for d in fail_dirs:
        shutil.rmtree(d, ignore_errors=True)
        f.write(f"DELETED: {d}\n")

print(f"Done. Results in {OUT}")
