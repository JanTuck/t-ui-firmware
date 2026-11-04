#!/usr/bin/env python3
"""Exercise extracted UI surfaces with production touch input and real LVGL."""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from test_touch_edges import callback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulator", type=Path)
    parser.add_argument("--touch-ref", help="Read the callback from this git revision for a negative control")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    cache = (args.simulator or root / ".pio/ui-simulator").resolve()
    ui = root / "lib/meshtastic-device-ui"
    lv = root / ".pio/libdeps/t-deck-tft/lvgl"
    compiler = shutil.which("g++")
    objects = [str(p.with_suffix(".o")) for p in (cache / "obj").glob("*.source")
               if not p.read_text().replace("\\", "/").endswith("/main.cpp") and p.with_suffix(".o").is_file()]
    if not compiler or not objects:
        raise SystemExit("Run the component simulator first to populate its build cache")
    source = (root / "bin/ui-simulator/main.cpp").read_text()
    driver = "lib/meshtastic-device-ui/include/graphics/driver/LGFXDriver.h"
    production = callback(subprocess.check_output(
        ["git", "-c", f"safe.directory={root}", "show", f"{args.touch_ref}:{driver}"], text=True, cwd=root)
        if args.touch_ref else (root / driver).read_text())
    old_reader = '''static void readPointer(lv_indev_t *, lv_indev_data_t *data) {
  data->point = pointer;
  data->state = down ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
}'''
    reader = r'''volatile bool tdeck_input_gated = false;
struct SurfacePanel {
  int width() const { return 320; }
  int height() const { return 240; }
  template <typename T> bool getTouch(T *x, T *y) {
    *x = static_cast<int16_t>(pointer.x);
    *y = static_cast<int16_t>(pointer.y);
    return down;
  }
};
template <class LGFX> struct LGFXDriver {
  static LGFX *lgfx;
  static void touchpad_read(lv_indev_t *, lv_indev_data_t *);
};
template <class LGFX> LGFX *LGFXDriver<LGFX>::lgfx = nullptr;
CALLBACK
static void readPointer(lv_indev_t *input, lv_indev_data_t *data) {
  static SurfacePanel panel;
  LGFXDriver<SurfacePanel>::lgfx = &panel;
  LGFXDriver<SurfacePanel>::touchpad_read(input, data);
}
static void surfaceEdgeDrag(lv_obj_t *surface, const char *name, int x, int startY, int initialScroll) {
  lv_obj_scroll_to_y(surface, initialScroll, LV_ANIM_OFF);
  step(100);
  lv_area_t viewportBefore, viewportAfter;
  lv_obj_get_coords(surface, &viewportBefore);
  pointer = {x, startY}; down = false; step(40);
  down = true; step(40);
  int before = lv_obj_get_scroll_y(surface), last = before;
  assert(before >= initialScroll - 2);
  for (int y = startY - 10; y >= 0; y -= 10) {
    pointer.y = y; step(30);
    int current = lv_obj_get_scroll_y(surface);
    assert(current >= last - 2 && current - last <= 35);
    last = current;
  }
  for (int y : {0, -1, -6, -16, -40}) {
    pointer.y = y; step(30);
    int current = lv_obj_get_scroll_y(surface);
    assert(current >= last - 2 && current - last <= 35);
    last = current;
  }
  assert(last > before + 20);
  down = false; step(400);
  lv_obj_get_coords(surface, &viewportAfter);
  assert(viewportBefore.x1 == viewportAfter.x1 && viewportBefore.x2 == viewportAfter.x2);
  assert(viewportBefore.y1 == viewportAfter.y1 && viewportBefore.y2 == viewportAfter.y2);
  printf("PASS: %s signed top-edge drag: %d -> %d, no top reset\n", name, before, last);
}
'''.replace("CALLBACK", production)
    assert old_reader in source
    source = source.replace(old_reader, reader)
    source = source.replace("int main() {", "int main() {\n  setbuf(stdout, nullptr);")
    source = source.replace('  capture("settings-display.ppm");', '''  surfaceEdgeDrag(settings_screen, "Settings", 310, 180, 500);
  lv_obj_scroll_to_y(settings_screen, 0, LV_ANIM_OFF); step();
  capture("settings-display.ppm");''')
    source = source.replace('  assert(lv_obj_get_scroll_x(pager) >= 300);', '  assert(lv_obj_get_scroll_x(pager) >= 300);\n  puts("PASS: launcher edge swipe advances page");')
    source = source.replace('for (int x = 280; x >= 40; x -= 20)', 'for (int x = 280; x >= -20; x -= 20)')
    source = source.replace('for (int x = 40; x <= 280; x += 20)', 'for (int x = 40; x <= 340; x += 20)')
    fixture = (root / "bin/ui-simulator/files-fixture.h").read_text()
    fixture = fixture.replace('        assert(lv_obj_get_scroll_bottom(objects.alert_label) > 0);', '''        assert(lv_obj_get_scroll_bottom(objects.alert_label) > 0);
        surfaceEdgeDrag(objects.alert_label, "Long error text", 150, 150, 20);
        checkDialog(objects.alert_panel);
        lv_obj_scroll_to_y(objects.alert_label, 0, LV_ANIM_OFF); step();''')
    fixture = fixture.replace('        pointer = {200, 175};', '''        surfaceEdgeDrag(fixture.files_list, "Files list", 200, 175, 20);
        assert(!fixture.filesSelName[0]);
        lv_obj_scroll_to_y(fixture.files_list, 0, LV_ANIM_OFF); step();
        pointer = {200, 175};''')
    with tempfile.TemporaryDirectory(prefix="scroll-surfaces-") as scratch:
        temporary = Path(scratch)
        (temporary / "main.cpp").write_text(source)
        (temporary / "files-fixture.h").write_text(fixture)
        includes = [temporary, cache, lv, lv.parent, ui / "include", ui / "generated/ui_320x240"]
        obj = temporary / "main.o"
        subprocess.run([compiler, "-std=c++17", "-O2", "-g", "-ffunction-sections", "-fdata-sections",
                        "-DLV_CONF_INCLUDE_SIMPLE", "-DRAM_SIZE=2048", "-DUSE_X11=0", "-DLV_USE_LIBINPUT=0",
                        *(f"-I{p}" for p in includes), "-c", str(temporary / "main.cpp"), "-o", str(obj)], check=True)
        executable = temporary / "surfaces"
        subprocess.run([compiler, "-Wl,--gc-sections", str(obj), *objects, "-lm", "-o", str(executable)], check=True)
        subprocess.run([str(executable)], cwd=temporary, check=True)
    print("Surface checks passed; Settings callbacks and storage remain fixture substitutes, no physical touch bus emulation")


if __name__ == "__main__":
    main()
