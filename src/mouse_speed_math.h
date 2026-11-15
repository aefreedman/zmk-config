/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include <stdint.h>

enum { MS_DOWN, MS_UP, MS_RESET, MS_FAST_HOLD, MS_FAST_TOGGLE, MS_PREC_HOLD, MS_PREC_TOGGLE };
enum { MS_FAST_HELD = 1, MS_FAST_LATCHED = 2, MS_PREC_HELD = 4, MS_PREC_LATCHED = 8 };
enum { MS_DEFAULT = 2000, MS_MIN = 100, MS_MAX = 10000, MS_STEP = 100 };

static inline int32_t ms_adjust(int32_t current, unsigned action) {
    if (action == MS_RESET) return MS_DEFAULT;
    int64_t next = (int64_t)current + (action == MS_UP ? MS_STEP : -MS_STEP);
    return next < MS_MIN ? MS_MIN : next > MS_MAX ? MS_MAX : (int32_t)next;
}

static inline uint32_t ms_mode_press(uint32_t flags, unsigned action) {
    switch (action) {
    case MS_FAST_HOLD: return flags | MS_FAST_HELD;
    case MS_FAST_TOGGLE: return flags ^ MS_FAST_LATCHED;
    case MS_PREC_HOLD: return flags | MS_PREC_HELD;
    case MS_PREC_TOGGLE: return flags ^ MS_PREC_LATCHED;
    default: return flags;
    }
}

static inline uint32_t ms_mode_release(uint32_t flags, unsigned action) {
    if (action == MS_FAST_HOLD) return flags & ~((uint32_t)MS_FAST_HELD);
    if (action == MS_PREC_HOLD) return flags & ~((uint32_t)MS_PREC_HELD);
    return flags;
}

static inline int32_t ms_effective_speed(int32_t normal, uint32_t flags) {
    if (flags & (MS_PREC_HELD | MS_PREC_LATCHED)) return 500;
    if (flags & (MS_FAST_HELD | MS_FAST_LATCHED)) return 4000;
    return normal;
}

static inline int32_t ms_scale(int32_t value, int32_t speed, int16_t *remainder) {
    int64_t numerator = (int64_t)value * speed + (remainder ? *remainder : 0);
    int32_t result = (int32_t)(numerator / MS_DEFAULT);
    if (remainder) *remainder = (int16_t)(numerator % MS_DEFAULT);
    return result;
}
