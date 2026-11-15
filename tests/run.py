#!/usr/bin/env python3
"""Host checks for generated layout and the production C gesture decision engine.

Does not emulate Zephyr, Bluetooth, split event routing, or physical hardware.
"""
# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
import os
from pathlib import Path
import re
import shutil
import sys
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

def layout_checks():
    spec = importlib.util.spec_from_file_location("generator", ROOT / "scripts/generate_keymap.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    assert len(generator.POSITIONS) == len(set(generator.POSITIONS)) == 41
    assert generator.POSITIONS[36:] == [53, 54, 58, 59, 60]
    assert generator.POSITIONS[37] == 54  # Left middle: Shift/Symbol.
    assert generator.POSITIONS[39] == 59  # Right middle: NUM/Backspace.
    assert generator.POSITIONS[:36] == [*range(12, 42), *range(46, 52)]
    original = generator.source_layers()
    assert set(original) == set(generator.LAYERS)
    generated = generator.generate()
    assert (ROOT / "config/halcyon_elora.keymap").read_text() == generated
    layers = re.findall(r'bindings = <\n(.*?)\n            >;', generated, re.S)
    assert len(layers) == 9
    for name, layer in zip([*generator.LAYERS, "MOUSE"], layers):
        bindings = [x.strip() for x in re.findall(r'&\w+(?:\s+(?!&)\w+)*', layer)]
        assert len(bindings) == 72, (name, len(bindings))
        assert bindings[:12] == ["&none"] * 12, name
        assert bindings[57] == "&tog MOUSE", name
        if name == "MOUSE":
            expected = {20: "&mmv MOVE_UP", 31: "&mmv MOVE_LEFT",
                        32: "&mmv MOVE_DOWN", 33: "&mmv MOVE_RIGHT",
                        58: "&mkp LCLK", 59: "&mkp RCLK"}
            for index in generator.POSITIONS:
                assert bindings[index] == expected.get(index, "&trans"), (name, index)
            arrows = {"KC_UP": "MOVE_UP", "KC_LEFT": "MOVE_LEFT",
                      "KC_DOWN": "MOVE_DOWN", "KC_RGHT": "MOVE_RIGHT"}
            for index, token in zip(generator.POSITIONS, original["NUM"]):
                if token in arrows:
                    assert bindings[index] == "&mmv " + arrows[token]
        else:
            for index, token in zip(generator.POSITIONS, original[name]):
                assert bindings[index] == generator.binding(token), (name, index, token)
        for index in set(range(72)) - set(generator.POSITIONS) - {57}:
            assert bindings[index] == "&none", (name, index)
        assert not any("SPACE" in bindings[i] for i in range(52, 57)), name
    assert "&rgb_ug" not in generated
    assert "CONFIG_ZMK_RGB_UNDERGLOW=n" in (ROOT / "config/halcyon_elora.conf").read_text()
    for config in ["config/halcyon_elora.conf", "tests/native-sim/native_sim.conf"]:
        assert "CONFIG_ZMK_POINTING=y" in (ROOT / config).read_text()
    print("Layout: 9 layers, mouse toggle/directions/clicks, blank top/extras, right-only Space, RGB off passed")
    return generator


def visual_checks(directory, generator):
    output = Path(directory) / "keymap"
    subprocess.run([sys.executable, str(ROOT / "scripts/render_keymap.py"),
                    "--output", str(output)], check=True)
    layers = generator.build_layers()
    assert {p.name for p in output.iterdir()} == {
        "index.html", *(name.lower() + ".svg" for name, _, _ in layers)}
    namespace = {"s": "http://www.w3.org/2000/svg"}
    for name, _, bindings in layers:
        svg = ET.parse(output / (name.lower() + ".svg")).getroot()
        keys = svg.findall("s:g", namespace)
        assert [int(key.attrib["data-position"]) for key in keys] == list(range(62))
        for pos, key in enumerate(keys):
            assert key.findtext("s:title", namespaces=namespace) == f"Position {pos}: {bindings[pos]}"
            if bindings[pos] == "&kp COLN":
                assert key.findtext("s:text[@class='legend']", namespaces=namespace) == ":"
    index = (output / "index.html").read_text()
    assert index.count("<svg ") == 9 and "<script" not in index
    print("Visuals: nine offline SVGs, 62 correctly labeled positions each, HTML overview passed")


def main():
    generator = layout_checks()
    compiler = os.environ.get("CC") or shutil.which("clang") or shutil.which("gcc")
    if not compiler:
        raise SystemExit("Install Clang/GCC or set CC")
    with tempfile.TemporaryDirectory(prefix="elora-tests-", dir=ROOT) as directory:
        binary = Path(directory) / "test_dance"
        subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic",
                        "-fsanitize=address,undefined", "-g", "-I", str(ROOT / "src"),
                        str(ROOT / "src/reviung_dance.c"), str(ROOT / "tests/test_dance.c"),
                        "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
        visual_checks(directory, generator)

if __name__ == "__main__":
    main()
