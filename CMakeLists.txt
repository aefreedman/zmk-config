# Include before core keymap/HID listeners so dances resolve before lookup/reporting.
if(CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
  target_sources(app PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/src/reviung_dance.c
    ${CMAKE_CURRENT_LIST_DIR}/src/behavior_reviung.c
    ${CMAKE_CURRENT_LIST_DIR}/src/behavior_reviung_base.c)
endif()
