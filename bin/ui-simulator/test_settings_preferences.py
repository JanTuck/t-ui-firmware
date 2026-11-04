#!/usr/bin/env python3
"""Fault-inject the real checked Preferences wrapper; the ESP32 NVS API is a host fake."""

from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        raise SystemExit("g++ or clang++ is required")
    with tempfile.TemporaryDirectory(prefix="settings-nvs-") as scratch:
        path = Path(scratch)
        (path / "Preferences.h").write_text(
            """#pragma once
#include <cstddef>
#include <cstdint>
inline bool openResult = true;
inline bool failWrite = false;
inline bool shortWrite = false;
class Preferences {
public:
    bool begin(const char *, bool, const char *) { return openResult; }
    size_t write(size_t size) { return failWrite ? 0 : shortWrite ? size - 1 : size; }
    size_t putBool(const char *, bool) { return write(1); }
    size_t putUChar(const char *, uint8_t) { return write(1); }
    size_t putShort(const char *, int16_t) { return write(2); }
    size_t putUShort(const char *, uint16_t) { return write(2); }
    size_t putUInt(const char *, uint32_t) { return write(4); }
    size_t putLong(const char *, int32_t) { return write(4); }
};
"""
        )
        source = path / "test.cpp"
        source.write_text(
            """#include "TDeckSettingsPreferences.h"
#include <cassert>
static int errors = 0;
void tdeck_settings_save_failed(SettingsSaveError) { ++errors; }
void writeSettings(TDeckSettingsPreferences &p) {
    p.putBool("nav", true);
    p.putUChar("spd", 4);
    p.putShort("fired", 123);
    p.putUShort("wxmins", 60);
    p.putUInt("grace", 30);
    p.putLong("plat", -1234567);
}
int main() {
    TDeckSettingsPreferences p;
    assert(p.begin("settings", false));
    writeSettings(p);
    assert(errors == 0);
    failWrite = true;
    writeSettings(p);
    assert(errors == 6);
    failWrite = false;
    shortWrite = true;
    writeSettings(p);
    assert(errors == 12);
    openResult = false;
    assert(!p.begin("missing", true));
    assert(errors == 12);
    assert(!p.begin("full", false));
    assert(errors == 13);
}
"""
        )
        executable = path / "test"
        subprocess.run(
            [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", f"-I{path}", f"-I{root / 'src'}", str(source), "-o", str(executable)],
            check=True,
        )
        subprocess.run([str(executable)], check=True)
    print("Checked NVS writes: success, failed open, failed write, short write, and first-boot read passed")


if __name__ == "__main__":
    main()
