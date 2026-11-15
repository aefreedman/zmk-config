/* SPDX-License-Identifier: GPL-2.0-or-later */
#define DT_DRV_COMPAT aefreedman_base_select
#include <zephyr/device.h>
#include <drivers/behavior.h>
#include <zmk/behavior.h>
#include <zmk/keymap.h>

#if DT_HAS_COMPAT_STATUS_OKAY(DT_DRV_COMPAT)
static int pressed(struct zmk_behavior_binding *binding, struct zmk_behavior_binding_event event) {
    (void)event;
    if (binding->param1 > 2) return -EINVAL;
    /* Base IDs: Colemak=0 (always active), QWERTY=1, FPS=2. Leave overlays
     * including held ADJUST and toggled DJMAX untouched, like QMK DF().
     */
    zmk_keymap_layer_deactivate(1, true);
    zmk_keymap_layer_deactivate(2, true);
    if (binding->param1) zmk_keymap_layer_activate(binding->param1, true);
    return ZMK_BEHAVIOR_OPAQUE;
}
static int released(struct zmk_behavior_binding *binding, struct zmk_behavior_binding_event event) {
    (void)binding;
    (void)event;
    return ZMK_BEHAVIOR_OPAQUE;
}
static const struct behavior_driver_api api = {
    .binding_pressed = pressed,
    .binding_released = released,
#if IS_ENABLED(CONFIG_ZMK_BEHAVIOR_METADATA)
    .get_parameter_metadata = zmk_behavior_get_empty_param_metadata,
#endif
};
BEHAVIOR_DT_INST_DEFINE(0, NULL, NULL, NULL, NULL, POST_KERNEL,
                        CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &api);
#endif
