# Reviung41 → Halcyon Elora: initial compatibility audit

## Status and scope

Historical source audit below; implementation status is tracked in
[layout.md](layout.md). The initial eight-layer port and custom gesture engine
are now implemented, with host tests and three firmware targets enabled for
build validation. No firmware has been flashed or hardware tested.
Public repository: https://github.com/aefreedman/zmk-config.

Requirements:
- Base the layout on aefreedman's Reviung41 keymap, not splitkb's default map.
- Keep the entire physical top row unassigned on every layer (`&none`, not numbers).
- Retain numbers on the existing NUM layer.
- Keep development files under `~/dev/`.
- Hardware confirmed: LiPo batteries on both halves; dongle as central;
  e-ink display on the left; Halcyon encoder module on the right.
- RGB is not used; disable it and omit the old RGB controls.
- Space is on the right hand only; do not duplicate it on the left.
- Publish the config as the public repository `aefreedman/zmk-config`.

## Local repositories and reviewed revisions

| Path under ~/dev/ | Source | Reviewed commit |
| --- | --- | --- |
| qmk_firmware | aefreedman/qmk_firmware, master | 769b195e1f9038fe8c8d2df1a589e283f63554f3 |
| zmk-config | splitkb/zmk-halcyon-config | 092029ea5e9801edec254aa6492e2e76de0f16bb |
| zmk | splitkb/zmk, main+halcyon-fixes | 80cf18d57c52a8ed4badc7f330cec7eada6521d8 |
| zmk-halcyon-module | splitkb/zmk-halcyon-module, main | 0b95571b332862a6fda8d62a0f0a4c6ccd7895dc |

QMK and ZMK checkouts are shallow/sparse source references, not installed build
workspaces. The config's west manifest retains splitkb's recommended firmware
fork and Halcyon module. The manifest is now pinned to the reviewed commits above.

QMK source: `keyboards/reviung/reviung41/keymaps/aefreedman/`
(`keymap.c`, `config.h`, `rules.mk`, and both test suites).

## Compatibility summary

No fundamental blocker found for the intended layout. However, exact parity
with the custom C callbacks is NOT provided by a simple keycode translation.
The table records the initial assessment of stock behaviors. The implementation
now uses a custom gesture engine instead of nested behavior composition; see
layout.md for the implemented semantics and remaining differences.

| Existing feature | ZMK assessment |
| --- | --- |
| Eight layers: Colemak, QWERTY, symbols, numbers/navigation, function/media, adjust, FPS, DJMAX | Supported; numeric layer order must be redesigned, not blindly copied. |
| Ordinary keys, F1–F18, arrows/navigation, keypad arithmetic/decimal, media/volume | Native keypress equivalents. Preserve keypad usages rather than silently converting them to ordinary punctuation. Host interpretation remains host-dependent. |
| NUM/Backspace and FUNC/Delete layer-taps | Native hold-tap/layer-tap. Set tapping term to 200 ms. QMK default interruption behavior is closest to ZMK tap-preferred; repeat/quick-tap timing needs explicit review. |
| Enter tap / Ctrl hold | Native hold-tap can reproduce the main function, but the QMK implementation is a tap dance, not ordinary mod-tap. Its immediate resolution on another keypress and suppression of multi-taps require deliberate handling/tests. |
| Shift tap = one-shot Shift; hold = Shift; double tap = one-shot symbols; double hold = symbols | ZMK has tap dance, sticky modifiers/layers, and hold-tap building blocks. No direct import of QMK callbacks. Nested tap-dance/hold-tap is a candidate for the basic gestures, with timing/interrupt parity unproven. |
| Ctrl/Alt tap = one-shot Ctrl; double/triple tap = one-shot Ctrl+Alt; single/double/triple hold = Ctrl / Alt / Ctrl+Alt | Same composition issue. Combined modifier keycodes and sticky keys are available, but count, interruption, and release semantics need testing. |
| Shift 130 ms typing-rollover grace, excluding modifier/layer interrupts | No direct equivalent to this custom keycode-aware callback in stock declarative behaviors. Positional hold-tap can approximate a fixed mapping but does not dynamically classify the interrupting behavior across layers. Exact parity may require a custom ZMK behavior/module. |
| Stacking pending one-shot Shift/Ctrl/Alt | Sticky keys support stacking; configure a 3000 ms timeout and examine lazy/quick-release options. Defaults are not QMK-equivalent. |
| Releasing a held modifier clears only that modifier's pending one-shot bits | Custom QMK logic; stock sticky keys and held modifiers have separate state. Exact cancellation behavior is not established and may need custom code. Test that unrelated queued modifiers survive. |
| QMK DF(Colemak/QWERTY/FPS) | No direct runtime-default-layer equivalent among the reviewed stock layer behaviors. `&to` selects a layer but leaves layer 0 active and clears other nondefault layers. Use complete base layouts below overlays, with explicit selection/cleanup; do not describe this as identical to DF. |
| DJMAX toggle | Native `&tog`; test selection while DJMAX is active because `&to` clears other layers unlike DF. |
| RGB toggle, brightness/saturation/hue, next/previous effect | `&rgb_ug` equivalents exist and the wireless shield enables RGB. Effects/steps differ from QMK; battery module/power policy matters. |
| Reboot and bootloader | Native `&sys_reset` / `&bootloader`; split-device targeting must be verified, not assumed to reset both halves. |
| Transparent vs disabled keys | Use `&trans` vs `&none` deliberately. Top row must stay `&none` on all layers. |

