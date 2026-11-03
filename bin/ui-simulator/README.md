# Native LVGL UI simulator

Run on Linux with Python 3, GCC/G++, and the T-Deck PlatformIO dependencies installed:

```sh
python3 bin/ui-simulator/run.py
python3 bin/ui-simulator/grids.py .pio/ui-simulator
```

The second command needs Pillow. It produces native-resolution PNGs and 2x PNGs
with an 8-device-pixel alignment grid. No simulator code ships in firmware.

This is a **component simulator, not an ESP32 emulator**. It compiles the repository's
LVGL, fonts, actual calculator/clock/notes/status-bar implementations, generated
screens, and theme. It extracts the launcher icon and tile construction directly
from the firmware source on each run. Launcher actions are instrumented callbacks;
radio/node/channel data, time, audio, alarm persistence and PSRAM have explicit host substitutes.
The launcher fixture includes 18 apps, three pages, and an intentionally long name.
It does not recreate the complete firmware controller, SD app installation, PIN
authorization, Wi-Fi, mesh traffic, map tiles, or physical trackball driver.

Checks use LVGL's pointer driver for taps, holds and swipes, and its focus group
for navigation. Assertions cover tile bounds, focus across pages, click routing,
both swipe directions, no idle display flushes, 100 create/delete cycles without
retained LVGL heap, calculator arithmetic/error recovery/Back, keyboard arithmetic, clock mode
navigation, note title entry and delete-dialog cancellation. Utility screenshots include Notes without SD and its new-note editor.
Mesh and base lock screenshots check generated widget construction, not firmware
lock behavior. The simulator deliberately does not claim those controller paths
are tested.

Baseline launcher comparison:

```sh
python3 bin/ui-simulator/run.py --baseline cd363f267
```

The baseline renders the old component gallery without running the new regression assertions.
Rerun without the option afterwards, then export and assemble the comparison:
```sh
python3 bin/ui-simulator/grids.py .pio/ui-simulator
python3 bin/ui-simulator/gallery.py .pio/ui-simulator
```

Open `.pio/ui-simulator/comparison.html` for 17 matching old/new states and a grid toggle.
The gallery labels its coverage limits; it is not a complete device walkthrough.

On this 64-bit host, the identical fixture used 43,592 bytes of LVGL heap before
and 38,792 after (4,800 bytes / 11% less). These are component heap measurements,
not the ESP32's total memory or hardware CPU measurements. The new style removes
launcher gradients, shadow drawing and per-tile style duplication; it adds no
images, fonts, framebuffers or animation timers to firmware.

Hardware follow-up: verify boot, physical touch calibration, trackball navigation,
PIN unlock/sleep/wake, SD notes/files/maps/apps, messaging, Wi-Fi services and alarm
persistence on a T-Deck. In particular, simulator input timings do not measure
SPI contention with radio traffic.


The firmware's old focus-navigation mode remains disabled by its existing crash
guard. These focus tests validate LVGL widgets, not a repaired physical encoder
mode. Normal trackball pointer operation is preserved. Do not remove that guard
without separate input-group ownership and hardware validation.
