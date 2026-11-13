/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "reviung_dance.h"
#include <string.h>

#define TERM 200
#define GRACE 130
#define ONESHOT 3000

static void sync_outputs(struct rd_engine *e, int64_t now) {
    uint8_t mods = e->pending;
    bool symbols = e->pending_symbols;
    for (unsigned i = 0; i < RD_COUNT; i++) {
        mods |= e->dances[i].held;
        symbols |= e->dances[i].symbols;
    }
    if (mods != e->output) {
        uint8_t old = e->output;
        e->output = mods;
        e->mods(old, mods, now);
    }
    if (symbols != e->output_symbols) {
        e->output_symbols = symbols;
        e->symbols(symbols, now);
    }
}

static void queue_mods(struct rd_engine *e, uint8_t mods, int64_t now) {
    /* QMK refreshes the global one-shot timeout only if the mask changes. */
    if ((e->pending | mods) != e->pending) {
        e->pending |= mods;
        e->mods_deadline = now + ONESHOT;
    }
}

static void finish(struct rd_engine *e, unsigned kind, bool interrupted,
                   bool modifier_or_layer, int64_t now) {
    struct rd_dance *d = &e->dances[kind];
    if (!d->active || d->decided) {
        return;
    }
    d->decided = true;
    bool hold = d->pressed;
    if (kind == RD_SHIFT_SYM && d->count == 1 && hold && interrupted &&
        !modifier_or_layer && now - d->first_press < GRACE) {
        hold = false;
    }
    switch (kind) {
    case RD_SHIFT_SYM:
        if (d->count == 1) {
            if (hold) d->held = RD_SHIFT;
            else queue_mods(e, RD_SHIFT, now);
        } else if (d->count == 2) {
            if (hold) d->symbols = true;
            else {
                e->pending_symbols = true;
                e->symbols_deadline = now + ONESHOT;
            }
        }
        break;
    case RD_ENTER_CTRL:
        if (d->count == 1) {
            if (hold) d->held = RD_CTRL;
            else e->enter(now);
        }
        break;
    case RD_CTRL_ALT:
        if (d->count >= 1 && d->count <= 3) {
            if (hold) d->held = d->count == 1 ? RD_CTRL :
                                d->count == 2 ? RD_ALT : RD_CTRL | RD_ALT;
            else queue_mods(e, d->count == 1 ? RD_CTRL : RD_CTRL | RD_ALT, now);
        }
        break;
    }
    if (!d->pressed) {
        memset(d, 0, sizeof(*d));
    }
    sync_outputs(e, now);
}

void rd_init(struct rd_engine *e, void (*mods)(uint8_t, uint8_t, int64_t),
             void (*symbols)(bool, int64_t), void (*enter)(int64_t)) {
    memset(e, 0, sizeof(*e));
    e->mods = mods;
    e->symbols = symbols;
    e->enter = enter;
}

void rd_tick(struct rd_engine *e, int64_t now) {
    if (e->pending && now >= e->mods_deadline) e->pending = 0;
    if (e->pending_symbols && now >= e->symbols_deadline) e->pending_symbols = false;
    sync_outputs(e, now);
    for (unsigned i = 0; i < RD_COUNT; i++) {
        if (e->dances[i].active && !e->dances[i].decided &&
            now >= e->dances[i].deadline) {
            finish(e, i, false, false, now);
        }
    }
}

void rd_press(struct rd_engine *e, enum rd_kind kind, int64_t now) {
    rd_tick(e, now);
    struct rd_dance *d = &e->dances[kind];
    if (!d->active) {
        d->active = true;
        d->first_press = now;
    }
    if (d->pressed || d->decided) return;
    d->pressed = true;
    /* Saturate only beyond all recognized gestures; overflow must do nothing. */
    if (d->count < 4) d->count++;
    d->deadline = now + TERM;
}

void rd_release(struct rd_engine *e, enum rd_kind kind, int64_t now) {
    rd_tick(e, now);
    struct rd_dance *d = &e->dances[kind];
    if (!d->active) return;
    d->pressed = false;
    if (d->decided) {
        /* Enter/Ctrl's original reset does not delete queued Ctrl one-shots. */
        if (kind != RD_ENTER_CTRL) e->pending &= (uint8_t)~d->held;
        memset(d, 0, sizeof(*d));
        sync_outputs(e, now);
    }
    /* QMK's dance timeout runs from the last press, not release. */
}

void rd_interrupt(struct rd_engine *e, int kind_at_position, bool modifier_or_layer, int64_t now) {
    rd_tick(e, now);
    for (unsigned i = 0; i < RD_COUNT; i++) {
        if ((int)i != kind_at_position) finish(e, i, true, modifier_or_layer, now);
    }
}

void rd_consume(struct rd_engine *e, int64_t now) {
    e->pending = 0;
    e->pending_symbols = false;
    sync_outputs(e, now);
}

int64_t rd_next_deadline(const struct rd_engine *e) {
    int64_t next = 0;
#define EARLIEST(t) do { if (!next || (t) < next) next = (t); } while (0)
    if (e->pending) EARLIEST(e->mods_deadline);
    if (e->pending_symbols) EARLIEST(e->symbols_deadline);
    for (unsigned i = 0; i < RD_COUNT; i++) {
        if (e->dances[i].active && !e->dances[i].decided) EARLIEST(e->dances[i].deadline);
    }
#undef EARLIEST
    return next;
}
