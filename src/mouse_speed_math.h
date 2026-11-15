/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include <stdint.h>

enum { MS_DOWN, MS_UP, MS_RESET };
enum { MS_DEFAULT = 2000, MS_MIN = 100, MS_MAX = 10000, MS_STEP = 100 };

static inline int32_t ms_adjust(int32_t current, unsigned action) {
    if (action == MS_RESET) return MS_DEFAULT;
    int64_t next = (int64_t)current + (action == MS_UP ? MS_STEP : -MS_STEP);
    return next < MS_MIN ? MS_MIN : next > MS_MAX ? MS_MAX : (int32_t)next;
}

static inline int32_t ms_scale(int32_t value, int32_t speed, int16_t *remainder) {
    int64_t numerator = (int64_t)value * speed + (remainder ? *remainder : 0);
    int32_t result = (int32_t)(numerator / MS_DEFAULT);
    if (remainder) *remainder = (int16_t)(numerator % MS_DEFAULT);
    return result;
}
