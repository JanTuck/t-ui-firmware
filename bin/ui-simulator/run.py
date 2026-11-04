from pathlib import Path
import argparse
import concurrent.futures
import subprocess
import os
import re

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument("--out", type=Path, default=Path(".pio/ui-simulator"))
parser.add_argument("--baseline", help="Git revision to render for the launcher comparison")
args = parser.parse_args()
root, out = args.root.resolve(), args.out.resolve()
out.mkdir(parents=True, exist_ok=True)
ui = root / "lib/meshtastic-device-ui"
lv = root / ".pio/libdeps/t-deck-tft/lvgl"
source = (ui / "source/graphics/TFT/TFTView_320x240.cpp").read_text()
if args.baseline:
    source = subprocess.check_output(["git", "-c", f"safe.directory={root}", "show", f"{args.baseline}:lib/meshtastic-device-ui/source/graphics/TFT/TFTView_320x240.cpp"], cwd=root, text=True)
icons = source[source.index("uint32_t tintAccent" if args.baseline else "lv_obj_t *icBox"):source.index("// Draw an app's OWN icon")]
(out / "icons.inc").write_text(icons)
grid = source[source.index("    lv_obj_t *page = nullptr;", source.index("void TFTView_320x240::buildAppGrid")):source.index("    if (pageCount > 1)", source.index("void TFTView_320x240::buildAppGrid"))]
grid = grid.replace("buildTileIconFromFile(tile, ip)", "false")
(out / "grid.inc").write_text(grid)
pin_start = source.index("        lockpad_screen = lv_obj_create(NULL);")
pin_end = source.index("        lv_obj_add_event_cb(pad, lockpad_event", pin_start)
(out / "lockpad.inc").write_text(source[pin_start:pin_end])
pin_messages = re.findall(r'lv_label_set_text\(lock_title_label, "([^"\n]+)"\);', source)
(out / "pin-messages.inc").write_text(
    "static const char *pinMessages[] = {" + ",".join('"' + text + '"' for text in pin_messages) + "};")
settings_start = source.index("{", source.index("void TFTView_320x240::createSettingsScreen")) + 1
settings_end = source.index('\n}', settings_start)
settings = source[settings_start:settings_end]
settings = re.sub(r"lv_obj_add_event_cb\(.*?LV_EVENT_(?:CLICKED|ALL|VALUE_CHANGED), NULL\);", "", settings, flags=re.S)
settings = re.sub(r"    wifi_status_timer = lv_timer_create.*?;\n", "", settings)
for call, replacement in {
    "updateLocPrecisionLabel()": 'lv_label_set_text(loc_precision_label, "Rough")',
    "updateWifiNetLabel()": 'lv_label_set_text(wifi_net_btn_lbl, "Trail network")',
    "updateWifiStatus()": 'lv_label_set_text(wifi_status_label, "Wi-Fi off")',
    "updateTimeoutBtnLabel()": 'lv_label_set_text(timeout_btn_label, "1 minute")',
    "tdeck_gps_get_enabled()": "true", "tdeck_sound_get_enabled()": "true",
    "tdeck_tz_get()": "-1", "tdeck_clock_get_12h()": "false",
    "tdeck_trackball_nav_enabled()": "true", "TUI_VERSION": '\"fixture\"',
    "firmware_version": '\"fixture\"',
}.items():
    settings = settings.replace(call, replacement)
(out / "settings.inc").write_text(settings)
gps_error = re.search(r'else if \(st == 3\).*?lv_label_set_text\(THIS->share_now_hint,\s*"([^"]+)"', source, re.S).group(1)
(out / "settings-messages.inc").write_text('static const char *gpsError = "' + gps_error + '";')
trackball_start = source.index("{", source.index("void TFTView_320x240::updateTrackballRows")) + 1
trackball = source[trackball_start:source.index("\n}", trackball_start)]
trackball = trackball.replace("tdeck_trackball_nav_enabled()", "fixtureCursor").replace("tdeck_trackball_speed()", "1").replace("tdeck_trackball_style()", "0")
(out / "trackball.inc").write_text(trackball)
for name, signature in (("files-build", "void TFTView_320x240::openFiles(void)"),
                        ("files-actions", "void TFTView_320x240::filesUpdateActionBar(void)"),
                        ("files-newfolder", "void TFTView_320x240::filesNewFolderPrompt(void)"),
                        ("files-closefolder", "void TFTView_320x240::closeNewFolder(void)"),
                        ("files-back", "void TFTView_320x240::handleBackGesture(void)"),
                        ("files-notice", "void TFTView_320x240::notifyClientNotification(const char *message)"),
                        ("files-message", "void TFTView_320x240::messageAlert(const char *alert, bool show)"),
                        ("files-name-fit", "bool filesNameFits("), ("files-empty", "void filesEmptyLabel("), ("files-format", "void fmtBytes("), ("files-row", "void filesStyleRow(")):
    if name == "files-name-fit" and signature not in source:
        (out / (name + ".inc")).write_text('bool filesNameFits(const char *, size_t, bool) { return true; }')
        continue
    if name == "files-empty" and signature not in source:
        (out / (name + ".inc")).write_text('void filesEmptyLabel(lv_obj_t *list, const char *text) { lv_list_add_text(list, text); }')
        continue
    if name == "files-notice" and signature not in source:
        (out / (name + ".inc")).write_text('void notifyClientNotification(const char *) {}')
        continue
    start = source.index(signature)
    end = source.index("\n}", start) + 2
    fragment = source[start:end].replace("TFTView_320x240::", "")
    (out / (name + ".inc")).write_text(fragment)
