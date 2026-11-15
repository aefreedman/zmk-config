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
    assert len(layers) == 11
    for name, layer in zip([*generator.LAYERS, "MOUSE", "MOUSE_FAST", "MOUSE_PRECISION"], layers):
        bindings = [x.strip() for x in re.findall(r'&\w+(?:\s+(?!&)\w+)*', layer)]
        assert len(bindings) == 72, (name, len(bindings))
        assert bindings[:12] == ["&none"] * 12, name
        assert bindings[57] == "&tog MOUSE", name
        if name == "MOUSE":
            expected = {19: "&kp PG_UP", 21: "&kp PG_DN",
                        20: "&mmv MOVE_UP", 31: "&mmv MOVE_LEFT",
                        32: "&mmv MOVE_DOWN", 33: "&mmv MOVE_RIGHT",
                        58: "&mkp LCLK", 59: "&mkp RCLK", 60: "&ms_fast"}
            for index in generator.POSITIONS:
                assert bindings[index] == expected.get(index, "&trans"), (name, index)
            assert bindings[61] == "&ms_precision"
            assert bindings[44] == "&ms_down" and bindings[45] == "&ms_up"
            arrows = {"KC_UP": "MOVE_UP", "KC_LEFT": "MOVE_LEFT",
                      "KC_DOWN": "MOVE_DOWN", "KC_RGHT": "MOVE_RIGHT"}
            for index, token in zip(generator.POSITIONS, original["NUM"]):
                if token in arrows:
                    assert bindings[index] == "&mmv " + arrows[token]
        elif name in {"MOUSE_FAST", "MOUSE_PRECISION"}:
            for index in [*generator.POSITIONS, 44, 45, 52, 61]:
                assert bindings[index] == "&trans", (name, index)
        else:
            for index, token in zip(generator.POSITIONS, original[name]):
                expected = "&none" if name == "NUM" and index == 58 else generator.binding(token)
                assert bindings[index] == expected, (name, index, token)
            if name == "NUM":
                assert bindings[52] == "&kp KP_DOT" and bindings[58] == "&none"
        extras = {57}
        if name in {"MOUSE", "MOUSE_FAST", "MOUSE_PRECISION"}:
            extras.update({44, 45, 61})
        if name in {"NUM", "MOUSE_FAST", "MOUSE_PRECISION"}:
            extras.add(52)
        for index in set(range(72)) - set(generator.POSITIONS) - extras:
            assert bindings[index] == "&none", (name, index)
        assert not any("SPACE" in bindings[i] for i in range(52, 57)), name
    assert "&rgb_ug" not in generated
    assert "CONFIG_ZMK_RGB_UNDERGLOW=n" in (ROOT / "config/halcyon_elora.conf").read_text()
    for config in ["config/halcyon_elora.conf", "tests/native-sim/native_sim.conf"]:
        assert "CONFIG_ZMK_POINTING=y" in (ROOT / config).read_text()
    assert "#define ZMK_POINTING_DEFAULT_MOVE_VAL 2000" in generated
    assert "input-processors = <&normal_speed>;" in generated
    assert "input-processors = <&zip_xy_scaler 2 1>;" in generated
    assert "input-processors = <&zip_xy_scaler 1 4>;" in generated
    assert "bindings = <&ms_adjust 0>, <&ms_adjust 2>;" in generated
    assert "bindings = <&ms_adjust 1>, <&ms_adjust 2>;" in generated
    assert generated.index("layers = <MOUSE_PRECISION>") < generated.index("layers = <MOUSE_FAST>")
    for mode in ["MOUSE_FAST", "MOUSE_PRECISION"]:
        assert f"bindings = <&mo {mode}>, <&tog {mode}>;" in generated
    print("Layout: 2000/4000/500 speeds, normal ±100/reset, PgUp/PgDn, blank top/extras, RGB off passed")
    return generator


