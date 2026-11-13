# Elora layout and firmware status

## Physical mapping

The three Reviung typing rows transfer unchanged to Elora's three typing rows
(excluding the new top row). All twelve top-row keys are `&none` on all layers.
The four additional inner keys on the bottom typing row are also unassigned.

Thumbs, in the order used by the shield keymap (left-to-right within each half):

| Half | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| Left (outer → inner) | blank | blank | GUI | Shift/Symbol | blank |
| Right (inner → outer) | Space | NUM/Backspace | FUNC/Delete | blank | blank |

This is the initial placement; physical comfort must be checked on hardware.
Layer-specific thumb bindings are preserved from Reviung: e.g. NUM replaces GUI
with 0, Shift/Symbol with Shift, and the right-hand Space position with keypad
period. Space itself is never assigned to a left thumb, including game layers.

Encoder rotation is provisionally volume up/down on every layer. Encoder press
and all other module button positions are unassigned. The left display uses the
forest image. Neither choice is a final user preference.

## Layers

Order: Colemak (startup), QWERTY, FPS, symbols, numbers/navigation,
function/media, adjust, DJMAX.

Base layouts are below overlays so a selected FPS layout cannot mask NUM/FUNC.
A small custom base-selection behavior changes only the nondefault base layers,
leaving held/toggled overlays intact instead of using ZMK `&to` (which would
clear them). Selection is not persistent across reboots, matching the QMK `DF`
usage. Colemak is always ZMK layer 0; all selectable bases are fully mapped where
the original has keys. QMK RGB keys on ADJUST are deliberately disabled.

Hold FUNC/Delete, then hold the right-hand quote position (ADJUST) to access the
original layout selection keys. FPS exits via its original bottom-left Colemak
key; DJMAX toggles off via its original top-right key. This means the first
*typing* row, not the permanently blank physical top row.

## Custom gesture behavior

`src/reviung_dance.c` is a portable, host-tested decision engine.
`src/behavior_reviung.c` integrates it with ZMK position/keycode events and timers.
It avoids nested stock hold-taps for dances, since those add a second decision
stage and cannot directly inspect the interrupting key's behavior.

- Shift/Symbol: tap → queued Shift; hold → held Shift; double tap → queued
  symbols; double hold → held symbols. Other counts do nothing.
- Enter/Ctrl: single tap → Enter, single hold → Ctrl; other counts do nothing.
- Ctrl/Alt: single tap → queued Ctrl; double/triple tap → queued Ctrl+Alt;
  single/double/triple hold → Ctrl / Alt / Ctrl+Alt. Other counts do nothing.
- 200 ms dance decision timeout, measured from the most recent press.
- Shift interrupted by an ordinary key before 130 ms becomes one-shot Shift;
  modifier/layer interrupts preserve a real hold. The adapter resolves the
  actual active binding rather than relying only on physical positions.
- Pending modifiers stack with a 3000 ms timeout. Held modifiers do not expire.
- A nonmodifier HID press consumes queued modifiers after its down report;
  held modifiers remain active. Releasing a held Shift/Ctrl/Alt dance removes
  only its own queued modifier bits. Enter/Ctrl retains the QMK exception.
- Queued symbols expire after 3000 ms and are consumed by a nonmodifier HID
  press. Held symbols remain until physical release.

## Explicit differences and unverified areas

This is a first implementation, NOT a claim of fully verified QMK equivalence.

- The symbol one-shot is consumed by an emitted nonmodifier HID press. A disabled
  key, layer switch, or modifier does not consume it. Full QMK one-shot-layer
  special-key handling is not reproduced; it needs hardware evaluation.
- One-shot modifiers release immediately after the consuming down report rather
  than following the host key-up. This aims to avoid modifying a typing rollover;
  mouse interactions and application-specific shortcut handling need testing.
- Enter uses immediate down/up events once decided. No hardware report timing
  test has been performed yet.
- Layer-taps use ZMK tap-preferred with 200 ms tapping and quick-tap intervals.
  ZMK measures quick-tap press-to-press, unlike QMK's release-to-next-press.
- Timer expiry resolves at 200 ms; QMK's core checks strictly later than its
  tapping term. Exact simultaneous boundary scheduling cannot be identical.
- Modifier reference ownership is preserved within this custom engine and ZMK
  tracks emitted modifiers; interaction with other sources of the same modifier
  still requires firmware/event-pipeline and hardware checks.
- Runtime keymap editing/Studio and layer reordering are not enabled. Adding new
  behavior types requires updating the adapter's modifier/layer classification.
- Bootloader/reset key bindings target the central device (dongle). Use the
  physical reset button to enter a half's bootloader; do not assume a key resets
  all three devices.
- Displays, encoder direction, actual scan positions, radio routing, power use,
  and Bluetooth pairing cannot be validated by host decision-engine tests.

## Development

All development checkouts are under `~/dev/`. This repo is `~/dev/zmk-config`.
The original GPL keymap is frozen in `reference/reviung41/` for reproducibility;
see `docs/reviung-port-audit.md` for its source commit. Generated bindings retain
GPL attribution. The west manifest pins the reviewed firmware and module commits.

```sh
cd ~/dev/zmk-config
python3 scripts/generate_keymap.py       # regenerate after an intentional edit
python3 scripts/generate_keymap.py --check
python3 tests/run.py                    # Python layout checks + actual C engine
```

Host C tests run with AddressSanitizer/UndefinedBehaviorSanitizer. They cover all
tap/hold counts including overflow, grace boundaries, layered modifier chords,
stacking order, one-shot expiry, cancellation ownership, and held modifiers
beyond the timeout. These do NOT execute the Zephyr adapter or Bluetooth stack.

GitHub Actions runs the host checks before building dongle/left/right firmware.
Do not flash firmware until all builds pass and the remaining validation is
understood. Hardware testing remains pending even after a successful build.