start = source.index("    if (filesVol == VOL_ROOT)", source.index("void TFTView_320x240::filesRefresh"))
end = source.index("        return;", start) + len("        return;\n    }")
(out / "files-root.inc").write_text(source[start:end])
start = source.index("    auto entry_cb =", source.index("void TFTView_320x240::filesRefresh"))
end = source.index("    int count = 0;", start)
(out / "files-entries.inc").write_text(source[start:end])
start = source.index("        auto trash_cb =", source.index("void TFTView_320x240::filesRefresh"))
end = source.index("        int count = 0;", start)
(out / "files-trash-select.inc").write_text(source[start:end])
start = source.index("    bool onSd = (filesVol == VOL_SD);", source.index("// ---------- browsing a volume"))
end = source.index("    // entry tap:", start)
(out / "files-capacity.inc").write_text(source[start:end])
flags = ["-O2", "-g", "-ffunction-sections", "-fdata-sections", "-DLV_CONF_INCLUDE_SIMPLE",
         "-DRAM_SIZE=2048", "-DUSE_X11=0", "-DLV_USE_LIBINPUT=0"]
flags += [f"-I{p}" for p in [out, lv, lv.parent, ui / "include", ui / "generated/ui_320x240"]]
sources = list((lv / "src").rglob("*.c"))
sources += [ui / "generated/ui_320x240/ui_font_montserrat_12.c", root / "bin/ui-simulator/main.cpp"]
sources += [ui / f"generated/ui_320x240/ui_font_montserrat_{n}.c" for n in (14, 16, 20)]
sources += [ui / f"source/graphics/TFT/{n}.cpp" for n in ("CalculatorApp", "NotesApp", "StopwatchApp", "TuiStatusBar", "TuiLabel")]
(out / "Arduino.h").write_text('#pragma once\n#include "lvgl.h"\n#include <initializer_list>\n#include <cstring>\ninline uint32_t millis() { return lv_tick_get(); }\n')
(out / "host-memory.h").write_text('#include <cstdlib>\n#define MALLOC_CAP_SPIRAM 0\ninline void *heap_caps_calloc(size_t n, size_t s, int) { return calloc(n, s); }\n')
sources += [p for p in (ui / "generated/ui_320x240").glob("*.c") if p.name != "ui.c" and p not in sources]
sources += [ui / "source/graphics/TFT/Themes.cpp", ui / "source/graphics/TFT/NodesApp.cpp", ui / "source/graphics/TFT/ChannelsApp.cpp", root / "bin/ui-simulator/fixtures.cpp"]
if args.baseline:
    baseline_dir = out / "baseline"
    baseline_dir.mkdir(exist_ok=True)
    for i, src in enumerate(sources):
        if src.suffix == ".cpp" and src.is_relative_to(ui):
            relative = src.relative_to(root).as_posix()
            old = subprocess.check_output(["git", "-c", f"safe.directory={root}", "show", f"{args.baseline}:{relative}"], cwd=root)
            sources[i] = baseline_dir / src.name
            sources[i].write_bytes(old)
(out / "lv_i18n.h").write_text('#pragma once\n#define _(s) (s)\n')
objdir = out / "obj"
objdir.mkdir(exist_ok=True)
def compile_one(pair):
    n, src = pair
    obj = objdir / f"{n}.o"
    # Rebuild the harness on every run, including its extracted firmware fragments.
    identity = obj.with_suffix(".source")
    if identity.exists() and identity.read_text() == str(src) and src.name != "main.cpp" and obj.exists() and obj.stat().st_mtime > max(src.stat().st_mtime, (ui / "include/graphics/view/TFT/TuiStyle.h").stat().st_mtime if src.suffix == ".cpp" else 0):
        return str(obj)
    subprocess.run(["g++" if src.suffix == ".cpp" else "gcc", *flags, *(["-DVIEW_320x240"] if src.name == "Themes.cpp" else []), *(["-include", str(out / "host-memory.h")] if src.name == "NotesApp.cpp" else []), "-c", str(src), "-o", str(obj)], check=True, capture_output=True)
    identity.write_text(str(src))
    return str(obj)
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    try:
        objs = list(pool.map(compile_one, enumerate(sources)))
    except subprocess.CalledProcessError as exc:
        print(exc.stderr.decode())
        raise
subprocess.run(["g++", "-Wl,--gc-sections", *objs, "-lm", "-o", str(out / "simulator")], check=True)
subprocess.run([str(out / "simulator")], cwd=out, check=True, env={**os.environ, "SIM_BASELINE": "1" if args.baseline else ""})
