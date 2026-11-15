/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <zephyr/device.h>
#include <zephyr/input/input.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/dt-bindings/input/input-event-codes.h>
#include <drivers/behavior.h>
#include <drivers/input_processor.h>
#include <zmk/behavior.h>
#include "mouse_speed_math.h"

#if DT_HAS_COMPAT_STATUS_OKAY(aefreedman_mouse_speed) && \
    DT_HAS_COMPAT_STATUS_OKAY(aefreedman_mouse_speed_scaler)
LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

/* RAM-only: adjustments never wear flash or change the fixed Fast/Precision rates. */
static atomic_t normal_speed = ATOMIC_INIT(MS_DEFAULT);

static int adjust_pressed(struct zmk_behavior_binding *binding,
                          struct zmk_behavior_binding_event event) {
    (void)event;
    if (binding->param1 > MS_RESET) return -EINVAL;
    atomic_val_t previous, next;
    do {
        previous = atomic_get(&normal_speed);
        next = ms_adjust((int32_t)previous, binding->param1);
    } while (!atomic_cas(&normal_speed, previous, next));
    LOG_DBG("Normal mouse speed: %d", (int)next);
    return ZMK_BEHAVIOR_OPAQUE;
}

static int adjust_released(struct zmk_behavior_binding *binding,
                           struct zmk_behavior_binding_event event) {
    (void)binding;
    (void)event;
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api adjust_api = {
    .binding_pressed = adjust_pressed,
    .binding_released = adjust_released,
#if IS_ENABLED(CONFIG_ZMK_BEHAVIOR_METADATA)
    .get_parameter_metadata = zmk_behavior_get_empty_param_metadata,
#endif
};
BEHAVIOR_DT_DEFINE(DT_INST(0, aefreedman_mouse_speed), NULL, NULL, NULL, NULL,
                   POST_KERNEL, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &adjust_api);

static int normal_scale(const struct device *dev, struct input_event *event,
                        uint32_t param1, uint32_t param2,
                        struct zmk_input_processor_state *state) {
    (void)dev;
    (void)param1;
    (void)param2;
    if (event->type != INPUT_EV_REL ||
        (event->code != INPUT_REL_X && event->code != INPUT_REL_Y)) {
        return ZMK_INPUT_PROC_CONTINUE;
    }
    int32_t speed = atomic_get(&normal_speed);
    event->value = ms_scale(event->value, speed, state ? state->remainder : NULL);
    LOG_DBG("Normal pointer scale: %d at %d", (int)event->value, (int)speed);
    return ZMK_INPUT_PROC_CONTINUE;
}

static const struct zmk_input_processor_driver_api scale_api = {
    .handle_event = normal_scale,
};
DEVICE_DT_DEFINE(DT_INST(0, aefreedman_mouse_speed_scaler), NULL, NULL, NULL, NULL,
                 POST_KERNEL, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &scale_api);
#endif
