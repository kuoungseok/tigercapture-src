"""Prepare VSeeFace settings.ini for TigerCapture sidecar tests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vmc_protocol import VMC_DEFAULT_HOST, VMC_VSEEFACE_SENDER_PORT
from app.vtuber.vseeface_sidecar_config import (
    OPENSEEFACE_TRACKING_CAMERA_NAME,
    build_sidecar_settings_values,
    default_vseeface_settings_path,
    read_openseedemo_settings,
    write_vseeface_sidecar_settings,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write VSeeFace OpenSeeDemo sidecar settings.")
    parser.add_argument("--settings", default=str(default_vseeface_settings_path()))
    parser.add_argument("--avatar-vrm", required=True)
    parser.add_argument("--openseeface-host", default=VMC_DEFAULT_HOST)
    parser.add_argument("--openseeface-port", type=int, default=VMC_VSEEFACE_SENDER_PORT)
    parser.add_argument("--camera-name", default=OPENSEEFACE_TRACKING_CAMERA_NAME)
    parser.add_argument("--disable-virtual-camera", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    values = build_sidecar_settings_values(
        avatar_vrm=args.avatar_vrm,
        openseeface_host=args.openseeface_host,
        openseeface_port=args.openseeface_port,
        camera_name=args.camera_name,
        enable_virtual_camera=not args.disable_virtual_camera,
    )
    result = write_vseeface_sidecar_settings(args.settings, values, backup=not args.no_backup)
    payload = {
        "schema": "tigerstudio.vtuber.vseeface_sidecar_config.v1",
        "ok": True,
        "settings": result.to_dict(),
        "values": read_openseedemo_settings(args.settings),
        "notes": [
            "IP/Port configure VSeeFace's OpenSeeFace tracking input.",
            "They do not enable VSeeFace's VMC receiver; that remains a runtime VSeeFace UI state.",
        ],
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "settings": result.path, "encoding": result.encoding, "backup": result.backup_path}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
