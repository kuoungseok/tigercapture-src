"""Patch VSeeFace to skip unconditional LeapMotion activation.

This is a local sidecar test aid for machines without the Ultraleap/Leap
service. VSeeFace v1.13.38c activates its LeapMotion GameObject during
EarlyTrigger.Start before the UI/model flow becomes usable on this machine.

The patch NOPs only:
    ldarg.0; ldfld leapMotion; ldc.i4.1; callvirt GameObject.SetActive(bool)
and leaves the following ret intact.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil


DEFAULT_DLL = (
    Path(__file__).resolve().parents[1]
    / "debugCapture"
    / "vseeface"
    / "VSeeFace"
    / "VSeeFace_Data"
    / "Managed"
    / "Assembly-CSharp.dll"
)

LEAP_START_ORIGINAL = bytes.fromhex("02 7B D0 02 00 04 17 6F 44 00 00 0A 2A")
LEAP_START_PATCHED = bytes([0x00] * 12) + bytes([0x2A])
HAND_INIT_ORIGINAL = bytes.fromhex("02 02 7B 10 03 00 04 6F 72 00 00 0A 6F 65 00 00 2B")
HAND_INIT_BAD_PATCHED = bytes([0x2A]) + HAND_INIT_ORIGINAL[1:]
LEAP_SETUP_HAND_INIT_CALL_ORIGINAL = bytes.fromhex("02 7B A2 03 00 04 6F 6D 02 00 06")
LEAP_SETUP_HAND_INIT_CALL_PATCHED = bytes([0x00] * len(LEAP_SETUP_HAND_INIT_CALL_ORIGINAL))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Disable VSeeFace startup LeapMotion activation.")
    parser.add_argument("--dll", type=Path, default=DEFAULT_DLL)
    parser.add_argument("--restore", type=Path, help="Restore from a backup DLL path.")
    args = parser.parse_args(argv)

    dll = args.dll
    if args.restore:
        shutil.copy2(args.restore, dll)
        print({"ok": True, "restored_from": str(args.restore), "dll": str(dll)})
        return 0

    data = dll.read_bytes()
    restores = [
        ("restore_bad_hand_controller_initialize_ret", HAND_INIT_BAD_PATCHED, HAND_INIT_ORIGINAL),
    ]
    patches = [
        ("leap_start_set_active", LEAP_START_ORIGINAL, LEAP_START_PATCHED),
        ("leap_setup_hand_initialize_call", LEAP_SETUP_HAND_INIT_CALL_ORIGINAL, LEAP_SETUP_HAND_INIT_CALL_PATCHED),
    ]
    patched = bytearray(data)
    applied: list[dict[str, str]] = []
    already: list[dict[str, object]] = []
    for name, bad, fixed in restores:
        index = data.find(bad)
        if index >= 0:
            if data.find(bad, index + 1) >= 0:
                print({"ok": False, "error": "restore_signature_not_unique", "patch": name, "dll": str(dll)})
                return 2
            patched[index:index + len(bad)] = fixed
            data = bytes(patched)
            applied.append({"patch": name, "offset": hex(index)})

    for name, original, replacement in patches:
        index = data.find(original)
        if index >= 0:
            if data.find(original, index + 1) >= 0:
                print({"ok": False, "error": "patch_signature_not_unique", "patch": name, "dll": str(dll)})
                return 2
            patched[index:index + len(original)] = replacement
            applied.append({"patch": name, "offset": hex(index)})
            continue

        patched_offsets = _all_offsets(data, replacement)
        if patched_offsets:
            already.append({"patch": name, "offsets": [hex(offset) for offset in patched_offsets]})
            continue

        print({"ok": False, "error": "patch_signature_not_found", "patch": name, "dll": str(dll)})
        return 2

    if not applied:
        print({"ok": True, "already_patched": True, "dll": str(dll), "patches": already})
        return 0

    backup = dll.with_name(f"{dll.name}.codex_leap_patch_backup_{datetime.now():%Y%m%d_%H%M%S}")
    shutil.copy2(dll, backup)
    dll.write_bytes(bytes(patched))
    print({
        "ok": True,
        "dll": str(dll),
        "backup": str(backup),
        "applied": applied,
        "already": already,
    })
    return 0


def _all_offsets(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        index = data.find(needle, start)
        if index < 0:
            return offsets
        offsets.append(index)
        start = index + 1


if __name__ == "__main__":
    raise SystemExit(main())
