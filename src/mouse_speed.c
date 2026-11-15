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

/* RAM-only state; no flash writes, extra keymap layers, or changed key bindings. */
static atomic_t normal_speed = ATOMIC_INIT(MS_DEFAULT);
static atomic_t mode_flags = ATOMIC_INIT(0);

static void update_mode(unsigned action, bool pressed) {
    atomic_val_t previous, next;
    do {
        previous = atomic_get(&mode_flags);
        next = pressed ? ms_mode_press(previous, action) : ms_mode_release(previous, action);
    } while (!atomic_cas(&mode_flags, previous, next));
    if (previous != next) LOG_DBG("Mouse mode state: %d", (int)next);
}

static int control_pressed(struct zmk_behavior_binding *binding,
                           struct zmk_behavior_binding_event event) {
    (void)event;
    if (binding->param1 > MS_PREC_TOGGLE) return -EINVAL;
    if (binding->param1 > MS_RESET) {
        update_mode(binding->param1, true);
        return ZMK_BEHAVIOR_OPAQUE;
    }
    atomic_val_t previous, next;
    do {
        previous = atomic_get(&normal_speed);
        next = ms_adjust((int32_t)previous, binding->param1);
    } while (!atomic_cas(&normal_speed, previous, next));
    LOG_DBG("Normal mouse speed: %d", (int)next);
    return ZMK_BEHAVIOR_OPAQUE;
}

static int control_released(struct zmk_behavior_binding *binding,
                            struct zmk_behavior_binding_event event) {
    (void)event;
    if (binding->param1 > MS_PREC_TOGGLE) return -EINVAL;
    update_mode(binding->param1, false);
    return ZMK_BEHAVIOR_OPAQUE;
}

static const struct behavior_driver_api control_api = {
    .binding_pressed = control_pressed,
    .binding_released = control_released,
#if IS_ENABLED(CONFIG_ZMK_BEHAVIOR_METADATA)
    .get_parameter_metadata = zmk_behavior_get_empty_param_metadata,
#endif
};
BEHAVIOR_DT_DEFINE(DT_INST(0, aefreedman_mouse_speed), NULL, NULL, NULL, NULL,
                   POST_KERNEL, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &control_api);

static int pointer_scale(const struct device *dev, struct input_event *event,
                         uint32_t param1, uint32_t param2,
                         struct zmk_input_processor_state *state) {
    (void)dev;
    (void)param1;
    (void)param2;
    if (event->type != INPUT_EV_REL ||
        (event->code != INPUT_REL_X && event->code != INPUT_REL_Y)) {
        return ZMK_INPUT_PROC_CONTINUE;
    }
    uint32_t flags = atomic_get(&mode_flags);
    int32_t speed = ms_effective_speed(atomic_get(&normal_speed), flags);
    event->value = ms_scale(event->value, speed, state ? state->remainder : NULL);
    LOG_DBG("Pointer speed scale: %d at %d mode %d", (int)event->value, (int)speed, (int)flags);
    return ZMK_INPUT_PROC_CONTINUE;
}

static const struct zmk_input_processor_driver_api scale_api = {
    .handle_event = pointer_scale,
};
DEVICE_DT_DEFINE(DT_INST(0, aefreedman_mouse_speed_scaler), NULL, NULL, NULL, NULL,
                 POST_KERNEL, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &scale_api);
#endif
