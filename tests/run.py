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
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def layout_checks():
    spec = importlib.util.spec_from_file_location("generator", ROOT / "scripts/generate_keymap.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    assert len(generator.POSITIONS) == len(set(generator.POSITIONS)) == 41
    assert generator.POSITIONS[38] == 57  # Original Space is right inner thumb.
    assert generator.POSITIONS[:36] == [*range(12, 42), *range(46, 52)]
    original = generator.source_layers()
    assert set(original) == set(generator.LAYERS)
    generated = generator.generate()
    assert (ROOT / "config/halcyon_elora.keymap").read_text() == generated
    layers = re.findall(r'bindings = <\n(.*?)\n            >;', generated, re.S)
    assert len(layers) == 8
    for name, layer in zip(generator.LAYERS, layers):
        bindings = [x.strip() for x in re.findall(r'&\w+(?:\s+(?!&)\w+)*', layer)]
        assert len(bindings) == 72, (name, len(bindings))
        assert bindings[:12] == ["&none"] * 12, name
        for index, token in zip(generator.POSITIONS, original[name]):
            assert bindings[index] == generator.binding(token), (name, index, token)
        for index in set(range(72)) - set(generator.POSITIONS):
            assert bindings[index] == "&none", (name, index)
        assert not any("SPACE" in bindings[i] for i in range(52, 57)), name
    assert "&rgb_ug" not in generated
    assert "CONFIG_ZMK_RGB_UNDERGLOW=n" in (ROOT / "config/halcyon_elora.conf").read_text()
    print("Layout: all 8 layers, 72 positions, blank top/extras, right-only Space, RGB off passed")

def main():
    layout_checks()
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

if __name__ == "__main__":
    main()
