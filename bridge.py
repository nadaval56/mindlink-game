#!/usr/bin/env python3
"""
MindLink Bridge — connects ThinkGear/NeuroSky EEG to browser via WebSocket.

Priority:
  1. ThinkGear Connector (TGC) on localhost:13854
  2. Direct Bluetooth serial (--port / auto-detect)
  3. Demo mode (synthesized data)
"""

import asyncio
import json
import math
import random
import socket
import struct
import time
import argparse
import sys
import logging

try:
    import websockets
except ImportError:
    print("ERROR: run  pip install -r requirements.txt  first", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger(__name__)

WS_PORT = 8765
TGC_HOST = "127.0.0.1"
TGC_PORT = 13854
BROADCAST_INTERVAL = 0.1  # seconds

# ── shared state ────────────────────────────────────────────────────────────

state = {
    "attention": 0,
    "meditation": 0,
    "blink": 0,
    "signal": 200,
    "connected": False,
}

_blink_latch = 0          # consumed after one broadcast
_demo_t0 = time.time()


# ── ThinkGear Connector reader ───────────────────────────────────────────────

def _parse_tgc_json(line: bytes) -> None:
    """Parse a JSON line from ThinkGear Connector and update state."""
    global _blink_latch
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return

    if "poorSignalLevel" in obj:
        state["signal"] = obj["poorSignalLevel"]
        state["connected"] = obj["poorSignalLevel"] < 200

    if "eSense" in obj:
        es = obj["eSense"]
        if "attention" in es:
            state["attention"] = es["attention"]
        if "meditation" in es:
            state["meditation"] = es["meditation"]

    if "blinkStrength" in obj:
        _blink_latch = obj["blinkStrength"]


async def tgc_reader() -> None:
    """Read JSON stream from ThinkGear Connector."""
    log.info("Connecting to ThinkGear Connector on %s:%d", TGC_HOST, TGC_PORT)
    reader, writer = await asyncio.open_connection(TGC_HOST, TGC_PORT)
    # Send JSON-format request
    writer.write(b'{"enableRawOutput": false, "format": "Json"}')
    await writer.drain()
    log.info("Connected to ThinkGear Connector")
    while True:
        line = await reader.readline()
        if not line:
            raise ConnectionResetError("TGC connection closed")
        _parse_tgc_json(line)


# ── Serial / Bluetooth reader ────────────────────────────────────────────────

SYNC_BYTE = 0xAA
EXCODE = 0x55

def _parse_thinkgear_payload(payload: bytes) -> None:
    global _blink_latch
    i = 0
    while i < len(payload):
        code = payload[i]; i += 1
        if code == EXCODE:
            continue
        if code >= 0x80:
            if i >= len(payload):
                break
            vlen = payload[i]; i += 1
            val = payload[i:i+vlen]; i += vlen
            if code == 0x80:  # raw EEG (ignore)
                pass
            elif code == 0x83:  # ASIC EEG power (ignore)
                pass
        else:
            if i >= len(payload):
                break
            val_byte = payload[i]; i += 1
            if code == 0x02:
                state["signal"] = val_byte
                state["connected"] = (val_byte < 200)
            elif code == 0x04:
                state["attention"] = val_byte
            elif code == 0x05:
                state["meditation"] = val_byte
            elif code == 0x16:
                _blink_latch = val_byte


async def serial_reader(port: str) -> None:
    try:
        import serial_asyncio
    except ImportError:
        try:
            import serial
        except ImportError:
            raise RuntimeError("pyserial not installed")

        # Fallback: blocking serial in executor
        import serial as ser_mod
        loop = asyncio.get_event_loop()

        def _blocking():
            s = ser_mod.Serial(port, baudrate=57600, timeout=1)
            log.info("Opened serial port %s", port)
            buf = bytearray()
            while True:
                chunk = s.read(256)
                if chunk:
                    buf.extend(chunk)
                    # scan for packets
                    while len(buf) >= 4:
                        if buf[0] != SYNC_BYTE or buf[1] != SYNC_BYTE:
                            buf.pop(0)
                            continue
                        plen = buf[2]
                        if plen == SYNC_BYTE:
                            buf.pop(0)
                            continue
                        if len(buf) < 4 + plen:
                            break
                        payload = buf[3:3+plen]
                        checksum_given = buf[3+plen]
                        checksum_calc = (~sum(payload)) & 0xFF
                        if checksum_calc == checksum_given:
                            _parse_thinkgear_payload(bytes(payload))
                        buf = buf[4+plen:]

        await loop.run_in_executor(None, _blocking)
        return

    reader, _ = await serial_asyncio.open_serial_connection(url=port, baudrate=57600)
    log.info("Opened serial port %s via serial_asyncio", port)
    buf = bytearray()
    while True:
        chunk = await reader.read(256)
        buf.extend(chunk)
        while len(buf) >= 4:
            if buf[0] != SYNC_BYTE or buf[1] != SYNC_BYTE:
                buf.pop(0)
                continue
            plen = buf[2]
            if plen == SYNC_BYTE:
                buf.pop(0)
                continue
            if len(buf) < 4 + plen:
                break
            payload = buf[3:3+plen]
            checksum_given = buf[3+plen]
            checksum_calc = (~sum(payload)) & 0xFF
            if checksum_calc == checksum_given:
                _parse_thinkgear_payload(bytes(payload))
            buf = buf[4+plen:]


def _auto_detect_port() -> str | None:
    """Try to find a Mind Link serial port automatically."""
    import glob
    candidates = (
        glob.glob("/dev/tty.MindLink*") +
        glob.glob("/dev/ttyACM*") +
        glob.glob("/dev/rfcomm*") +
        [f"COM{i}" for i in range(3, 13)]
    )
    for p in candidates:
        try:
            import serial
            s = serial.Serial(p, baudrate=57600, timeout=0.5)
            s.close()
            log.info("Auto-detected port: %s", p)
            return p
        except Exception:
            continue
    return None


# ── Demo mode ────────────────────────────────────────────────────────────────

_next_blink = time.time() + random.uniform(4, 8)

def _update_demo() -> None:
    global _blink_latch, _next_blink
    t = time.time() - _demo_t0
    # Attention: sine wave 40–90 with small noise, period ~10s
    state["attention"] = int(65 + 25 * math.sin(2 * math.pi * t / 10) + random.uniform(-3, 3))
    state["attention"] = max(0, min(100, state["attention"]))
    state["meditation"] = int(50 + 15 * math.sin(2 * math.pi * t / 15))
    state["signal"] = 0
    state["connected"] = False
    now = time.time()
    if now >= _next_blink:
        _blink_latch = random.randint(60, 180)
        _next_blink = now + random.uniform(4, 8)


# ── WebSocket server ─────────────────────────────────────────────────────────

_clients: set = set()


async def _broadcast_loop(demo: bool) -> None:
    global _blink_latch
    while True:
        if demo:
            _update_demo()
        msg = {
            "attention": state["attention"],
            "meditation": state["meditation"],
            "blink": _blink_latch,
            "signal": state["signal"],
            "connected": state["connected"],
        }
        _blink_latch = 0  # consume after one broadcast
        if _clients:
            data = json.dumps(msg)
            await asyncio.gather(*[c.send(data) for c in list(_clients)], return_exceptions=True)
        await asyncio.sleep(BROADCAST_INTERVAL)


async def _ws_handler(ws) -> None:
    _clients.add(ws)
    log.info("Browser connected (%d total)", len(_clients))
    try:
        await ws.wait_closed()
    finally:
        _clients.discard(ws)
        log.info("Browser disconnected (%d total)", len(_clients))


# ── main ─────────────────────────────────────────────────────────────────────

async def main(port: str | None, force_demo: bool) -> None:
    demo = force_demo

    async def _start_eeg():
        nonlocal demo
        if force_demo:
            log.info("Demo mode forced via --demo")
            return

        # Try TGC first
        try:
            await asyncio.wait_for(tgc_reader(), timeout=5)
            return
        except (ConnectionRefusedError, asyncio.TimeoutError, OSError):
            log.info("TGC not available, trying serial...")

        # Try serial
        target_port = port or _auto_detect_port()
        if target_port:
            try:
                await serial_reader(target_port)
                return
            except Exception as e:
                log.warning("Serial failed (%s), falling back to demo", e)

        log.info("No EEG source found — running in Demo mode")
        demo = True

    async def _eeg_task():
        while True:
            try:
                await _start_eeg()
            except Exception as e:
                log.warning("EEG reader crashed: %s — retrying in 5s", e)
                await asyncio.sleep(5)

    eeg_task = asyncio.create_task(_eeg_task())

    # Give EEG 2s to connect before starting broadcast
    await asyncio.sleep(2)

    broadcast_task = asyncio.create_task(_broadcast_loop(demo))

    async with websockets.serve(_ws_handler, "0.0.0.0", WS_PORT):
        log.info("WebSocket server listening on ws://localhost:%d", WS_PORT)
        log.info("Open index.html in your browser (or GitHub Pages)")
        await asyncio.gather(eeg_task, broadcast_task)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MindLink EEG→WebSocket bridge")
    parser.add_argument("--port", help="Serial port (e.g. COM5 or /dev/rfcomm0)")
    parser.add_argument("--demo", action="store_true", help="Force demo mode")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.port, args.demo))
    except KeyboardInterrupt:
        log.info("Stopped.")
