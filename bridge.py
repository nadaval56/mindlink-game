#!/usr/bin/env python3
"""
MindLink Bridge — Bluetooth Serial → WebSocket

Usage:
  python bridge.py              # auto-detect COM port
  python bridge.py --port COM6  # specify port
  python bridge.py --demo       # demo mode (no device needed)
"""

import asyncio
import json
import math
import random
import time
import argparse
import sys
import logging

try:
    import websockets
except ImportError:
    print("ERROR: run  pip install websockets pyserial  first", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

WS_PORT = 8765
BROADCAST_INTERVAL = 0.1

# ── shared state ──────────────────────────────────────────────────────────────

state = {
    "attention":  0,
    "meditation": 0,
    "blink":      0,
    "signal":     200,
    "connected":  False,
}
_blink_latch = 0

# ── ThinkGear packet parser ───────────────────────────────────────────────────

SYNC = 0xAA

def _parse_payload(payload: bytes) -> None:
    global _blink_latch
    i = 0
    while i < len(payload):
        code = payload[i]; i += 1
        if code == 0x55:          # EXCODE — skip
            continue
        if code >= 0x80:          # multi-byte value
            if i >= len(payload): break
            vlen = payload[i]; i += 1
            i += vlen             # skip (raw EEG / EEG power — not needed)
        else:                     # single-byte value
            if i >= len(payload): break
            val = payload[i]; i += 1
            if code == 0x02:      # POOR_SIGNAL
                state["signal"]    = val
                state["connected"] = (val < 200)
            elif code == 0x04:    # ATTENTION
                state["attention"] = val
            elif code == 0x05:    # MEDITATION
                state["meditation"] = val
            elif code == 0x16:    # BLINK_STRENGTH
                _blink_latch = val
                log.info("Blink detected: strength=%d", val)


def _process_buf(buf: bytearray) -> bytearray:
    """Scan buffer for complete ThinkGear packets and parse them."""
    while len(buf) >= 4:
        if buf[0] != SYNC or buf[1] != SYNC:
            buf.pop(0)
            continue
        plen = buf[2]
        if plen == SYNC:          # not a valid length byte
            buf.pop(0)
            continue
        if len(buf) < 4 + plen:
            break                 # wait for more data
        payload  = buf[3:3+plen]
        checksum = buf[3+plen]
        if (~sum(payload)) & 0xFF == checksum:
            _parse_payload(bytes(payload))
        buf = buf[4+plen:]
    return buf

# ── auto-detect serial port ───────────────────────────────────────────────────

def _find_port():
    import glob, serial
    candidates = (
        glob.glob("/dev/tty.MindLink*") +
        glob.glob("/dev/rfcomm*") +
        glob.glob("/dev/ttyACM*")
    )
    # Windows: scan COM3–COM20, prefer ones with "Bluetooth" in description
    try:
        import serial.tools.list_ports
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower()
            if any(k in desc for k in ("bluetooth", "mind", "serial", "standard")):
                candidates.insert(0, p.device)
            else:
                candidates.append(p.device)
    except Exception:
        for i in range(3, 21):
            candidates.append(f"COM{i}")

    seen = []
    for p in candidates:
        if p in seen: continue
        seen.append(p)
        try:
            s = serial.Serial(p, baudrate=57600, timeout=0.5)
            s.close()
            log.info("Found serial port: %s", p)
            return p
        except Exception:
            continue
    return None

# ── serial reader ─────────────────────────────────────────────────────────────

async def serial_reader(port: str) -> None:
    import serial as ser_mod
    loop = asyncio.get_event_loop()
    log.info("Opening %s at 57600 baud...", port)

    def _blocking():
        nonlocal buf
        s = ser_mod.Serial(port, baudrate=57600, timeout=1)
        log.info("Connected to Mind Link on %s", port)
        state["connected"] = True
        buf = bytearray()
        while True:
            chunk = s.read(256)
            if chunk:
                buf.extend(chunk)
                buf = _process_buf(buf)

    buf = bytearray()
    await loop.run_in_executor(None, _blocking)

# ── demo mode ─────────────────────────────────────────────────────────────────

_demo_t0    = time.time()
_next_blink = time.time() + random.uniform(4, 8)

def _update_demo() -> None:
    global _blink_latch, _next_blink
    t = time.time() - _demo_t0
    state["attention"]  = int(max(0, min(100, 65 + 25*math.sin(2*math.pi*t/10) + random.uniform(-3,3))))
    state["meditation"] = int(50 + 15*math.sin(2*math.pi*t/15))
    state["signal"]     = 0
    state["connected"]  = False
    now = time.time()
    if now >= _next_blink:
        _blink_latch    = random.randint(60, 180)
        _next_blink     = now + random.uniform(4, 8)

# ── WebSocket server ──────────────────────────────────────────────────────────

_clients: set = set()

async def _ws_handler(ws) -> None:
    _clients.add(ws)
    log.info("Browser connected (%d total)", len(_clients))
    try:
        await ws.wait_closed()
    finally:
        _clients.discard(ws)
        log.info("Browser disconnected (%d total)", len(_clients))

async def _broadcast_loop(demo: bool) -> None:
    global _blink_latch
    while True:
        if demo:
            _update_demo()
        msg = {**state, "blink": _blink_latch}
        _blink_latch = 0
        if _clients:
            data = json.dumps(msg)
            await asyncio.gather(*[c.send(data) for c in list(_clients)], return_exceptions=True)
        await asyncio.sleep(BROADCAST_INTERVAL)

# ── main ──────────────────────────────────────────────────────────────────────

async def main(port, force_demo: bool) -> None:
    demo = force_demo

    if not force_demo:
        target = port or _find_port()
        if target:
            asyncio.create_task(_serial_task(target))
        else:
            log.info("No serial port found — Demo mode")
            demo = True
    else:
        log.info("Demo mode (--demo flag)")

    async with websockets.serve(_ws_handler, "0.0.0.0", WS_PORT):
        log.info("WebSocket server on ws://localhost:%d", WS_PORT)
        log.info("Open index.html in your browser")
        await _broadcast_loop(demo)


async def _serial_task(port: str) -> None:
    while True:
        try:
            await serial_reader(port)
        except Exception as e:
            log.warning("Serial error: %s — retrying in 5s", e)
            state["connected"] = False
            await asyncio.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MindLink EEG→WebSocket bridge")
    parser.add_argument("--port", help="Serial port, e.g. COM6 or /dev/rfcomm0")
    parser.add_argument("--demo", action="store_true", help="Force demo mode")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.port, args.demo))
    except KeyboardInterrupt:
        log.info("Stopped.")
