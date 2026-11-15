/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include "mouse_speed_math.h"

int main(void) {
    assert(ms_adjust(2000, MS_DOWN) == 1900);
    assert(ms_adjust(2000, MS_UP) == 2100);
    assert(ms_adjust(3900, MS_RESET) == 2000);
    assert(ms_adjust(MS_MIN, MS_DOWN) == MS_MIN);
    assert(ms_adjust(MS_MAX, MS_UP) == MS_MAX);
    assert(ms_adjust(INT32_MAX, MS_UP) == MS_MAX);
    assert(ms_adjust(INT32_MIN, MS_DOWN) == MS_MIN);
    assert(ms_scale(32, 2000, NULL) == 32);
    assert(ms_scale(32, 4000, NULL) == 64);
    assert(ms_scale(32, 500, NULL) == 8);
    assert(ms_scale(INT16_MAX, MS_MAX, NULL) == 163835);
    assert(ms_scale(INT16_MIN, MS_MAX, NULL) == -163840);
    for (int sign = -1; sign <= 1; sign += 2) {
        int16_t remainder = 0;
        int total = 0;
        for (int i = 0; i < 100; i++) {
            total += ms_scale(sign * 32, 2100, &remainder);
            assert(remainder > -MS_DEFAULT && remainder < MS_DEFAULT);
        }
        assert(total == sign * 3360 && remainder == 0);
        total = 0;
        for (int i = 0; i < 20; i++) total += ms_scale(sign, MS_MIN, &remainder);
        assert(total == sign && remainder == 0);
    }
    puts("Mouse speed math: steps/reset, bounds, wide products, signed fractional movement passed");
}
