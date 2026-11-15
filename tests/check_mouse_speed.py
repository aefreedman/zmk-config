#!/usr/bin/env python3
"""Validate effective pointer output, runtime modes, and optional speed adjustments."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
from pathlib import Path
import re


def verify(log, adjustments=False):
    mouse_active = False
    mode_state = 0
    sample_mode = "normal"
    sample_speed = 2000
    sample_delta = 0
    peaks = {}
    changes = []
    precision_won_overlap = False
    for line in log.splitlines():
        layer = re.search(r"layer_changed: layer (\d+) state ([01]) locked [01]", line)
        if layer:
            assert int(layer[1]) < 9, "Speed controls unexpectedly used additional layers"
            if layer[1] == "8":
                mouse_active = layer[2] == "1"
        change = re.search(r"Normal mouse speed: (\d+)", line)
        if change:
            changes.append(int(change[1]))
        mode = re.search(r"Mouse mode state: (\d+)", line)
        if mode:
            mode_state = int(mode[1])
        scale = re.search(r"Pointer speed scale: (-?\d+) at (\d+) mode (\d+)", line)
        if scale:
            sample_delta, sample_speed, flags = map(int, scale.groups())
            assert 0 <= flags <= 15
            sample_mode = "precision" if flags & 12 else "fast" if flags & 3 else "normal"
            if sample_mode == "normal":
                assert 100 <= sample_speed <= 10000 and sample_speed % 100 == 0
            else:
                assert sample_speed == {"fast": 4000, "precision": 500}[sample_mode]
            if flags & 12 and flags & 3:
                precision_won_overlap = True
        movement = re.search(r"Mouse movement set to (-?\d+)/(-?\d+)", line)
        if movement:
            x, y = int(movement[1]), int(movement[2])
            if x or y:
                assert mouse_active, "Pointer output continued after Mouse was switched off"
                assert y == 0 and x > 0 and x == sample_delta, (x, y, sample_delta)
                key = f"normal@{sample_speed}" if sample_mode == "normal" else sample_mode
                peaks[key] = max(peaks.get(key, 0), x)
    expected_peaks = {"normal@2000": 32, "fast": 64, "precision": 8}
    if adjustments:
        expected_peaks.update({"normal@2100": 34, "normal@1900": 31})
        assert changes == [2100, 2000, 1900, 2000, 2100, 2200, 2000], changes
    else:
        assert not changes, changes
        assert precision_won_overlap, "No precision-over-fast overlap was exercised"
    assert peaks == expected_peaks, peaks
    assert not mouse_active and mode_state == 0
    return peaks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--adjustments", action="store_true")
    args = parser.parse_args()
    peaks = verify(args.log.read_text(), adjustments=args.adjustments)
    print(f"Native runtime speeds validated without extra layers: normal2000, fast4000, precision500; peaks={peaks}")
