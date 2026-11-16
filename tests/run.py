#!/usr/bin/env python3
"""Host checks for generated layout and the production C gesture decision engine.

Does not emulate Zephyr, Bluetooth, split event routing, or physical hardware.
"""
# SPDX-License-Identifier: GPL-2.0-or-later
import hashlib
import json
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
    custom = generator.build_layers()
    # Frozen pre-cleanup bindings; undo only the toggle swap and added Enter.
    matrix = [bindings.copy() for _, _, bindings in custom]
    for (name, _, _), bindings in zip(custom, matrix):
        assert bindings[44] == "&tog MOUSE"
        bindings[44], bindings[57] = bindings[57], bindings[44]
        if name != "MOUSE":
            assert bindings[45] == "&kp RET", name
            bindings[45] = "&none"
    fingerprint = hashlib.sha256(json.dumps(matrix, separators=(",", ":")).encode()).hexdigest()
    assert fingerprint == "97d1adf10cb24bd32ce6d73f84cdb10808295833f9161947bd8abf2ff051859f"
    assert not (ROOT / "reference").exists()
    native = generator.build_layers("native")
    for (_, _, original), (_, _, alternate) in zip(custom, native):
        assert alternate == [generator.NATIVE_BINDINGS.get(binding, binding) for binding in original]
    for backend, filename in generator.KEYMAPS.items():
        assert (ROOT / "config" / filename).read_text() == generator.generate(backend)
    native_text = generator.generate("native")
    assert "aefreedman,thumb-gestures" not in native_text and "&tg " not in native_text
    assert '#include "native_thumb_gestures.dtsi"' in native_text
    native_definitions = (ROOT / "config/native_thumb_gestures.dtsi").read_text()
    assert all(compatible.startswith("zmk,behavior-") for compatible in
               re.findall(r'compatible = "([^"]+)"', native_definitions))
    generated = generator.generate()
    layers = re.findall(r'bindings = <\n(.*?)\n            >;', generated, re.S)
    assert len(layers) == 9
    for (name, _, expected_bindings), layer in zip(custom, layers):
        bindings = [x.strip() for x in re.findall(r'&\w+(?:\s+(?!&)\w+)*', layer)]
        assert len(bindings) == 72, (name, len(bindings))
        assert bindings == expected_bindings, name
        assert bindings[:12] == ["&none"] * 12, name
        assert bindings[44] == "&tog MOUSE", name
        assert bindings.count("&tog MOUSE") == 1, name
        if name == "MOUSE":
            expected = {19: "&kp PG_UP", 21: "&kp PG_DN",
                        20: "&mmv MOVE_UP", 31: "&mmv MOVE_LEFT",
                        32: "&mmv MOVE_DOWN", 33: "&mmv MOVE_RIGHT",
                        44: "&tog MOUSE", 45: "&ms_up", 57: "&ms_down",
                        58: "&mkp LCLK", 59: "&mkp RCLK", 60: "&ms_fast",
                        61: "&ms_precision"}
            assert bindings == [expected.get(index, "&none") for index in range(72)]
            assert "&trans" not in bindings
        if name == "NUM":
            assert bindings[52] == "&kp KP_DOT" and bindings[58] == "&none"
        assert bindings[62:] == ["&none"] * 10, name
        assert not any("SPACE" in bindings[i] for i in range(52, 57)), name
    assert "&rgb_ug" not in generated
    assert "CONFIG_ZMK_RGB_UNDERGLOW=n" in (ROOT / "config/halcyon_elora.conf").read_text()
    for config in ["config/halcyon_elora.conf", "tests/native-sim/native_sim.conf"]:
        assert "CONFIG_ZMK_POINTING=y" in (ROOT / config).read_text()
    assert "#define ZMK_POINTING_DEFAULT_MOVE_VAL 2000" in generated
    assert "input-processors = <&pointer_speed>;" in generated
    assert "MOUSE_FAST" not in generated and "MOUSE_PRECISION" not in generated
    assert "zip_xy_scaler" not in generated
    assert "bindings = <&ms_adjust 0>, <&ms_adjust 2>;" in generated
    assert "bindings = <&ms_adjust 1>, <&ms_adjust 2>;" in generated
    assert "bindings = <&ms_adjust 3>, <&ms_adjust 4>;" in generated
    assert "bindings = <&ms_adjust 5>, <&ms_adjust 6>;" in generated
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
        "&base_select COLEMAK": "layer", "&tg 0": "dual-role",
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
    assert "Mouse toggle 44" not in index and ".highlight" not in index
    print(f"Visuals: {len(layers)} SVGs, 62 correct labels each, consistent action categories passed")


def speed_verifier_checks():
    spec = importlib.util.spec_from_file_location("speed_verifier", ROOT / "tests/check_mouse_speed.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    log = """layer_changed: layer 8 state 1 locked 1
Pointer speed scale: 32 at 2000 mode 0
Mouse movement set to 32/0
Mouse mode state: 1
Pointer speed scale: 64 at 4000 mode 1
Mouse movement set to 64/0
Mouse mode state: 5
Pointer speed scale: 8 at 500 mode 5
Mouse movement set to 8/0
Mouse mode state: 1
Mouse mode state: 0
layer_changed: layer 8 state 0 locked 1
"""
    verifier.verify(log)
    for bad in [log.replace("at 500 mode 5", "at 4000 mode 5"),
                log.replace("Mouse movement set to 64/0", "Mouse movement set to 32/0"),
                log + "Mouse movement set to 1/0\n"]:
        try:
            verifier.verify(bad)
        except AssertionError:
            pass
        else:
            raise AssertionError("Mouse speed verifier accepted an invalid trace")
    print("Effective-speed verifier: accepts expected trace; rejects wrong priority/speed/stuck output")


def native_verifier_checks():
    spec = importlib.util.spec_from_file_location("native_verifier", ROOT / "tests/check_native_gestures.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    prefix = "<dbg> zmk: "
    log = "\n".join([
        "[00:00:00.000,000] " + prefix + "54 tap dance pressed",
        "[00:00:00.200,000] " + prefix + "hid_listener_keycode_pressed: usage_page 0x07 keycode 0xE1",
        "[00:00:00.600,000] " + prefix + "54 tap dance pressed",
        "[00:00:01.000,000] " + prefix + "hid_listener_keycode_pressed: usage_page 0x07 keycode 0xE1",
        *[f"[00:00:03.00{i},000] " + prefix + f"hid_listener_keycode_{state}: usage_page 0x07 keycode {code}"
          for i, (state, code) in enumerate([
              ("pressed", "0xE1"), ("pressed", "0xE0"), ("released", "0xE1"),
              ("pressed", "0x04"), ("released", "0xE0"), ("released", "0x04")])],
    ])
    assert verifier.verify(log) == 400
    for bad in ["", log.replace("01.000,000", "00.800,000"), log.replace("0xE0", "0xE1")]:
        try:
            verifier.verify(bad)
        except AssertionError:
            pass
        else:
            raise AssertionError("Native gesture verifier accepted incorrect timing/modifier expiry")
    print("Native trace verifier: checks latency and independent sticky expiration")


def main():
    generator = layout_checks()
    speed_verifier_checks()
    native_verifier_checks()
    compiler = os.environ.get("CC") or shutil.which("clang") or shutil.which("gcc")
    if not compiler:
        raise SystemExit("Install Clang/GCC or set CC")
    with tempfile.TemporaryDirectory(prefix="elora-tests-", dir=ROOT) as directory:
        cases = {"test_thumb_gestures": ["src/thumb_gestures.c", "tests/test_thumb_gestures.c"],
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
