/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include <stdbool.h>
#include <stdint.h>

/* Standalone decision engine: no Zephyr dependencies, shared by host tests. */
enum tg_kind { TG_SHIFT_SYM, TG_ENTER_CTRL, TG_CTRL_ALT, TG_COUNT };
enum { TG_CTRL = 1, TG_SHIFT = 2, TG_ALT = 4 };
struct tg_dance {
    bool active, pressed, decided, symbols;
    unsigned count;
    uint8_t held;
    int64_t first_press, deadline;
};
struct tg_engine {
    struct tg_dance dances[TG_COUNT];
    uint8_t pending, output;
    bool pending_symbols, output_symbols;
    int64_t mods_deadline, symbols_deadline;
    void (*mods)(uint8_t old, uint8_t current, int64_t now);
    void (*symbols)(bool active, int64_t now);
    void (*enter)(int64_t now);
};
void tg_init(struct tg_engine *e, void (*mods)(uint8_t, uint8_t, int64_t),
             void (*symbols)(bool, int64_t), void (*enter)(int64_t));
void tg_tick(struct tg_engine *e, int64_t now);
void tg_press(struct tg_engine *e, enum tg_kind kind, int64_t now);
void tg_release(struct tg_engine *e, enum tg_kind kind, int64_t now);
/* Call before lookup/dispatch of another position, after identifying its current binding. */
void tg_interrupt(struct tg_engine *e, int kind_at_position, bool modifier_or_layer, int64_t now);
/* Called AFTER the consuming nonmodifier HID press has been dispatched. */
void tg_consume(struct tg_engine *e, int64_t now);
/* 0 means no pending timers. */
int64_t tg_next_deadline(const struct tg_engine *e);
