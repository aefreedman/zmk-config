/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <assert.h>
#include <stdio.h>
#include "thumb_gestures.h"

static struct tg_engine e;
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
    tg_init(&e, output_mods, output_symbols, output_enter);
}
static int64_t taps(enum tg_kind kind, unsigned count, int64_t start, bool hold_last) {
    for (unsigned i = 0; i < count; i++) {
        tg_press(&e, kind, start);
        if (i == count - 1 && hold_last) return start;
        tg_release(&e, kind, start + 20);
        start += 40;
    }
    return start - 40;
}
static void test_gestures(void) {
    for (unsigned kind = 0; kind < TG_COUNT; kind++) {
        for (unsigned count = 1; count <= 5; count++) {
            for (unsigned hold = 0; hold < 2; hold++) {
                reset();
                int64_t last = taps(kind, count, 10, hold);
                tg_tick(&e, last + 200);
                uint8_t expected = 0;
                if (kind == TG_SHIFT_SYM && count == 1) expected = TG_SHIFT;
                if (kind == TG_ENTER_CTRL && count == 1 && hold) expected = TG_CTRL;
                if (kind == TG_CTRL_ALT && count <= 3) {
                    expected = count == 1 ? TG_CTRL : (hold && count == 2) ? TG_ALT : TG_CTRL | TG_ALT;
                }
                assert(mods == expected);
                assert(symbols == (kind == TG_SHIFT_SYM && count == 2));
                assert(enters == (kind == TG_ENTER_CTRL && count == 1 && !hold));
                if (hold) {
                    tg_release(&e, kind, last + 210);
                    assert(mods == 0 && !symbols);
                } else {
                    tg_consume(&e, last + 210);
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
            tg_press(&e, TG_SHIFT_SYM, 10);
            tg_interrupt(&e, -1, special, 10 + delays[i]);
            assert(mods == TG_SHIFT);
            tg_consume(&e, 11 + delays[i]);
            bool hold = special || delays[i] >= 130;
            assert(mods == (hold ? TG_SHIFT : 0));
            tg_tick(&e, 5000);
            assert(mods == (hold ? TG_SHIFT : 0));
            tg_release(&e, TG_SHIFT_SYM, 5010);
            assert(mods == 0);
        }
    }
}
static void test_stacking_and_release(void) {
    for (unsigned count = 1; count <= 3; count++) {
        for (unsigned reverse = 0; reverse < 2; reverse++) {
            reset();
            enum tg_kind first = reverse ? TG_CTRL_ALT : TG_SHIFT_SYM;
            enum tg_kind second = reverse ? TG_SHIFT_SYM : TG_CTRL_ALT;
            int64_t last = taps(first, reverse ? count : 1, 10, false);
            tg_interrupt(&e, second, true, last + 30);
            int64_t last2 = taps(second, reverse ? 1 : count, last + 40, false);
            tg_tick(&e, last2 + 200);
            assert(mods == (TG_SHIFT | TG_CTRL | (count > 1 ? TG_ALT : 0)));
            tg_consume(&e, last2 + 210);
            assert(mods == 0);
        }
        reset();
        /* Pending Shift survives release of a held Ctrl/Alt dance. */
        taps(TG_SHIFT_SYM, 1, 10, false);
        tg_interrupt(&e, TG_CTRL_ALT, true, 40);
        int64_t last = taps(TG_CTRL_ALT, count, 50, true);
        tg_interrupt(&e, -1, true, last + 20);
        uint8_t held = count == 1 ? TG_CTRL : count == 2 ? TG_ALT : TG_CTRL | TG_ALT;
        assert(mods == (TG_SHIFT | held));
        tg_release(&e, TG_CTRL_ALT, last + 30);
        assert(mods == TG_SHIFT && e.pending == TG_SHIFT);
    }
    reset();
    /* Pending Ctrl survives Enter/Ctrl hold release (unlike Ctrl/Alt reset). */
    taps(TG_CTRL_ALT, 1, 10, false);
    tg_interrupt(&e, TG_ENTER_CTRL, true, 40);
    tg_press(&e, TG_ENTER_CTRL, 50);
    tg_interrupt(&e, -1, true, 70);
    tg_release(&e, TG_ENTER_CTRL, 80);
    assert(e.pending == TG_CTRL && mods == TG_CTRL);
}
static void test_chotg_timeout_and_oneshot(void) {
    reset();
    tg_press(&e, TG_SHIFT_SYM, 10);
    tg_interrupt(&e, TG_CTRL_ALT, true, 30);
    tg_press(&e, TG_CTRL_ALT, 30);
    tg_interrupt(&e, -1, true, 50); /* NUM layer-tap interrupt. */
    assert(mods == (TG_SHIFT | TG_CTRL));
    for (int i = 0; i < 3; i++) {
        tg_tick(&e, 4000 + i * 4000);
        tg_consume(&e, 4001 + i * 4000); /* Multiple arrow presses. */
        assert(mods == (TG_SHIFT | TG_CTRL));
    }
    tg_release(&e, TG_CTRL_ALT, 13000);
    assert(mods == TG_SHIFT);
    tg_release(&e, TG_SHIFT_SYM, 13010);
    assert(mods == 0);

    reset();
    taps(TG_SHIFT_SYM, 1, 10, false);
    tg_tick(&e, 210);
    assert(mods == TG_SHIFT && tg_next_deadline(&e) == 3210);
    tg_tick(&e, 3209);
    assert(mods == TG_SHIFT);
    tg_tick(&e, 3210);
    assert(mods == 0 && tg_next_deadline(&e) == 0);

    reset();
    int64_t last = taps(TG_SHIFT_SYM, 2, 10, false);
    tg_tick(&e, last + 200);
    assert(symbols);
    tg_tick(&e, last + 3200);
    assert(!symbols);
}
static void test_same_mod_cancellation(void) {
    reset();
    taps(TG_CTRL_ALT, 2, 10, false);
    tg_tick(&e, 250);
    assert(mods == (TG_CTRL | TG_ALT));
    tg_press(&e, TG_CTRL_ALT, 300);
    tg_interrupt(&e, -1, true, 320);
    tg_release(&e, TG_CTRL_ALT, 330);
    assert(mods == TG_ALT && e.pending == TG_ALT);
    tg_consume(&e, 340);
    assert(mods == 0);
}
int main(void) {
    test_gestures();
    test_rollover();
    test_stacking_and_release();
    test_chotg_timeout_and_oneshot();
    test_same_mod_cancellation();
    puts("Thumb gesture engine: gesture, boundary, chord, overflow, timeout and ownership tests passed");
}
