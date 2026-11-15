#!/usr/bin/env python3
"""Validate effective pointer output, modes, and optional runtime adjustment trace."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
from pathlib import Path
import re


def verify(log, adjustments=False):
    active = set()
    peaks = {}
    factors = set()
    changes = []
    normal_target = 2000
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
        change = re.search(r"Normal mouse speed: (\d+)", line)
        if change:
            changes.append(int(change[1]))
        normal = re.search(r"Normal pointer scale: -?\d+ at (\d+)", line)
        if normal:
            assert mode == "normal", "Normal adjustment incorrectly applied to Fast/Precision"
            normal_target = int(normal[1])
            assert 100 <= normal_target <= 10000 and normal_target % 100 == 0
        scale = re.search(r"scaled (-?\d+) with (\d+)/(\d+) to (-?\d+) with remainder", line)
        if scale:
            factor = (int(scale[2]), int(scale[3]))
            expected = {"precision": (1, 4), "fast": (2, 1)}
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
                key = f"normal@{normal_target}" if mode == "normal" else mode
                peaks[key] = max(peaks.get(key, 0), x)
    # Plateau speed * 16ms, rounded across ticks by remainder tracking.
    expected_peaks = {"normal@2000": 32, "fast": 64, "precision": 8}
    if adjustments:
        expected_peaks.update({"normal@2100": 34, "normal@1900": 31})
        assert changes == [2100, 2000, 1900, 2000, 2100, 2200, 2000], changes
    else:
        assert not changes, changes
        assert precision_won_overlap, "No precision-over-fast overlap was exercised"
    assert peaks == expected_peaks, peaks
    assert factors == {(2, 1), (1, 4)}, factors
    assert not active.intersection({8, 9, 10}), active
    return peaks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--adjustments", action="store_true")
    args = parser.parse_args()
    peaks = verify(args.log.read_text(), adjustments=args.adjustments)
    print(f"Native effective speeds validated: normal2000, fast4000, precision500; tick peaks={peaks}")
