#!/usr/bin/env python3
"""Validate effective pointer output in the native mouse-speed scenario log."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
from pathlib import Path
import re


def verify(log):
    active = set()
    peaks = {"normal": 0, "fast": 0, "precision": 0}
    factors = set()
    precision_won_overlap = False
    for line in log.splitlines():
        layer = re.search(r"layer_changed: layer (\d+) state ([01]) locked [01]", line)
        if layer:
            number = int(layer[1])
            if layer[2] == "1":
                active.add(number)
            else:
                active.discard(number)
        mode = "precision" if 10 in active else "fast" if 9 in active else "normal"
        scale = re.search(r"scaled (-?\d+) with (\d+)/(\d+) to (-?\d+) with remainder", line)
        if scale:
            factor = (int(scale[2]), int(scale[3]))
            expected = {"precision": (1, 2), "fast": (9, 5)}
            assert mode in expected and factor == expected[mode], (mode, factor, line)
            factors.add(factor)
            if {9, 10} <= active:
                precision_won_overlap = True
        movement = re.search(r"Mouse movement set to (-?\d+)/(-?\d+)", line)
        if movement:
            x, y = int(movement[1]), int(movement[2])
            if x or y:
                assert 8 in active, "Pointer output continued after Mouse was switched off"
                assert y == 0 and x > 0, (x, y)
                peaks[mode] = max(peaks[mode], x)
    # Nominal speed * 16ms: 1000=>16, 1800=>28/29 with remainder, 500=>8.
    assert peaks == {"normal": 16, "fast": 29, "precision": 8}, peaks
    assert factors == {(9, 5), (1, 2)}, factors
    assert precision_won_overlap, "No precision-over-fast overlap was exercised"
    assert not active.intersection({8, 9, 10}), active
    return peaks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    peaks = verify(args.log.read_text())
    print(f"Native effective speeds validated: normal1000, fast1800, precision500; tick peaks={peaks}")
