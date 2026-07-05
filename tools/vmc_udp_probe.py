"""Small UDP probe for validating VMC/OSC sender output."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import time
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vmc_protocol import VMC_VSEEFACE_RECEIVER_PORT


def main() -> int:
    parser = argparse.ArgumentParser(description="Listen for VMC/OSC UDP packets and write a summary.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=VMC_VSEEFACE_RECEIVER_PORT)
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--out", default="debugCapture/vmc_udp_probe.json")
    args = parser.parse_args()

    packets: list[dict] = []
    deadline = time.time() + max(0.1, float(args.seconds))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, int(args.port)))
    sock.settimeout(0.25)
    try:
        while time.time() < deadline:
            try:
                data, address = sock.recvfrom(65535)
            except socket.timeout:
                continue
            packets.append({
                "from": f"{address[0]}:{address[1]}",
                "bytes": len(data),
                "address": _read_osc_address(data),
            })
    finally:
        sock.close()

    counts: dict[str, int] = {}
    for packet in packets:
        counts[packet["address"]] = counts.get(packet["address"], 0) + 1
    report = {
        "schema": "tigerstudio.vtuber.vmc_udp_probe.v1",
        "host": args.host,
        "port": int(args.port),
        "seconds": float(args.seconds),
        "packet_count": len(packets),
        "address_counts": counts,
        "first_packets": packets[:20],
        "ok": bool(packets),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "packet_count": report["packet_count"], "address_counts": counts, "out": str(out)}, ensure_ascii=False))
    return 0 if report["ok"] else 2


def _read_osc_address(data: bytes) -> str:
    try:
        end = data.index(b"\0")
    except ValueError:
        return ""
    return data[:end].decode("utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
