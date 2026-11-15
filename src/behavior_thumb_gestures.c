/* SPDX-License-Identifier: GPL-2.0-or-later */
#define DT_DRV_COMPAT aefreedman_thumb_gestures
#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <drivers/behavior.h>
#include <zmk/behavior.h>
#include <zmk/event_manager.h>
#include <zmk/events/keycode_state_changed.h>
#include <zmk/events/position_state_changed.h>
#include <zmk/keymap.h>
#include <dt-bindings/zmk/keys.h>
#include <string.h>
#include "thumb_gestures.h"

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)

static struct tg_engine engine;
static struct k_work_delayable timer;
static uint32_t positions[TG_COUNT];
static bool emitting;
extern const struct zmk_listener zmk_listener_thumb_gestures;
#define SYM_LAYER DT_INST_PROP(0, symbol_layer)

static void schedule(void) {
    int64_t deadline = tg_next_deadline(&engine);
    if (deadline) {
        int64_t delay = deadline - k_uptime_get();
        k_work_reschedule(&timer, K_MSEC(MAX(1, delay)));
    } else {
        k_work_cancel_delayable(&timer);
    }
}

static void emit_mods(uint8_t old, uint8_t current, int64_t now) {
    static const uint32_t codes[] = {LCTRL, LSHFT, LALT};
    bool previous = emitting;
    emitting = true;
    for (unsigned i = 0; i < ARRAY_SIZE(codes); i++) {
        if ((old ^ current) & BIT(i)) {
            raise_zmk_keycode_state_changed_from_encoded(codes[i], (current & BIT(i)) != 0, now);
        }
    }
    emitting = previous;
}

static void emit_symbols(bool active, int64_t now) {
    (void)now;
    if (active) zmk_keymap_layer_activate(SYM_LAYER, false);
    else zmk_keymap_layer_deactivate(SYM_LAYER, false);
}

static void emit_enter(int64_t now) {
    /* This passes through our keycode listener so pending one-shots apply to Enter. */
    raise_zmk_keycode_state_changed_from_encoded(RET, true, now);
    raise_zmk_keycode_state_changed_from_encoded(RET, false, now);
}

static void timer_handler(struct k_work *work) {
    (void)work;
    tg_tick(&engine, k_uptime_get());
    schedule();
}

static int pressed(struct zmk_behavior_binding *binding, struct zmk_behavior_binding_event event) {
    if (binding->param1 >= TG_COUNT) return -EINVAL;
    positions[binding->param1] = event.position;
    tg_press(&engine, binding->param1, event.timestamp);
    schedule();
    return ZMK_BEHAVIOR_OPAQUE;
}

static int released(struct zmk_behavior_binding *binding, struct zmk_behavior_binding_event event) {
    if (binding->param1 >= TG_COUNT) return -EINVAL;
    tg_release(&engine, binding->param1, event.timestamp);
    schedule();
    return ZMK_BEHAVIOR_OPAQUE;
}

/* Resolve the ACTUAL active binding, rather than a position-only whitelist:
 * the same position may be a layer key on one layer and punctuation on another.
 * Studio layer reordering is deliberately not enabled in this initial config.
 */
static const struct zmk_behavior_binding *binding_at(uint32_t position) {
    for (int i = ZMK_KEYMAP_LAYERS_LEN - 1; i >= 0; i--) {
        if (!zmk_keymap_layer_active(i)) continue;
        const struct zmk_behavior_binding *b = zmk_keymap_get_layer_binding_at_idx(i, position);
        if (b && b->behavior_dev && strcmp(b->behavior_dev, DEVICE_DT_NAME(DT_NODELABEL(trans)))) {
            return b;
        }
    }
    return NULL;
}

