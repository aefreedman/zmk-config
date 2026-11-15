#!/usr/bin/env python3
"""Check measured native gesture latency and independently expiring sticky modifiers."""
# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import re
import sys


def verify(log):
    starts, shifts, events = [], [], []
    for line in log.splitlines():
        stamp = re.search(r"\[(\d+):(\d+):(\d+)\.(\d{3}),(\d{3})\]", line)
        if not stamp:
            continue
        h, m, s, ms, us = map(int, stamp.groups())
        now = ((h * 60 + m) * 60 + s) * 1000 + ms + us / 1000
        if "54 tap dance pressed" in line:
            starts.append(now)
        event = re.search(r"hid_listener_keycode_(pressed|released): usage_page 0x07 keycode 0x([0-9A-Fa-f]+)", line)
        if event:
            state, code = event[1], int(event[2], 16)
            events.append((state, code))
            if state == "pressed" and code == 0xE1:
                shifts.append(now)
    assert len(starts) >= 2 and len(shifts) >= 2, "Missing timestamped gesture trace"
    delay = shifts[1] - starts[1]
    assert 390 <= delay <= 430, f"Expected nested ~400ms hold, observed {delay}ms"
    assert events[-6:] == [
        ("pressed", 0xE1), ("pressed", 0xE0), ("released", 0xE1),
        ("pressed", 0x04), ("released", 0xE0), ("released", 0x04),
    ], events[-6:]
    return delay


if __name__ == "__main__":
    delay = verify(Path(sys.argv[1]).read_text())
    print(f"Native differences verified: nested hold {delay:g}ms; Shift expires independently of later Ctrl")
