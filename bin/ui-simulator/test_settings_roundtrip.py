#!/usr/bin/env python3
"""Exercise real trackball settings with a retained fake NVS store, not physical flash."""
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        raise SystemExit("g++ or clang++ is required")
    with tempfile.TemporaryDirectory(prefix="settings-roundtrip-") as scratch:
        path = Path(scratch)
        shutil.copyfile(root / "src/TDeckTrackball.cpp", path / "TDeckTrackball.cpp")
        (path / "configuration.h").write_text('#pragma once\n#define LOG_INFO(...) ((void)0)\n')
        (path / "Preferences.h").write_text(r'''#pragma once
#include <cstdint>
#include <cstddef>
#include <map>
#include <string>
inline std::map<std::string, std::map<std::string, int64_t>> nvs;
inline bool failOpen = false, failWrite = false;
class Preferences {
    std::string space;
    bool readOnly = true, opened = false;
public:
    bool begin(const char *name, bool ro = false, const char * = nullptr) {
        space = name; readOnly = ro;
        opened = !failOpen && (!ro || nvs.count(space));
        if (opened && !ro) nvs[space];
        return opened;
    }
    void end() { opened = false; }
    int64_t get(const char *key, int64_t fallback) {
        return opened && nvs[space].count(key) ? nvs[space][key] : fallback;
    }
    bool getBool(const char *key, bool fallback) { return get(key, fallback); }
    uint8_t getUChar(const char *key, uint8_t fallback) { return get(key, fallback); }
    size_t put(const char *key, int64_t value, size_t bytes) {
        if (!opened || readOnly || failWrite) return 0;
        nvs[space][key] = value; return bytes;
    }
    size_t putBool(const char *k, bool v) { return put(k,v,1); }
    size_t putUChar(const char *k, uint8_t v) { return put(k,v,1); }
    size_t putShort(const char *k, int16_t v) { return put(k,v,2); }
    size_t putUShort(const char *k, uint16_t v) { return put(k,v,2); }
    size_t putUInt(const char *k, uint32_t v) { return put(k,v,4); }
    size_t putLong(const char *k, int32_t v) { return put(k,v,4); }
};
''')
        (path / "test.cpp").write_text(r'''#include "TDeckTrackball.cpp"
#include <cassert>
static int errors = 0;
static SettingsSaveError lastError = SettingsSaveError::None;
void tdeck_settings_save_failed(SettingsSaveError error) { ++errors; lastError = error; }
void coldCache() { s_tbNav = s_tbClick = s_tbSpeed = s_tbStyle = -1; }
int main() {
    coldCache();
    assert(!tdeck_trackball_nav_enabled());
    assert(!tdeck_trackball_click_enabled());
    assert(tdeck_trackball_speed() == 2);
    assert(tdeck_trackball_style() == 0);
    assert(errors == 0);
    tdeck_trackball_nav_set_enabled(true); coldCache();
    assert(tdeck_trackball_nav_enabled());
    tdeck_trackball_click_set_enabled(true); coldCache();
    assert(tdeck_trackball_click_enabled());
    tdeck_trackball_set_speed(4); coldCache();
    assert(tdeck_trackball_speed() == 4);
    tdeck_trackball_set_style(1); coldCache();
    assert(tdeck_trackball_style() == 1);
    const auto committed = nvs;
    assert(errors == 0);
    failWrite = true;
    tdeck_trackball_nav_set_enabled(false);
    tdeck_trackball_click_set_enabled(false);
    tdeck_trackball_set_speed(0);
    tdeck_trackball_set_style(0);
    assert(errors == 4 && nvs == committed);
    assert(lastError == SettingsSaveError::NvsWrite);
    failWrite = false; coldCache();
    assert(tdeck_trackball_nav_enabled() && tdeck_trackball_click_enabled());
    assert(tdeck_trackball_speed() == 4 && tdeck_trackball_style() == 1);
    failOpen = true; tdeck_trackball_set_speed(1);
    assert(errors == 5 && nvs == committed);
    assert(lastError == SettingsSaveError::NvsOpen);
    failOpen = false; coldCache();
    tdeck_trackball_set_speed(5); tdeck_trackball_set_style(-1);
    assert(errors == 5 && nvs == committed);
    assert(tdeck_trackball_speed() == 4 && tdeck_trackball_style() == 1);
    tdeck_trackball_nav_set_enabled(false); coldCache();
    assert(!tdeck_trackball_nav_enabled());
    tdeck_trackball_click_set_enabled(false); coldCache();
    assert(!tdeck_trackball_click_enabled());
    tdeck_trackball_set_speed(0); coldCache();
    assert(tdeck_trackball_speed() == 0);
    tdeck_trackball_set_style(0); coldCache();
    assert(tdeck_trackball_style() == 0);
    assert(errors == 5);
}
''')
        executable = path / "test"
        subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", f"-I{path}",
                        f"-I{root / 'src'}", str(path / "test.cpp"), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
    print("Actual trackball settings: defaults, isolated writes/cold-cache reads, failed opens/writes and bounds passed")


if __name__ == "__main__":
    main()
