/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include <stdbool.h>
#include <stdint.h>

/* Standalone decision engine: no Zephyr dependencies, shared by host tests. */
enum rd_kind { RD_SHIFT_SYM, RD_ENTER_CTRL, RD_CTRL_ALT, RD_COUNT };
enum { RD_CTRL = 1, RD_SHIFT = 2, RD_ALT = 4 };
struct rd_dance {
    bool active, pressed, decided, symbols;
    unsigned count;
    uint8_t held;
    int64_t first_press, deadline;
};
struct rd_engine {
    struct rd_dance dances[RD_COUNT];
    uint8_t pending, output;
    bool pending_symbols, output_symbols;
    int64_t mods_deadline, symbols_deadline;
    void (*mods)(uint8_t old, uint8_t current, int64_t now);
    void (*symbols)(bool active, int64_t now);
    void (*enter)(int64_t now);
};
void rd_init(struct rd_engine *e, void (*mods)(uint8_t, uint8_t, int64_t),
             void (*symbols)(bool, int64_t), void (*enter)(int64_t));
void rd_tick(struct rd_engine *e, int64_t now);
void rd_press(struct rd_engine *e, enum rd_kind kind, int64_t now);
void rd_release(struct rd_engine *e, enum rd_kind kind, int64_t now);
/* Call before lookup/dispatch of another position, after identifying its current binding. */
void rd_interrupt(struct rd_engine *e, int kind_at_position, bool modifier_or_layer, int64_t now);
/* Called AFTER the consuming nonmodifier HID press has been dispatched. */
void rd_consume(struct rd_engine *e, int64_t now);
/* 0 means no pending timers. */
int64_t rd_next_deadline(const struct rd_engine *e);