def visual_checks(directory, generator):
    output = Path(directory) / "keymap"
    subprocess.run([sys.executable, str(ROOT / "scripts/render_keymap.py"),
                    "--output", str(output)], check=True)
    layers = generator.build_layers()
    assert {p.name for p in output.iterdir()} == {
        "index.html", *(name.lower() + ".svg" for name, _, _ in layers)}
    namespace = {"s": "http://www.w3.org/2000/svg"}
    categories = {
        "&kp A": "normal", "&kp SPACE": "normal",
        "&kp LGUI": "modifier", "&kp LSHFT": "modifier",
        "&tog MOUSE": "layer", "&tog DJMAX": "layer", "&mo ADJUST": "layer",
        "&base_select COLEMAK": "layer", "&rd 0": "dual-role",
        "&lt NUM BSPC": "dual-role", "&ms_fast": "dual-role",
        "&ms_precision": "dual-role", "&ms_down": "dual-role", "&ms_up": "dual-role",
        "&kp PG_UP": "navigation", "&kp PG_DN": "navigation", "&kp LEFT": "navigation",
        "&mmv MOVE_LEFT": "navigation", "&mkp LCLK": "navigation",
        "&kp C_VOL_UP": "media", "&kp F1": "system", "&bootloader": "system",
        "&none": "blank", "&trans": "transparent",
    }
    seen_categories = set()
    for name, _, bindings in layers:
        svg = ET.parse(output / (name.lower() + ".svg")).getroot()
        keys = svg.findall("s:g", namespace)
        assert [int(key.attrib["data-position"]) for key in keys] == list(range(62))
        for pos, key in enumerate(keys):
            assert "highlight" not in key.attrib["class"]
            if bindings[pos] in categories:
                assert key.attrib["class"] == "key " + categories[bindings[pos]], (name, pos)
                seen_categories.add(bindings[pos])
            assert key.findtext("s:title", namespaces=namespace) == f"Position {pos}: {bindings[pos]}"
            if bindings[pos] == "&kp COLN":
                assert key.findtext("s:text[@class='legend']", namespaces=namespace) == ":"
    assert seen_categories == set(categories)
    index = (output / "index.html").read_text()
    assert index.count("<svg ") == len(layers) and "<script" not in index
    assert 'aria-label="Key categories"' in index
    assert "Mouse toggle 57" not in index and ".highlight" not in index
    print(f"Visuals: {len(layers)} SVGs, 62 correct labels each, consistent action categories passed")


def speed_verifier_checks():
    spec = importlib.util.spec_from_file_location("speed_verifier", ROOT / "tests/check_mouse_speed.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    log = """layer_changed: layer 8 state 1 locked 1
Normal pointer scale: 32 at 2000
Mouse movement set to 32/0
layer_changed: layer 9 state 1 locked 0
scaled 32 with 2/1 to 64 with remainder 0
Mouse movement set to 64/0
layer_changed: layer 10 state 1 locked 0
scaled 32 with 1/4 to 8 with remainder 0
Mouse movement set to 8/0
layer_changed: layer 10 state 0 locked 0
layer_changed: layer 9 state 0 locked 0
layer_changed: layer 8 state 0 locked 1
"""
    verifier.verify(log)
    for bad in [log.replace("with 1/4", "with 2/1"),
                log.replace("Mouse movement set to 64/0", "Mouse movement set to 32/0"),
                log + "Mouse movement set to 1/0\n"]:
        try:
            verifier.verify(bad)
        except AssertionError:
            pass
        else:
            raise AssertionError("Mouse speed verifier accepted an invalid trace")
    print("Effective-speed verifier: accepts expected trace; rejects wrong priority/speed/stuck output")


def main():
    generator = layout_checks()
    speed_verifier_checks()
    compiler = os.environ.get("CC") or shutil.which("clang") or shutil.which("gcc")
    if not compiler:
        raise SystemExit("Install Clang/GCC or set CC")
    with tempfile.TemporaryDirectory(prefix="elora-tests-", dir=ROOT) as directory:
        cases = {"test_dance": ["src/reviung_dance.c", "tests/test_dance.c"],
                 "test_mouse_speed": ["tests/test_mouse_speed.c"]}
        for name, sources in cases.items():
            binary = Path(directory) / name
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic",
                            "-fsanitize=address,undefined", "-g", "-I", str(ROOT / "src"),
                            *(str(ROOT / source) for source in sources),
                            "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
        visual_checks(directory, generator)

if __name__ == "__main__":
    main()
