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
from the firmware source on each run. The custom PIN layout and complete scrolling Settings
page are also extracted from the firmware; their controller callbacks are excluded. Launcher actions are instrumented callbacks;
radio/node/channel data, time, audio, alarm persistence and PSRAM have explicit host substitutes.
The launcher fixture includes 18 apps, three pages, and an intentionally long name.
It does not recreate the complete firmware controller, SD app installation, PIN
authorization, Wi-Fi, mesh traffic, map tiles, or physical trackball driver.

Checks use LVGL's pointer driver for taps, holds and swipes, and its focus group
for navigation. Assertions cover tile bounds, focus across pages, click routing,
both swipe directions, no idle display flushes, 100 create/delete cycles without
retained LVGL heap, 100 alternating theme refreshes without retained heap, calculator arithmetic/error recovery/Back, keyboard arithmetic, clock mode
navigation, note title entry and delete-dialog cancellation. Header, PIN, confirmation
and node-action labels are checked for bounds and overlap. Settings checks every
visible sibling control and every label pair, including rows outside the viewport.
Its cursor hints come from the actual update function in both on/off states.
Pointer tests cover Settings slider dragging, switch toggling, timezone menu selection
and all 12 PIN keys; device persistence and PIN authorization are excluded. PIN errors
and the GPS failure caption are extracted from the source and checked for overlap. Node actions are opened
and closed through pointer input, and Favorites must render its fixture row. Utility screenshots include Notes without SD and its new-note editor.
Mesh and base lock screenshots check generated widget construction, not firmware
lock behavior. The simulator deliberately does not claim those controller paths
are tested.

Files uses the actual storage picker, byte formatter, row styles, action bar,
folder-name dialog, directory/trash selection callbacks and Back handler.
Pointer checks cover selection changes, folder descent, long-press selection,
scrolling, disabled unsafe names, copy/paste/cancel, restore/delete confirmation,
and returning Home. Notes opening and filesystem actions use explicit spies in
this visual harness. Storage, no-SD, full/unavailable internal storage, focus,
pressed, selected and dialog states have matching old/new captures. Error alerts
are checked on the active Files screen; the old screen failed to show that alert.
Capacity renders use host snprintf; the new formatter is also tested against
LVGL's restricted formatter without float or long-long support. Neither host
formatter is claimed to reproduce ESP32 libc exactly.
100 Files list rebuilds and 100 error notices retain no heap; idle Files causes no display flushes. Long error text scrolls by touch while OK remains visible.

Run actual extracted storage functions against failure-injecting filesystem handles:

```sh
python3 bin/ui-simulator/test_files_storage.py
python3 bin/ui-simulator/test_settings_preferences.py
```

These cover partial/failed/growing copies, fresh capacity checks, safe filename
bounds, recursive deletion failures, trash-name/metadata collisions, and failed
metadata writes or renames. NVS tests cover checked write results with a Preferences
substitute; they do not emulate physical flash. Copy retains its existing temporary
4 KiB PSRAM buffer. SD I/O remains synchronous, so its hardware latency is not
measured by these host tests.

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

Open `.pio/ui-simulator/comparison.html` for 47 matching old/new states and a grid toggle.
The gallery labels its coverage limits; it is not a complete device walkthrough.

On this 64-bit host, the identical fixture used 43,592 bytes of LVGL heap before
and 38,792 after (4,800 bytes / 11% less). These are component heap measurements,
not the ESP32's total memory or hardware CPU measurements. The Files screen fixture uses
8,168 bytes versus 8,392 before; shared row styles avoid repeating their property
allocations for every directory entry. These immutable row styles live in flash. The new style removes
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

Settings persistence has a separate headless firmware target (Linux, or the repository's
native-test Docker image):

```sh
./bin/run-tests.sh -e native-settings-test -f test_admin_radio
python3 bin/ui-simulator/test_settings_preferences.py
```

The first command runs the real AdminModule, MeshService, NodeDB, SafeFile, and sound,
clock, units, and timezone bridges against an isolated host filesystem. It checks
save/readback, rejected writes, preservation of the last committed settings, and error
notifications. Its dedicated environment excludes ESP32-only UI/bridge sources and the
standalone chess test executables; only the unrelated raw USB remote-control hook is a
no-op. A successful filtered run reports `RESULT: FILTERED`, not a full-suite green.
The second command tests the real checked Preferences wrapper with failed and short NVS
writes injected through a fake ESP32 Preferences API. Neither test emulates physical
flash faults, NVS wear, SPI contention, or the device's available storage.

UI10 saving follow-up: Notes has an explicit Save action; failed saves keep the
editor and text. Actual Notes storage functions are tested for write/commit failures
and interrupted saves in the app-owned `/notes` directory. Arbitrary text files
opened through Files preserve existing transaction sidecars; an interrupted save
there may need manual recovery from `.tui-bak` rather than automatic cleanup.
Save errors identify the failed step instead of assuming
full/bad storage. The all-settings failure reported on a physical T-Deck has not
been reproduced locally; stage-specific device feedback is still required.

Additional regressions:
```sh
python3 bin/ui-simulator/test_notes_storage.py
python3 bin/ui-simulator/test_safe_file_readback.py
python3 bin/ui-simulator/test_settings_roundtrip.py
python3 bin/ui-simulator/test_timezone_pending.py
python3 bin/ui-simulator/test_screenshot_storage.py
```
