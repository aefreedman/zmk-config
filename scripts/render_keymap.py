#!/usr/bin/env python3
"""Render the generator's Elora layers as offline SVGs and an HTML index."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
from dataclasses import dataclass
from html import escape
import importlib.util
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
# Numeric geometry from splitkb.com, splitkb_halcyon_elora's first 62 keys:
# https://github.com/splitkb/zmk-halcyon-module/blob/0b95571b332862a6fda8d62a0f0a4c6ccd7895dc/boards/shields/halcyon_elora/halcyon_elora-layouts.dtsi
# All keys are 100 x 100, with zero rotation/origin (units: hundredths).
KEY_POSITIONS = (
    (0, 75), (100, 75), (200, 25), (300, 0), (400, 25), (500, 50),
    (1050, 50), (1150, 25), (1250, 0), (1350, 25), (1450, 75), (1550, 75),
    (0, 175), (100, 175), (200, 125), (300, 100), (400, 125), (500, 150),
    (1050, 150), (1150, 125), (1250, 100), (1350, 125), (1450, 175), (1550, 175),
    (0, 275), (100, 275), (200, 225), (300, 200), (400, 225), (500, 250),
    (1050, 250), (1150, 225), (1250, 200), (1350, 225), (1450, 275), (1550, 275),
    (0, 375), (100, 375), (200, 325), (300, 300), (400, 325), (500, 350),
    (600, 400), (700, 425), (850, 425), (950, 400), (1050, 350), (1150, 325),
    (1250, 300), (1350, 325), (1450, 375), (1550, 375), (250, 425), (350, 425),
    (450, 450), (550, 500), (650, 525), (900, 525), (1000, 500), (1100, 450),
    (1200, 425), (1300, 425),
)


@dataclass(frozen=True)
class PhysicalKey:
    width: int
    height: int
    x: int
    y: int
    rotation: int
    origin_x: int
    origin_y: int

    def corners(self):
        angle = math.radians(self.rotation / 100)
        for x, y in ((self.x, self.y), (self.x + self.width, self.y),
                     (self.x, self.y + self.height),
                     (self.x + self.width, self.y + self.height)):
            dx, dy = x - self.origin_x, y - self.origin_y
            yield (self.origin_x + dx * math.cos(angle) - dy * math.sin(angle),
                   self.origin_y + dx * math.sin(angle) + dy * math.cos(angle))


def read_geometry(path):
    source = path.read_text()
    block = re.search(r"splitkb_halcyon_elora:\s*splitkb_halcyon_elora\s*\{(.*?)\};", source, re.S)
    if not block:
        raise ValueError("Missing splitkb_halcyon_elora physical layout")
    keys = []
    for attrs in re.findall(r"<&key_physical_attrs\s+([^>]+)>", block[1]):
        # DT negative cells can be parenthesized; all physical units are 1/100.
        values = [int(value) for value in re.findall(r"-?\d+", attrs)]
        if len(values) != 7:
            raise ValueError(f"Expected seven physical attributes: {attrs}")
        key = PhysicalKey(*values)
        if key.width <= 0 or key.height <= 0:
            raise ValueError("Physical key dimensions must be positive")
        keys.append(key)
    if len(keys) != 62:
        raise ValueError(f"Expected 62 physical keys, got {len(keys)}")
    return keys


def load_layers(repo):
    path = repo / "scripts/generate_keymap.py"
    spec = importlib.util.spec_from_file_location("keymap_generator", path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    if not hasattr(module, "build_layers"):
        raise ValueError(f"{path} must expose build_layers()")
    layers = module.build_layers()
    if len(layers) != 9:
        raise ValueError(f"Expected nine layers, got {len(layers)}")
    names = set()
    for name, label, bindings in layers:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) or name.lower() in names:
            raise ValueError(f"Invalid or duplicate layer name: {name}")
        names.add(name.lower())
        if not isinstance(label, str) or len(bindings) != 72:
            raise ValueError(f"{name}: expected label and 72 bindings")
        if not all(isinstance(binding, str) for binding in bindings):
            raise ValueError(f"{name}: bindings must be strings")
    if "mouse" not in names:
        raise ValueError("Missing MOUSE layer")
    return layers


KEY_LABELS = {
    "SPACE": "Space", "RET": "Enter", "BSPC": "Bksp", "DEL": "Delete",
    "ESC": "Esc", "TAB": "Tab", "LCTRL": "Ctrl", "RCTRL": "R Ctrl",
    "LSHFT": "Shift", "RSHFT": "R Shift", "LALT": "Alt", "RALT": "R Alt",
    "LGUI": "GUI", "RGUI": "R GUI", "LEFT": "←", "RIGHT": "→",
    "UP": "↑", "DOWN": "↓", "PG_UP": "PgUp", "PG_DN": "PgDn",
    "HOME": "Home", "END": "End", "INS": "Insert", "CAPS": "Caps",
    "SEMI": ";", "SQT": "'", "COMMA": ",", "DOT": ".", "FSLH": "/",
    "MINUS": "-", "EQUAL": "=", "LBKT": "[", "RBKT": "]", "BSLH": "\\",
    "GRAVE": "`", "DQT": '"', "LPAR": "(", "RPAR": ")", "LBRC": "{",
    "RBRC": "}", "UNDER": "_", "DLLR": "$", "PRCNT": "%", "AMPS": "&",
    "QMARK": "?", "EXCL": "!", "AT": "@", "HASH": "#", "CARET": "^",
    "STAR": "*", "PLUS": "+", "TILDE": "~", "LT": "<", "GT": ">",
    "COLON": ":", "COLN": ":", "PIPE": "|", "C_VOL_DN": "Vol −", "C_VOL_UP": "Vol +",
    "C_MUTE": "Mute", "C_PREV": "Previous", "C_NEXT": "Next",
    "C_PLAY_PAUSE": "Play/Pause", "KP_DOT": "Num .", "KP_DIVIDE": "Num /",
    "KP_MULTIPLY": "Num *", "KP_PLUS": "Num +",
}


def key_label(code):
    return code[1:] if re.fullmatch(r"N[0-9]", code) else KEY_LABELS.get(code, code)


CATEGORIES = {
    "normal": ("Typing / symbols", "#ffffff"),
    "modifier": ("Modifiers", "#eee5fa"),
    "layer": ("Layer controls", "#fff0cc"),
    "dual-role": ("Tap / hold / dance", "#e3edff"),
    "navigation": ("Navigation / editing / pointer", "#def2e9"),
    "media": ("Media controls", "#fbe3eb"),
    "system": ("Function / system", "#e4eaf2"),
}
MODIFIERS = {"LCTRL", "RCTRL", "LSHFT", "RSHFT", "LALT", "RALT", "LGUI", "RGUI", "CAPS"}
NAVIGATION = {"UP", "DOWN", "LEFT", "RIGHT", "PG_UP", "PG_DN", "HOME", "END",
              "INS", "BSPC", "DEL", "RET", "ESC", "TAB"}


def key_category(code):
    if code in MODIFIERS:
        return "modifier"
    if code in NAVIGATION:
        return "navigation"
    if code.startswith("C_"):
        return "media"
    if re.fullmatch(r"F[0-9]+", code):
        return "system"
    return "normal"


def legend(binding):
    parts = binding.split()
    if binding == "&none":
        return ["—"], "blank"
    if binding == "&trans":
        return ["▽", "Transparent"], "transparent"
    if parts[:1] == ["&rd"]:
        return {"0": (["Shift / Sym"], "dual-role"),
                "1": (["Enter / Ctrl"], "dual-role"),
                "2": (["Ctrl / Alt"], "dual-role")}.get(parts[-1], ([binding], "dual-role"))
    if len(parts) == 2 and parts[0] == "&kp":
        label = key_label(parts[1])
        return (["Cursor", label] if parts[1] in {"UP", "DOWN", "LEFT", "RIGHT"}
                else [label]), key_category(parts[1])
    if len(parts) == 3 and parts[0] == "&lt":
        return [key_label(parts[2]), f"hold {parts[1]}"], "dual-role"
    if len(parts) == 2 and parts[0] in {"&tog", "&mo", "&base_select"}:
        action = {"&tog": "Toggle", "&mo": "Hold", "&base_select": "Base"}[parts[0]]
        return [action, parts[1]], "layer"
    if len(parts) == 2 and parts[0] == "&mmv":
        return ["Mouse", {"MOVE_UP": "↑", "MOVE_DOWN": "↓", "MOVE_LEFT": "←",
                          "MOVE_RIGHT": "→"}.get(parts[1], parts[1])], "navigation"
    if len(parts) == 2 and parts[0] == "&mkp":
        return [{"LCLK": "Left click", "RCLK": "Right click"}.get(parts[1], parts[1])], "navigation"
    return [{"&bootloader": "Bootloader", "&sys_reset": "Reset"}.get(binding, binding)], "system"


SVG_STYLE = """
.key rect {fill:#fff;stroke:#748091;stroke-width:1.5}
.key text {fill:#172333;font-family:system-ui,sans-serif;text-anchor:middle}
.key .position {fill:#526172;font-size:13px;text-anchor:start}
.blank rect {fill:#f1f3f5}.blank .legend {fill:#657180}
.transparent rect {fill:#fafbfc;stroke-dasharray:5 4}
.transparent .legend {fill:#526172}
""" + "\n".join(f".{category} rect {{fill:{color}}}"
                  for category, (_, color) in CATEGORIES.items())


def render_svg(name, label, bindings, geometry):
    corners = [corner for key in geometry for corner in key.corners()]
    left, top = min(p[0] for p in corners) - 15, min(p[1] for p in corners) - 15
    width = max(p[0] for p in corners) + 15 - left
    height = max(p[1] for p in corners) + 15 - top
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{left:g} {top:g} {width:g} {height:g}" role="img" aria-label="{escape(label, quote=True)} keymap">',
           f'<title>{escape(name)} — {escape(label)}</title>', f'<style>{SVG_STYLE}</style>']
    for pos, (key, binding) in enumerate(zip(geometry, bindings)):
        lines, kind = legend(binding)
        classes = f"key {kind}"
        svg.append(f'<g class="{classes}" data-position="{pos}" transform="rotate({key.rotation / 100:g} {key.origin_x} {key.origin_y})">')
        svg.append(f'<title>Position {pos}: {escape(binding)}</title>')
        svg.append(f'<rect x="{key.x + 4}" y="{key.y + 4}" width="{key.width - 8}" height="{key.height - 8}" rx="7"/>')
        svg.append(f'<text class="position" x="{key.x + 11}" y="{key.y + 23}">{pos}</text>')
        for line_index, line in enumerate(lines):
            size = min(23, 156 / max(len(line), 1))
            y = key.y + 59 + (line_index - (len(lines) - 1) / 2) * 23
            svg.append(f'<text class="legend" x="{key.x + key.width / 2:g}" y="{y:g}" font-size="{size:g}">{escape(line)}</text>')
        svg.append('</g>')
    svg.append('</svg>')
    return "\n".join(svg)


def render_index(rendered):
    swatches = " ".join(
        f'<span class="category"><span class="swatch" style="background:{color}"></span>{escape(label)}</span>'
        for label, color in CATEGORIES.values())
    links = " · ".join(f'<a href="#{name.lower()}">{escape(label)}</a>' for name, label, _ in rendered)
    sections = "\n".join(f'<section id="{name.lower()}"><h2>{escape(label)} <small>({escape(name)})</small></h2>'
                         f'<p><a href="{name.lower()}.svg">Standalone SVG</a></p>{svg}</section>'
                         for name, label, svg in rendered)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Halcyon Elora keymap</title><style>
body {{font:16px/1.5 system-ui,sans-serif;color:#172333;background:white;margin:0 auto;padding:1.5rem;max-width:1500px}}
a {{color:#225b8b}} nav {{line-height:2}} section {{margin:2rem 0;border-top:1px solid #ccd2da}}
.category {{display:inline-flex;align-items:center;gap:.4rem;margin:.2rem 1rem .2rem 0}}
.swatch {{display:inline-block;width:1rem;height:1rem;border:1px solid #748091;border-radius:3px}}
svg {{display:block;width:100%;height:auto}} small {{font-weight:normal}} h2 {{margin-bottom:0}} section p {{margin-top:0}}
@media print {{body {{padding:0;max-width:none}} nav,section p {{display:none}} section {{break-inside:avoid;page-break-inside:avoid}}}}
</style></head><body><h1>Halcyon Elora keymap</h1>
<p>62 physical keys in their staggered layout. Small numbers are zero-based physical positions.
Module positions 62–71 are absent from this keyboard and are not drawn. Hover a key for its full binding.</p>
<p><strong>Legend:</strong> — = blank / no action; ▽ = transparent (falls through to the next active layer,
not a fixed underlying key). Blank keys are gray; transparent keys have dashed borders.
Colors consistently describe action types across every layer, not particular physical positions.</p>
<div aria-label="Key categories">{swatches}</div>
<p>Cursor arrows send keypresses; Mouse arrows move the pointer. Slash legends on rd behaviors summarize Shift/Sym, Enter/Ctrl,
and Ctrl/Alt; see the behavior definition for tap/hold/dance timing. Layer taps show tap action then hold layer.</p>
<nav aria-label="Layers">{links}</nav>{sections}
</body></html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT, help="Repository root (default: script's parent repository)")
    parser.add_argument("--layout", type=Path, help="Optional physical-layout DTSI override (62 keys)")
    parser.add_argument("--output", type=Path, help="Default: repo sibling ../notes/keymap")
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output or repo.parent / "notes/keymap"
    try:
        geometry = (read_geometry(args.layout) if args.layout else
                    [PhysicalKey(100, 100, x, y, 0, 0, 0) for x, y in KEY_POSITIONS])
        if len(geometry) != 62:
            raise ValueError("Expected 62 embedded physical keys")
        layers = load_layers(repo)
        rendered = [(name, label, render_svg(name, label, bindings, geometry))
                    for name, label, bindings in layers]
        for _, _, svg in rendered:
            ET.fromstring(svg)
        index = render_index(rendered)
        output.mkdir(parents=True, exist_ok=True)
        for name, _, svg in rendered:
            (output / f"{name.lower()}.svg").write_text(svg + "\n", encoding="utf-8")
        (output / "index.html").write_text(index, encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Rendered and XML-validated {len(rendered)} SVGs (62 keys each) and offline index: {output / 'index.html'}")


if __name__ == "__main__":
    main()
