#!/usr/bin/env python3
"""Run the actual screenshot service against controlled internal-storage capacity."""

from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/TDeckScreenshot.cpp").read_text(encoding="utf-8")
    service = source[source.index('extern "C" void tdeck_shot_service(void)'):]
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        raise SystemExit("g++ or clang++ is required")
    with tempfile.TemporaryDirectory(prefix="screenshot-storage-") as scratch:
        path = Path(scratch)
        unit = path / "test.cpp"
        unit.write_text(
            """#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#define SHOT_HAVE_FS 1
static constexpr uint32_t kMinFreeBytes = 600u * 1024u;
static bool s_streaming = false, s_capturing = false, s_failed = false, s_ready = false;
static uint32_t s_armedAtMs = 0;
static char s_lastPath[32] = {};
static int writes = 0, removals = 0;
static bool writeResult = true;
uint32_t millis() { return 0; }
void streamSlice() {}
void pruneShots() {}
bool writeBmp(const char *) { ++writes; return writeResult; }
struct Storage {
    uint32_t total = 0, used = 0;
    uint32_t totalBytes() { return total; }
    uint32_t usedBytes() { return used; }
    bool mkdir(const char *) { return true; }
    bool exists(const char *) { return false; }
    bool remove(const char *) { ++removals; return true; }
} FSCom;
"""
            + service
            + """
void expectBlocked(uint32_t total, uint32_t used) {
    FSCom.total = total; FSCom.used = used;
    s_ready = true; s_failed = false;
    strcpy(s_lastPath, "/shots/old.bmp");
    const int before = writes;
    tdeck_shot_service();
    assert(s_failed && !s_ready && !s_lastPath[0]);
    assert(writes == before);
}
int main() {
    expectBlocked(0, 0);
    expectBlocked(1000000, 1000000);
    expectBlocked(1000000, 1000001);
    expectBlocked(1000000, 1000000 - kMinFreeBytes + 1);
    FSCom.total = 1000000; FSCom.used = 1000000 - kMinFreeBytes;
    s_ready = true;
    tdeck_shot_service();
    assert(writes == 1 && !s_failed && !strcmp(s_lastPath, "/shots/shot001.bmp"));
    s_ready = true; writeResult = false;
    tdeck_shot_service();
    assert(writes == 2 && s_failed && removals == 1);
    puts("Screenshot storage: unavailable, full, invalid capacity, reserve boundary and write failure passed");
}
""",
            encoding="utf-8",
        )
        executable = path / "test"
        subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", str(unit), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
