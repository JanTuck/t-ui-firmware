# Control Center host tests

Run against a host-built LVGL 9.3 library and its matching configuration:

```sh
LVGL_ROOT=/path/to/lvgl \
LVGL_CONFIG_DIR=/path/to/config \
LVGL_LIBRARY=/path/to/liblvgl.a \
bash lib/meshtastic-device-ui/tests/control_center/run.sh
```

The tests compile the production panel and fonts with simulated input and firmware callbacks. They cover corner gestures, radio confirmation, touch and keyboard brightness persistence, modal and lock gating, input focus restoration, screen changes, and idle redraw suppression. They do not validate physical input drivers or radio hardware.
