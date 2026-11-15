# Include before core keymap/HID listeners so dances resolve before lookup/reporting.
if(NOT CONFIG_ZMK_SPLIT OR CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
  target_sources(app PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/src/thumb_gestures.c
    ${CMAKE_CURRENT_LIST_DIR}/src/behavior_thumb_gestures.c
    ${CMAKE_CURRENT_LIST_DIR}/src/behavior_base_select.c
    ${CMAKE_CURRENT_LIST_DIR}/src/mouse_speed.c)
endif()