The source does NOT use leader sequences, dynamic macro recording, combos,
Caps Word, tap-toggle, or EEPROM-persistent default selection. Those are not
migration blockers for this particular keymap. The future macro row is reserved,
not an existing macro implementation to port.

### Important details from the current source

- Colemak is layer 0, so it is the startup base despite QWERTY appearing first in
  the keymap.c initializer.
- QMK constants: TAPPING_TERM=200, ONESHOT_TIMEOUT=3000,
  SHIFT_HOLD_GRACE_MS=130.
- Multi-tap overflow is not necessarily equivalent: custom QMK callbacks return
  no action for unsupported counts; stock ZMK tap dance selects its last binding
  as soon as the maximum configured count is reached.
- QMK tap-dance callbacks resolve on interruption and inspect whether the key is
  still physically held. Stock ZMK tap dance selects by count and delegates the
  action. A nested hold-tap introduces another decision stage; do not assume the
  original press timestamp or held-state rules are preserved automatically.
- QMK layer lookup and ZMK's always-active layer 0 differ. Put selectable base/game
  layouts below NUM/SYM/FUNC/ADJUST overlays and explicitly manage switching.

## Validation performed

Ran the existing host-side tests with the checked-out QMK core:

```sh
TMPDIR=~/dev/ python3 ~/dev/qmk_firmware/keyboards/reviung/reviung41/keymaps/aefreedman/tests/run.py
```

Both passed:
- Tap-dance callback regression tests
- Tap-dance event regression tests

These establish the source baseline only. They are not tests of ZMK and do not
constitute a full QMK firmware build or hardware verification.

Port validation must cover: each tap/hold count, interrupted holds, rollover
before/at/after 130 ms, modifier/layer interruptions, Shift+Ctrl+NUM arrow
selection beyond the one-shot timeout, stacked one-shots in both orders,
release ownership/cancellation, one-shot symbols, overflow taps, held Backspace
repeat, base/game switching, DJMAX exit, and top-row inactivity on every layer.

## Decisions required before a buildable config

Confirmed build topology:
- Dongle: `halcyon_dongle//zmk`, shield `halcyon_elora_dongle`.
- Left: `halcyon_wireless//zmk`, shields `halcyon_elora_left mod_battery_lipo`
  plus `mod_display_epaper_forest` (provisional image); set
  `-DCONFIG_ZMK_SPLIT_ROLE_CENTRAL=n`.
- Right: `halcyon_wireless//zmk`, shields
  `halcyon_elora_right mod_battery_lipo mod_encoder_right`.
- Disable RGB. No Cirque module requested.

Initial implementation choices (pending hardware evaluation):
1. Space right-only; GUI and Shift/Symbol on the left; NUM/Backspace and
   FUNC/Delete on the right. See layout.md for exact thumb indices.
2. Custom code implements the multi-tap/hold gestures and rollover rule;
   differences and validation limitations are explicit in layout.md.
3. Forest is the provisional e-ink image; mountain/cityscape can replace it later.
4. Encoder rotation provisionally controls volume; encoder press remains blank.

Hardware identifiers are `halcyon_wireless//zmk` and
`halcyon_elora_left` / `halcyon_elora_right`, optionally
`halcyon_dongle//zmk` with `halcyon_elora_dongle`.
The inspected Kconfig makes the left half central by default. The template's
left-peripheral CMake flag is for a dongle topology, not direct Bluetooth.

## References

- https://github.com/splitkb/zmk-halcyon-config
- https://docs.splitkb.com/product-guides/halcyon-series/resources/compiling-firmware-zmk
- https://zmk.dev/docs/keymaps/behaviors/tap-dance
- https://zmk.dev/docs/keymaps/behaviors/hold-tap
- https://zmk.dev/docs/keymaps/behaviors/sticky-key
- https://zmk.dev/docs/keymaps/behaviors/sticky-layer
- https://zmk.dev/docs/keymaps/behaviors/layers

Source review also used the actual splitkb firmware fork's
`app/src/behaviors/behavior_tap_dance.c`, `behavior_sticky_key.c`, and Halcyon
Elora shield files rather than relying only on upstream documentation.
