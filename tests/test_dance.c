/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <assert.h>
#include <stdio.h>
#include "reviung_dance.h"

static struct rd_engine e;
static uint8_t mods;
static bool symbols;
static unsigned enters;
static void output_mods(uint8_t old, uint8_t current, int64_t now) {
    (void)now;
    assert(old == mods);
    mods = current;
}
static void output_symbols(bool active, int64_t now) { (void)now; symbols = active; }
static void output_enter(int64_t now) { (void)now; enters++; }
static void reset(void) {
    mods = enters = 0;
    symbols = false;
    rd_init(&e, output_mods, output_symbols, output_enter);
}
static int64_t taps(enum rd_kind kind, unsigned count, int64_t start, bool hold_last) {
    for (unsigned i = 0; i < count; i++) {
        rd_press(&e, kind, start);
        if (i == count - 1 && hold_last) return start;
        rd_release(&e, kind, start + 20);
        start += 40;
    }
    return start - 40;
}
static void test_gestures(void) {
    for (unsigned kind = 0; kind < RD_COUNT; kind++) {
        for (unsigned count = 1; count <= 5; count++) {
            for (unsigned hold = 0; hold < 2; hold++) {
                reset();
                int64_t last = taps(kind, count, 10, hold);
                rd_tick(&e, last + 200);
                uint8_t expected = 0;
                if (kind == RD_SHIFT_SYM && count == 1) expected = RD_SHIFT;
                if (kind == RD_ENTER_CTRL && count == 1 && hold) expected = RD_CTRL;
                if (kind == RD_CTRL_ALT && count <= 3) {
                    expected = count == 1 ? RD_CTRL : (hold && count == 2) ? RD_ALT : RD_CTRL | RD_ALT;
                }
                assert(mods == expected);
                assert(symbols == (kind == RD_SHIFT_SYM && count == 2));
                assert(enters == (kind == RD_ENTER_CTRL && count == 1 && !hold));
                if (hold) {
                    rd_release(&e, kind, last + 210);
                    assert(mods == 0 && !symbols);
                } else {
                    rd_consume(&e, last + 210);
                    assert(mods == 0 && !symbols);
                }
            }
        }
    }
}
static void test_rollover(void) {
    const int delays[] = {20, 129, 130, 199, 201};
    for (unsigned i = 0; i < sizeof(delays)/sizeof(delays[0]); i++) {
        for (unsigned special = 0; special < 2; special++) {
            reset();
            rd_press(&e, RD_SHIFT_SYM, 10);
            rd_interrupt(&e, -1, special, 10 + delays[i]);
            assert(mods == RD_SHIFT);
            rd_consume(&e, 11 + delays[i]);
            bool hold = special || delays[i] >= 130;
            assert(mods == (hold ? RD_SHIFT : 0));
            rd_tick(&e, 5000);
            assert(mods == (hold ? RD_SHIFT : 0));
            rd_release(&e, RD_SHIFT_SYM, 5010);
            assert(mods == 0);
        }
    }
}
static void test_stacking_and_release(void) {
    for (unsigned count = 1; count <= 3; count++) {
        for (unsigned reverse = 0; reverse < 2; reverse++) {
            reset();
            enum rd_kind first = reverse ? RD_CTRL_ALT : RD_SHIFT_SYM;
            enum rd_kind second = reverse ? RD_SHIFT_SYM : RD_CTRL_ALT;
            int64_t last = taps(first, reverse ? count : 1, 10, false);
            rd_interrupt(&e, second, true, last + 30);
            int64_t last2 = taps(second, reverse ? 1 : count, last + 40, false);
            rd_tick(&e, last2 + 200);
            assert(mods == (RD_SHIFT | RD_CTRL | (count > 1 ? RD_ALT : 0)));
            rd_consume(&e, last2 + 210);
            assert(mods == 0);
        }
        reset();
        /* Pending Shift survives release of a held Ctrl/Alt dance. */
        taps(RD_SHIFT_SYM, 1, 10, false);
        rd_interrupt(&e, RD_CTRL_ALT, true, 40);
        int64_t last = taps(RD_CTRL_ALT, count, 50, true);
        rd_interrupt(&e, -1, true, last + 20);
        uint8_t held = count == 1 ? RD_CTRL : count == 2 ? RD_ALT : RD_CTRL | RD_ALT;
        assert(mods == (RD_SHIFT | held));
        rd_release(&e, RD_CTRL_ALT, last + 30);
        assert(mods == RD_SHIFT && e.pending == RD_SHIFT);
    }
    reset();
    /* Pending Ctrl survives Enter/Ctrl hold release (unlike Ctrl/Alt reset). */
    taps(RD_CTRL_ALT, 1, 10, false);
    rd_interrupt(&e, RD_ENTER_CTRL, true, 40);
    rd_press(&e, RD_ENTER_CTRL, 50);
    rd_interrupt(&e, -1, true, 70);
    rd_release(&e, RD_ENTER_CTRL, 80);
    assert(e.pending == RD_CTRL && mods == RD_CTRL);
}
static void test_chord_timeout_and_oneshot(void) {
    reset();
    rd_press(&e, RD_SHIFT_SYM, 10);
    rd_interrupt(&e, RD_CTRL_ALT, true, 30);
    rd_press(&e, RD_CTRL_ALT, 30);
    rd_interrupt(&e, -1, true, 50); /* NUM layer-tap interrupt. */
    assert(mods == (RD_SHIFT | RD_CTRL));
    for (int i = 0; i < 3; i++) {
        rd_tick(&e, 4000 + i * 4000);
        rd_consume(&e, 4001 + i * 4000); /* Multiple arrow presses. */
        assert(mods == (RD_SHIFT | RD_CTRL));
    }
    rd_release(&e, RD_CTRL_ALT, 13000);
    assert(mods == RD_SHIFT);
    rd_release(&e, RD_SHIFT_SYM, 13010);
    assert(mods == 0);

    reset();
    taps(RD_SHIFT_SYM, 1, 10, false);
    rd_tick(&e, 210);
    assert(mods == RD_SHIFT && rd_next_deadline(&e) == 3210);
    rd_tick(&e, 3209);
    assert(mods == RD_SHIFT);
    rd_tick(&e, 3210);
    assert(mods == 0 && rd_next_deadline(&e) == 0);

    reset();
    int64_t last = taps(RD_SHIFT_SYM, 2, 10, false);
    rd_tick(&e, last + 200);
    assert(symbols);
    rd_tick(&e, last + 3200);
    assert(!symbols);
}
static void test_same_mod_cancellation(void) {
    reset();
    taps(RD_CTRL_ALT, 2, 10, false);
    rd_tick(&e, 250);
    assert(mods == (RD_CTRL | RD_ALT));
    rd_press(&e, RD_CTRL_ALT, 300);
    rd_interrupt(&e, -1, true, 320);
    rd_release(&e, RD_CTRL_ALT, 330);
    assert(mods == RD_ALT && e.pending == RD_ALT);
    rd_consume(&e, 340);
    assert(mods == 0);
}
int main(void) {
    test_gestures();
    test_rollover();
    test_stacking_and_release();
    test_chord_timeout_and_oneshot();
    test_same_mod_cancellation();
    puts("Reviung dance engine: gesture, boundary, chord, overflow, timeout and ownership tests passed");
}
