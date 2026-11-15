/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "thumb_gestures.h"
#include <string.h>

#define TERM 200
#define GRACE 130
#define ONESHOT 3000

static void sync_outputs(struct tg_engine *e, int64_t now) {
    uint8_t mods = e->pending;
    bool symbols = e->pending_symbols;
    for (unsigned i = 0; i < TG_COUNT; i++) {
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

static void queue_mods(struct tg_engine *e, uint8_t mods, int64_t now) {
    /* QMK refreshes the global one-shot timeout only if the mask changes. */
    if ((e->pending | mods) != e->pending) {
        e->pending |= mods;
        e->mods_deadline = now + ONESHOT;
    }
}

static void finish(struct tg_engine *e, unsigned kind, bool interrupted,
                   bool modifier_or_layer, int64_t now) {
    struct tg_dance *d = &e->dances[kind];
    if (!d->active || d->decided) {
        return;
    }
    d->decided = true;
    bool hold = d->pressed;
    if (kind == TG_SHIFT_SYM && d->count == 1 && hold && interrupted &&
        !modifier_or_layer && now - d->first_press < GRACE) {
        hold = false;
    }
    switch (kind) {
    case TG_SHIFT_SYM:
        if (d->count == 1) {
            if (hold) d->held = TG_SHIFT;
            else queue_mods(e, TG_SHIFT, now);
        } else if (d->count == 2) {
            if (hold) d->symbols = true;
            else {
                e->pending_symbols = true;
                e->symbols_deadline = now + ONESHOT;
            }
        }
        break;
    case TG_ENTER_CTRL:
        if (d->count == 1) {
            if (hold) d->held = TG_CTRL;
            else e->enter(now);
        }
        break;
    case TG_CTRL_ALT:
        if (d->count >= 1 && d->count <= 3) {
            if (hold) d->held = d->count == 1 ? TG_CTRL :
                                d->count == 2 ? TG_ALT : TG_CTRL | TG_ALT;
            else queue_mods(e, d->count == 1 ? TG_CTRL : TG_CTRL | TG_ALT, now);
        }
        break;
    }
    if (!d->pressed) {
        memset(d, 0, sizeof(*d));
    }
    sync_outputs(e, now);
}

void tg_init(struct tg_engine *e, void (*mods)(uint8_t, uint8_t, int64_t),
             void (*symbols)(bool, int64_t), void (*enter)(int64_t)) {
    memset(e, 0, sizeof(*e));
    e->mods = mods;
    e->symbols = symbols;
    e->enter = enter;
}

void tg_tick(struct tg_engine *e, int64_t now) {
    if (e->pending && now >= e->mods_deadline) e->pending = 0;
    if (e->pending_symbols && now >= e->symbols_deadline) e->pending_symbols = false;
    sync_outputs(e, now);
    for (unsigned i = 0; i < TG_COUNT; i++) {
        if (e->dances[i].active && !e->dances[i].decided &&
            now >= e->dances[i].deadline) {
            finish(e, i, false, false, now);
        }
    }
}

void tg_press(struct tg_engine *e, enum tg_kind kind, int64_t now) {
    tg_tick(e, now);
    struct tg_dance *d = &e->dances[kind];
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

void tg_release(struct tg_engine *e, enum tg_kind kind, int64_t now) {
    tg_tick(e, now);
    struct tg_dance *d = &e->dances[kind];
    if (!d->active) return;
    d->pressed = false;
    if (d->decided) {
        /* Enter/Ctrl's original reset does not delete queued Ctrl one-shots. */
        if (kind != TG_ENTER_CTRL) e->pending &= (uint8_t)~d->held;
        memset(d, 0, sizeof(*d));
        sync_outputs(e, now);
    }
    /* QMK's dance timeout runs from the last press, not release. */
}

void tg_interrupt(struct tg_engine *e, int kind_at_position, bool modifier_or_layer, int64_t now) {
    tg_tick(e, now);
    for (unsigned i = 0; i < TG_COUNT; i++) {
        if ((int)i != kind_at_position) finish(e, i, true, modifier_or_layer, now);
    }
}

void tg_consume(struct tg_engine *e, int64_t now) {
    e->pending = 0;
    e->pending_symbols = false;
    sync_outputs(e, now);
}

int64_t tg_next_deadline(const struct tg_engine *e) {
    int64_t next = 0;
#define EARLIEST(t) do { if (!next || (t) < next) next = (t); } while (0)
    if (e->pending) EARLIEST(e->mods_deadline);
    if (e->pending_symbols) EARLIEST(e->symbols_deadline);
    for (unsigned i = 0; i < TG_COUNT; i++) {
        if (e->dances[i].active && !e->dances[i].decided) EARLIEST(e->dances[i].deadline);
    }
#undef EARLIEST
    return next;
}
