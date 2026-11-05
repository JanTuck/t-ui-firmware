# Control Center host tests

Run against a host-built LVGL 9.3 library and its matching configuration:

```sh
LVGL_ROOT=/path/to/lvgl \
LVGL_CONFIG_DIR=/path/to/config \
LVGL_LIBRARY=/path/to/liblvgl.a \
bash lib/meshtastic-device-ui/tests/control_center/run.sh
```

The tests compile the production panel and fonts with simulated input and firmware callbacks. They cover corner gesture rejection, radio confirmation and disabled controls, pointer taps at five brightness levels, bidirectional drags through the sun glyph, drag-outside and actual press-lost delivery, one persistent write per changed drag, keypad/encoder persistence and group restoration, modal/lock/screen changes during dragging, text-entry gating, 200 open/close heap cycles, and idle redraw suppression. Brightness input checks also reject any radio callback or unintended panel dismissal. LVGL reaches maximum one pixel above the top edge, inside the extended hit area. They do not validate physical input drivers or radio hardware.

The status bar suite also checks idle redraw suppression and notification, clock, and battery updates.
