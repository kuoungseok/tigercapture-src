"""Standalone Live2D viewer — pure glfw rendering to avoid Qt GL context conflict.

Usage:
    python live2d_standalone.py [model3.json path]

Controls:
    Space / →   Next motion
    ←           Previous motion
    R           Reset to idle
    F           Toggle fullscreen
    Esc / Q     Quit
"""
import sys
import os
import json
import math


def main(model3_path: str = "") -> None:
    import faulthandler, sys as _sys
    faulthandler.enable(file=_sys.stderr)

    try:
        import glfw
    except ImportError:
        print("[L2D] glfw not installed — run: pip install glfw", file=sys.stderr)
        sys.exit(1)

    try:
        import live2d.v3 as l2d
    except ImportError:
        print("[L2D] live2d-py not installed — run: pip install live2d-py", file=sys.stderr)
        sys.exit(1)

    # ── glfw init ──────────────────────────────────────────────────────────
    if not glfw.init():
        print("[L2D] glfw.init() failed", file=sys.stderr)
        sys.exit(1)

    # No explicit GL version/profile hints — matches live2d-py official example.
    # Core profile + FORWARD_COMPAT caused heap corruption on LoadModelJson.

    title = "Live2D — TigerCapture"
    if model3_path:
        title = os.path.basename(os.path.dirname(model3_path)) + " — TigerCapture Live2D"

    window = glfw.create_window(700, 750, title, None, None)
    if not window:
        glfw.terminate()
        print("[L2D] could not create glfw window", file=sys.stderr)
        sys.exit(1)

    glfw.make_context_current(window)
    glfw.swap_interval(1)   # vsync

    # ── live2d init (needs active GL context) ─────────────────────────────
    l2d.init()
    l2d.glInit()

    # ── state ─────────────────────────────────────────────────────────────
    model = None
    motions: list[tuple[str, int]] = []   # (group, index) pairs
    motion_labels: list[str] = []
    current_motion_idx = -1
    is_fullscreen = False
    _windowed_pos = [0, 0]
    _windowed_size = [700, 750]

    def _load_model(path: str) -> None:
        nonlocal model, motions, motion_labels, current_motion_idx

        abs_path = os.path.abspath(path)   # absolute path — live2d resolves textures relative to this

        if model is not None:
            model = None

        try:
            m = l2d.LAppModel()
            m.LoadModelJson(abs_path)       # no os.chdir — absolute path only
            w, h = glfw.get_framebuffer_size(window)
            m.Resize(w, h)
            model = m
            print(f"[L2D] loaded: {os.path.basename(abs_path)}", flush=True)
        except Exception as e:
            print(f"[L2D load] {e}", file=sys.stderr, flush=True)
            return

        # Parse motions from model3.json
        motions = []
        motion_labels = []
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            mdata = data.get("FileReferences", {}).get("Motions", {})
            for grp, items in mdata.items():
                for i, item in enumerate(items):
                    fname = os.path.basename(item.get("File", ""))
                    label = fname.replace(".motion3.json", "")
                    if grp:
                        label = f"{grp}/{label}"
                    motions.append((grp, i))
                    motion_labels.append(label)
        except Exception:
            pass

        # Auto-play idle
        current_motion_idx = _find_idle()
        if current_motion_idx >= 0:
            _play_motion(current_motion_idx)
        elif motions:
            _play_motion(0)

    def _find_idle() -> int:
        for i, lbl in enumerate(motion_labels):
            if "idle" in lbl.lower():
                return i
        return -1

    def _play_motion(idx: int) -> None:
        nonlocal current_motion_idx
        if model is None or idx < 0 or idx >= len(motions):
            return
        grp, mi = motions[idx]
        try:
            model.StartMotion(grp, mi, l2d.MotionPriority.FORCE)
            current_motion_idx = idx
            label = motion_labels[idx] if motion_labels else f"motion {idx}"
            glfw.set_window_title(
                window,
                f"{label} — TigerCapture Live2D"
            )
            print(f"[L2D] motion: {label}", flush=True)
        except Exception as e:
            print(f"[L2D motion] {e}", file=sys.stderr)

    # ── callbacks ──────────────────────────────────────────────────────────
    def _key_cb(win, key, scancode, action, mods):
        nonlocal is_fullscreen, _windowed_pos, _windowed_size, current_motion_idx

        if action not in (glfw.PRESS, glfw.REPEAT):
            return

        if key in (glfw.KEY_ESCAPE, glfw.KEY_Q):
            glfw.set_window_should_close(win, True)

        elif key in (glfw.KEY_SPACE, glfw.KEY_RIGHT):
            if motions:
                _play_motion((current_motion_idx + 1) % len(motions))

        elif key == glfw.KEY_LEFT:
            if motions:
                _play_motion((current_motion_idx - 1) % len(motions))

        elif key == glfw.KEY_R:
            idx = _find_idle()
            _play_motion(idx if idx >= 0 else 0)

        elif key == glfw.KEY_F:
            if is_fullscreen:
                glfw.set_window_monitor(win, None,
                    _windowed_pos[0], _windowed_pos[1],
                    _windowed_size[0], _windowed_size[1], 0)
                is_fullscreen = False
            else:
                _windowed_pos[:] = glfw.get_window_pos(win)
                _windowed_size[:] = glfw.get_window_size(win)
                monitor = glfw.get_primary_monitor()
                mode = glfw.get_video_mode(monitor)
                glfw.set_window_monitor(win, monitor, 0, 0,
                    mode.size.width, mode.size.height, mode.refresh_rate)
                is_fullscreen = True

    def _resize_cb(win, w, h):
        try:
            from OpenGL.GL import glViewport
            glViewport(0, 0, w, h)
        except Exception:
            pass
        if model:
            try:
                model.Resize(w, h)
            except Exception:
                pass

    glfw.set_key_callback(window, _key_cb)
    glfw.set_framebuffer_size_callback(window, _resize_cb)

    # Initial model load
    if model3_path and os.path.exists(model3_path):
        _load_model(model3_path)

    print("[L2D] Controls: Space/→ next motion | ← prev | R idle | F fullscreen | Esc quit",
          flush=True)

    # ── render loop ────────────────────────────────────────────────────────
    try:
        while not glfw.window_should_close(window):
            glfw.poll_events()
            l2d.clearBuffer(0.12, 0.12, 0.18, 1.0)
            if model:
                try:
                    model.Update()
                    model.Draw()
                except Exception as e:
                    print(f"[L2D render] {e}", file=sys.stderr)
            glfw.swap_buffers(window)
    finally:
        model = None
        try:
            l2d.dispose()
        except Exception:
            pass
        glfw.destroy_window(window)
        glfw.terminate()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    main(path)
