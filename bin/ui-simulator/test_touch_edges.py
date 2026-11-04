#!/usr/bin/env python3
"""Drive real LVGL scrolling through production touch input and LovyanGFX coordinate conversion."""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


def callback(source):
    start = source.index("template <class LGFX> void LGFXDriver<LGFX>::touchpad_read(")
    return source[start:source.index("\n}", start) + 2]


def harness_source():
    return r'''#include "lvgl.h"
#include <algorithm>
#include <cassert>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <vector>
static int32_t sampleX = 160, sampleY = 120;
static bool samplePressed = false;
volatile bool tdeck_input_gated = false;
struct touch_point_t { int32_t x, y; };
struct FakePanel {
    int32_t width() const { return 320; }
    int32_t height() const { return 240; }
    uint_fast8_t getTouch(touch_point_t *point, uint_fast8_t count) {
        if (!samplePressed || !count) return 0;
        point[0] = {sampleX, sampleY};
        return 1;
    }
GETTER
    bool getTouchXY(uint16_t *x, uint16_t *y) {
        if (!samplePressed) return false;
        *x = sampleX; *y = sampleY;
        return true;
    }
};
template <class LGFX> struct LGFXDriver {
    static LGFX *lgfx;
    static void touchpad_read(lv_indev_t *, lv_indev_data_t *);
};
template <class LGFX> LGFX *LGFXDriver<LGFX>::lgfx = nullptr;
CALLBACK
static uint16_t pixels[320 * 24];
static lv_indev_t *input;
static void step(int milliseconds = 35) {
    for (int elapsed = 0; elapsed < milliseconds; elapsed += 5) {
        lv_tick_inc(5);
        lv_timer_handler();
    }
}
static void readPointer(lv_indev_t *driver, lv_indev_data_t *data) {
    LGFXDriver<FakePanel>::touchpad_read(driver, data);
}
static void feed(int32_t x, int32_t y, bool pressed) {
    sampleX = x; sampleY = y; samplePressed = pressed;
    step();
}
static int clicks = 0;
static void clicked(lv_event_t *) { ++clicks; }
static int32_t position(lv_obj_t *screen, bool horizontal) {
    return horizontal ? lv_obj_get_scroll_x(screen) : lv_obj_get_scroll_y(screen);
}
static void dragEdge(bool horizontal, bool high) {
    auto *screen = lv_obj_create(nullptr);
    lv_obj_set_style_pad_all(screen, 0, 0);
    lv_obj_set_style_border_width(screen, 0, 0);
    lv_obj_set_scroll_dir(screen, horizontal ? LV_DIR_HOR : LV_DIR_VER);
    lv_obj_remove_flag(screen, LV_OBJ_FLAG_SCROLL_ELASTIC);
    lv_obj_remove_flag(screen, LV_OBJ_FLAG_SCROLL_MOMENTUM);
    auto *content = lv_obj_create(screen);
    lv_obj_set_size(content, horizontal ? 2400 : 320, horizontal ? 240 : 2400);
    lv_obj_set_pos(content, 0, 0);
    lv_obj_remove_flag(content, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(content, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_event_cb(screen, clicked, LV_EVENT_CLICKED, nullptr);
    lv_screen_load(screen);
    lv_obj_update_layout(screen);
    if (horizontal) lv_obj_scroll_to_x(screen, 700, LV_ANIM_OFF);
    else lv_obj_scroll_to_y(screen, 700, LV_ANIM_OFF);
    const int32_t maximum = horizontal ? 319 : 239;
    const int32_t initial = high ? 60 : maximum - 60;
    auto send = [&](int32_t coordinate, bool pressed) {
        feed(horizontal ? coordinate : 160, horizontal ? 120 : coordinate, pressed);
    };
    send(initial, false);
    send(initial, true);
    int32_t last = position(screen, horizontal);
    const int beforeClicks = clicks;
    std::vector<int32_t> sequence;
    for (int32_t p = initial + (high ? 25 : -25); p > 0 && p < maximum; p += high ? 25 : -25)
        sequence.push_back(p);
    sequence.push_back(high ? maximum : 0);
    sequence.push_back(high ? maximum + 1 : -1);
    sequence.push_back(high ? maximum + 8 : -6);
#ifdef CUSTOM_TOUCH_DRIVER
    sequence.push_back(high ? INT16_MAX : INT16_MIN);
#else
    sequence.push_back(high ? INT32_MAX : INT32_MIN);
#endif
    sequence.push_back(high ? maximum : 0);
    sequence.push_back(high ? maximum - 1 : 1);
    sequence.push_back(high ? maximum - 15 : 15);
    sequence.push_back(high ? maximum - 30 : 30);
    bool moved = false;
    for (int32_t p : sequence) {
        send(p, true);
        const int32_t current = position(screen, horizontal);
        const int32_t delta = current - last;
        if (std::abs(delta) > 40 || current < 350 || current > 1050) {
            fprintf(stderr, "EDGE_JUMP axis=%s edge=%s raw=%d previous=%d actual=%d\n",
                    horizontal ? "x" : "y", high ? "high" : "low", int(p), int(last), int(current));
            exit(2);
        }
        moved |= current != last;
        last = current;
    }
    assert(moved && clicks == beforeClicks);
    send(high ? maximum - 30 : 30, false);
    step(100);
    assert(position(screen, horizontal) == last && clicks == beforeClicks);
    send(initial, true);
    assert(position(screen, horizontal) == last);
    send(initial + (high ? 35 : -35), true);
    const int32_t resumed = position(screen, horizontal);
    assert(std::abs(resumed - last) <= 40 && resumed != last);
    send(initial + (high ? 35 : -35), false);
    assert(clicks == beforeClicks);
    step(100);
    send(initial, true);
    send(initial, false);
    assert(clicks == beforeClicks + 1);
    lv_indev_reset(input, nullptr);
}
static void checkCoordinates() {
    const int32_t xs[] = {-16, -1, 0, 1, 318, 319, 320, 32767};
    const int32_t ys[] = {-16, -1, 0, 1, 238, 239, 240, 32767};
    samplePressed = true;
    for (int32_t x : xs) for (int32_t y : ys) {
        sampleX = x; sampleY = y;
        lv_indev_data_t data{};
        readPointer(input, &data);
        assert(data.state == LV_INDEV_STATE_PRESSED);
        assert(data.point.x == std::clamp<int32_t>(x, 0, 319));
        assert(data.point.y == std::clamp<int32_t>(y, 0, 239));
    }
    lv_indev_data_t data{};
    data.point = {77, 88};
    samplePressed = false;
    readPointer(input, &data);
    assert(data.state == LV_INDEV_STATE_RELEASED && data.point.x == 77 && data.point.y == 88);
    samplePressed = true;
    tdeck_input_gated = true;
    readPointer(input, &data);
    assert(data.state == LV_INDEV_STATE_RELEASED && data.point.x == 77 && data.point.y == 88);
    tdeck_input_gated = false;
    samplePressed = false;
}
int main() {
    lv_init();
    auto *display = lv_display_create(320, 240);
    lv_display_set_color_format(display, LV_COLOR_FORMAT_RGB565);
    lv_display_set_buffers(display, pixels, nullptr, sizeof(pixels), LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(display, [](lv_display_t *d, const lv_area_t *, uint8_t *) { lv_display_flush_ready(d); });
    FakePanel panel;
    LGFXDriver<FakePanel>::lgfx = &panel;
    input = lv_indev_create();
    lv_indev_set_type(input, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(input, readPointer);
    lv_indev_set_display(input, display);
    lv_timer_set_period(lv_indev_get_read_timer(input), 5);
    dragEdge(false, false);
    dragEdge(false, true);
    dragEdge(true, false);
    dragEdge(true, true);
    checkCoordinates();
    puts("PASS: four-edge drags, signed/overflow samples, release/reentry, no scroll jumps or accidental clicks, gate and coordinate bounds");
    lv_deinit();
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulator", type=Path)
    parser.add_argument(
        "--negative-control", default="265ae5783",
        help="Git revision containing the previous touch callback",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    simulator = (args.simulator or root / ".pio/ui-simulator").resolve()
    lvgl = root / ".pio/libdeps/t-deck-tft/lvgl"
    ui = root / "lib/meshtastic-device-ui"
    path = "lib/meshtastic-device-ui/include/graphics/driver/LGFXDriver.h"
    fixed = callback((root / path).read_text())
    previous = callback(subprocess.check_output(
        ["git", "-c", f"safe.directory={root}", "show", f"{args.negative_control}:{path}"],
        cwd=root, text=True,
    ))
    getter_source = (root / ".pio/libdeps/t-deck-tft/LovyanGFX/src/lgfx/v1/LGFXBase.hpp").read_text()
    start = getter_source.index("    template <typename T>\n    uint_fast8_t getTouch(T *x")
    getter = getter_source[start:getter_source.index("\n    }", start) + len("\n    }")]
    objects = []
    for identity in (simulator / "obj").glob("*.source"):
        compiled_source = identity.read_text().replace("\\", "/").strip()
        required = "/lvgl/src/" in compiled_source or compiled_source.endswith("/ui_font_montserrat_16.c")
        if required and identity.with_suffix(".o").is_file():
            objects.append(str(identity.with_suffix(".o")))
    compiler = shutil.which("g++")
    if not compiler or not objects:
        raise SystemExit("g++ and cached LVGL objects are required; run bin/ui-simulator/run.py first")
    harness = harness_source().replace("GETTER", getter)
    with tempfile.TemporaryDirectory(prefix="touch-edges-") as scratch:
        scratch = Path(scratch)
        variants = (("previous", previous, False), ("fixed", fixed, False), ("fixed-custom", fixed, True))
        for label, body, custom in variants:
            cpp = scratch / f"{label}.cpp"
            executable = scratch / label
            cpp.write_text(harness.replace("CALLBACK", body))
            flags = [
                "-std=c++17", "-O2", "-g", "-ffunction-sections", "-fdata-sections", "-DLV_CONF_INCLUDE_SIMPLE",
                "-DRAM_SIZE=2048", "-DUSE_X11=0", "-DLV_USE_LIBINPUT=0", f"-I{lvgl}", f"-I{ui / 'include'}",
            ]
            if custom:
                flags.append("-DCUSTOM_TOUCH_DRIVER")
            compilation = subprocess.run(
                [compiler, *flags, str(cpp), *objects, "-Wl,--gc-sections", "-lm", "-o", str(executable)],
                text=True, capture_output=True,
            )
            if compilation.returncode:
                raise SystemExit(compilation.stderr)
            result = subprocess.run([str(executable)], text=True, capture_output=True)
            if label == "previous":
                if result.returncode != 2 or "EDGE_JUMP" not in result.stderr:
                    raise SystemExit(f"Negative control did not reproduce the scroll jump: {result.stdout}{result.stderr}")
                print("EXPECTED PREVIOUS FAILURE:", result.stderr.strip())
            else:
                if result.returncode:
                    raise SystemExit(f"{label} failed: {result.stdout}{result.stderr}")
                print(label + ": " + result.stdout.strip())
    print("Actual LVGL/production adapter tested; controller/I2C samples are injected, not hardware emulation")


if __name__ == "__main__":
    main()