static int on_position(const struct zmk_position_state_changed *ev) {
    if (!ev->state) return ZMK_EV_EVENT_BUBBLE;
    const struct zmk_behavior_binding *b = binding_at(ev->position);
    int own_kind = -1;
    bool modifier_or_layer = false;
    if (b) {
        if (!strcmp(b->behavior_dev, DEVICE_DT_NAME(DT_INST(0, aefreedman_thumb_gestures)))) {
            own_kind = b->param1;
            modifier_or_layer = true;
        } else if (!strcmp(b->behavior_dev, DEVICE_DT_NAME(DT_NODELABEL(kp)))) {
            modifier_or_layer = is_mod(ZMK_HID_USAGE_PAGE(b->param1), ZMK_HID_USAGE_ID(b->param1));
        } else {
            /* Only the behavior types used by this map are classified here. */
            modifier_or_layer =
                !strcmp(b->behavior_dev, DEVICE_DT_NAME(DT_NODELABEL(lt))) ||
                !strcmp(b->behavior_dev, DEVICE_DT_NAME(DT_NODELABEL(mo))) ||
                !strcmp(b->behavior_dev, DEVICE_DT_NAME(DT_NODELABEL(tog))) ||
                !strcmp(b->behavior_dev, DEVICE_DT_NAME(DT_NODELABEL(base_select))) ||
                !strcmp(b->behavior_dev, DEVICE_DT_NAME(DT_NODELABEL(ms_fast))) ||
                !strcmp(b->behavior_dev, DEVICE_DT_NAME(DT_NODELABEL(ms_precision))) ||
                !strcmp(b->behavior_dev, DEVICE_DT_NAME(DT_NODELABEL(ms_down))) ||
                !strcmp(b->behavior_dev, DEVICE_DT_NAME(DT_NODELABEL(ms_up)));
        }
    }
    for (unsigned i = 0; i < TG_COUNT; i++) {
        if (engine.dances[i].active && positions[i] == ev->position) {
            own_kind = i;
            break;
        }
    }
    tg_interrupt(&engine, own_kind, modifier_or_layer, ev->timestamp);
    schedule();
    return ZMK_EV_EVENT_BUBBLE;
}

static int listener(const zmk_event_t *eh) {
    const struct zmk_position_state_changed *position = as_zmk_position_state_changed(eh);
    if (position) return on_position(position);
    const struct zmk_keycode_state_changed *key = as_zmk_keycode_state_changed(eh);
    if (!key || emitting || !key->state || is_mod(key->usage_page, key->keycode)) {
        return ZMK_EV_EVENT_BUBBLE;
    }
    /* Keep modifiers through the consuming key's down report, then release only
     * our pending one-shots. Held modifiers remain active for subsequent keys.
     */
    int64_t now = key->timestamp;
    tg_tick(&engine, now);
    if (!engine.pending && !engine.pending_symbols) return ZMK_EV_EVENT_BUBBLE;
    struct zmk_keycode_state_changed_event copy = copy_raised_zmk_keycode_state_changed(key);
    ZMK_EVENT_RAISE_AFTER(copy, thumb_gestures);
    tg_consume(&engine, now);
    schedule();
    return ZMK_EV_EVENT_HANDLED;
}

ZMK_LISTENER(thumb_gestures, listener);
ZMK_SUBSCRIPTION(thumb_gestures, zmk_position_state_changed);
ZMK_SUBSCRIPTION(thumb_gestures, zmk_keycode_state_changed);

static int init(const struct device *dev) {
    (void)dev;
    tg_init(&engine, emit_mods, emit_symbols, emit_enter);
    k_work_init_delayable(&timer, timer_handler);
    return 0;
}

static const struct behavior_driver_api api = {
    .binding_pressed = pressed,
    .binding_released = released,
#if IS_ENABLED(CONFIG_ZMK_BEHAVIOR_METADATA)
    .get_parameter_metadata = zmk_behavior_get_empty_param_metadata,
#endif
};
BEHAVIOR_DT_INST_DEFINE(0, init, NULL, NULL, NULL, POST_KERNEL,
                        CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &api);
#endif
