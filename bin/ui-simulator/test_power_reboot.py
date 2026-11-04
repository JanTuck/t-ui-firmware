#!/usr/bin/env python3
"""Run production power reboot dispatch with a virtual clock and simulated ESP restart."""

from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        raise SystemExit("A C++ compiler is required")
    source = (root / "src/Power.cpp").read_text(encoding="utf-8")

    def function(signature):
        start = source.index(signature)
        return source[start:source.index("\n}", start) + 2]

    production = function("void Power::powerCommandsCheck()") + "\n" + function("void Power::reboot()")
    fixture = r'''
#include "UptimeClock.h"
#include "Throttle.h"
#include <cassert>
#include <cstdio>
#include <cstdint>
#include <initializer_list>
#define LOG_INFO(...) ((void)0)
uint32_t millis() { return 0; }
uint32_t rebootAtMsec = 0, shutdownAtMsec = 0;
struct Restarted {};
unsigned rebootNotifications = 0, waypointSaves = 0, restarts = 0, shutdowns = 0;
struct RebootObservable {
    void notifyObservers(void *) { ++rebootNotifications; }
} notifyReboot;
struct WaypointStore {
    void saveToFlash() { ++waypointSaves; }
} waypointStore;
struct Esp {
    [[noreturn]] void restart() {
        assert(rebootNotifications == restarts + 1);
        assert(waypointSaves == restarts + 1);
        ++restarts;
        throw Restarted{};
    }
} ESP;
class Power {
public:
    void powerCommandsCheck();
    void reboot();
    void shutdown() { ++shutdowns; }
};
'''
    checks = r'''
void checkAt(Power &power, uint32_t now, bool expectedRestart) {
    Time::setTestMillis(now);
    const unsigned before = restarts;
    bool restarted = false;
    try { power.powerCommandsCheck(); }
    catch (const Restarted &) { restarted = true; }
    assert(restarted == expectedRestart);
    assert(restarts == before + (expectedRestart ? 1u : 0u));
    assert(rebootNotifications == restarts && waypointSaves == restarts);
}
int main() {
    Power power;
    for (uint32_t now : {0u, 1u, 1000u, UINT32_MAX}) checkAt(power, now, false);
    puts("PASS: unarmed reboot does not restart, including at clock wrap");

    Time::setTestMillis(1000);
    rebootAtMsec = Time::timerEndsAtMillis(5000);
    checkAt(power, 1000, false);
    checkAt(power, 5999, false);
    checkAt(power, 6000, true);
    rebootAtMsec = 0;
    checkAt(power, 6001, false);
    puts("PASS: scheduled reboot reaches ESP.restart exactly at its deadline after reboot hooks");

    Time::setTestMillis(7000);
    rebootAtMsec = Time::timerEndsAtMillis(5000);
    rebootAtMsec = 0;
    checkAt(power, 12000, false);
    puts("PASS: cancelled reboot does not restart at the former deadline");

    Time::setTestMillis(UINT32_MAX - 2000);
    rebootAtMsec = Time::timerEndsAtMillis(5000);
    assert(rebootAtMsec == 2999);
    checkAt(power, UINT32_MAX - 2000, false);
    checkAt(power, UINT32_MAX, false);
    checkAt(power, 0, false);
    checkAt(power, 2998, false);
    checkAt(power, 2999, true);
    puts("PASS: reboot countdown crosses the 32-bit wrap without firing early");

    Time::setTestMillis(UINT32_MAX);
    rebootAtMsec = Time::timerEndsAtMillis(1);
    assert(rebootAtMsec == 1);
    checkAt(power, 0, false);
    checkAt(power, 1, true);
    puts("PASS: deadline landing on zero remains armed and fires one millisecond later");

    Time::setTestMillis(200);
    rebootAtMsec = Time::timerEndsAtMillis(0);
    checkAt(power, 200, true);
    Time::setTestMillis(500);
    rebootAtMsec = Time::timerEndsAtMillis(20);
    checkAt(power, 600, true);
    assert(shutdowns == 0);
    puts("PASS: immediate and overdue reboot requests reach the physical restart boundary");
}
'''
    with tempfile.TemporaryDirectory(prefix="power-reboot-") as scratch:
        path = Path(scratch)
        (path / "Arduino.h").write_text("#pragma once\n#include <cstdint>\nuint32_t millis();\n")
        (path / "test.cpp").write_text(fixture + production + checks)
        executable = path / "test"
        subprocess.run(
            [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-DARCH_ESP32", "-DPIO_UNIT_TESTING",
             f"-I{path}", f"-I{root / 'src'}", f"-I{root / 'src/mesh'}", str(path / "test.cpp"),
             str(root / "src/UptimeClock.cpp"), str(root / "src/mesh/Throttle.cpp"), "-o", str(executable)],
            check=True,
        )
        subprocess.run([str(executable)], check=True)
    print("Production Power/Time/Throttle reboot dispatch passed; ESP.restart is simulated, no hardware was restarted")


if __name__ == "__main__":
    main()
