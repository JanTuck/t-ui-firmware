#!/usr/bin/env python3
"""Exercise production mount recovery and Arduino LittleFS/FS/VFS with an IDF state model."""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from test_safe_file_esp32 import prepare_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arduino-core",
        type=Path,
        default=Path.home() / ".platformio/packages/framework-arduinoespressif32",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which("g++") or shutil.which("clang++")
    sdk = args.arduino_core / "libraries/FS/src"
    littlefs = args.arduino_core / "libraries/LittleFS/src"
    if not compiler or not (littlefs / "LittleFS.cpp").is_file():
        raise SystemExit("A C++ compiler and cached Arduino ESP32 core are required")
    source = (root / "src/FSCommon.cpp").read_text()
    start = source.rfind("#if defined(ARCH_ESP32)", 0, source.index("static bool fsBootStorageAvailable"))
    end = source.index("\n}", source.index("void fsInit()")) + 2
    helper = source[start:end]
    database_source = (root / "src/mesh/NodeDB.cpp").read_text()
    start = database_source.index("bool NodeDB::saveToDisk(int saveWhat)")
    database_save = database_source[start:database_source.index("\n}", start) + 2]
    with tempfile.TemporaryDirectory(prefix="littlefs-mount-") as scratch:
        path = Path(scratch)
        prepare_sources(path, root, sdk)
        for name in ("LittleFS.h", "LittleFS.cpp"):
            shutil.copyfile(littlefs / name, path / name)
        (path / "sdkconfig.h").write_text("#pragma once\n#define CONFIG_LITTLEFS_PAGE_SIZE 256\n#define CONFIG_LOG_DEFAULT_LEVEL 0\n")
        with (path / "Arduino.h").open("a") as file:
            file.write("\ninline bool disableCore0WDT() { return false; }\ninline void enableCore0WDT() {}\nvoid delay(unsigned long);\n")
        with (path / "configuration.h").open("a") as file:
            file.write("\n#define LOG_WARN(...) ((void)0)\n#define LOG_INFO(...) ((void)0)\n")
        (path / "esp_littlefs.h").write_text(r'''#pragma once
#include <stddef.h>
typedef int esp_err_t;
typedef int esp_log_level_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_INVALID_STATE 0x103
#define ESP_ERR_NO_MEM 0x101
#define ESP_LOG_NONE 0
typedef struct {
    const char *base_path;
    const char *partition_label;
    const void *partition;
    bool format_if_mount_failed;
    bool read_only;
    bool dont_mount;
    bool grow_on_mount;
} esp_vfs_littlefs_conf_t;
bool esp_littlefs_mounted(const char *);
esp_err_t esp_vfs_littlefs_register(const esp_vfs_littlefs_conf_t *);
esp_err_t esp_vfs_littlefs_unregister(const char *);
esp_err_t esp_littlefs_format(const char *);
esp_err_t esp_littlefs_info(const char *, size_t *, size_t *);
void esp_log_level_set(const char *, esp_log_level_t);
''')
        (path / "FSCommon.h").write_text(r'''#pragma once
#include "LittleFS.h"
extern std::string mountBase;
class HostLittleFS : public fs::LittleFSFS {
public:
    bool begin(bool formatOnFail) { return LittleFSFS::begin(formatOnFail, mountBase.c_str()); }
};
extern HostLittleFS filesystem;
#define FSCom filesystem
#define FSBegin() filesystem.begin(true)
#define FILE_O_READ "r"
#define FILE_O_WRITE "w"
bool renameFile(const char *, const char *);
bool fsEnsureMounted();
void fsInit();
void resetBootState();
''')
        (path / "SPILock.h").write_text(r'''#pragma once
#include <cassert>
struct TestLock {
    int depth = 0;
    void lock() { assert(depth == 0); ++depth; }
    void unlock() { assert(depth > 0); --depth; }
};
extern TestLock *spiLock;
namespace concurrency {
struct LockGuard {
    TestLock *lock;
    explicit LockGuard(TestLock *value) : lock(value) { lock->lock(); }
    ~LockGuard() { lock->unlock(); }
};
}
''')
        (path / "mount.cpp").write_text(
            '#include "FSCommon.h"\n#include "configuration.h"\n#include "SPILock.h"\n'
            'void preFSBegin() {}\nvoid listDir(const char *, int) {}\n'
            + helper + '\nvoid resetBootState() { fsBootStorageAvailable = true; }\n'
        )
        (path / "NodeDBTest.h").write_text(r'''#pragma once
#include "SafeFile.h"
#include <atomic>
class NodeDB {
public:
    std::atomic<SettingsSaveError> lastSaveError{SettingsSaveError::None};
    bool saveToDisk(int);
    bool saveToDiskNoRetry(int) {
        SafeFile file("/prefs/uiconfig.proto", false);
        if (file.error() != SettingsSaveError::None) {
            lastSaveError.store(file.error());
            return false;
        }
        return file.write(uint8_t('x')) == 1 && file.close();
    }
};
''')
        (path / "database.cpp").write_text(r'''#include "NodeDBTest.h"
constexpr int SEGMENT_CONFIG = 1, SEGMENT_MODULECONFIG = 2, SEGMENT_DEVICESTATE = 4,
              SEGMENT_CHANNELS = 8, SEGMENT_NODEDATABASE = 16;
bool powerHAL_isPowerLevelSafe() { return true; }
bool filesystemStillReadable() { return false; }
bool fsFormat() { return filesystem.format(); }
#define RECORD_CRITICALERROR(...) ((void)0)
''' + database_save)
        (path / "test.cpp").write_text(r'''#include "SafeFile.h"
#include "NodeDBTest.h"
extern "C" {
#include "esp_littlefs.h"
}
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iterator>
TestLock lock;
TestLock *spiLock = &lock;
std::string mountBase;
HostLittleFS filesystem;
bool backendMounted = false;
int registerError = ESP_OK, unregisterError = ESP_OK;
unsigned registerCalls = 0, unregisterCalls = 0, formatCalls = 0;
unsigned failuresRemaining = 0, retryDelays = 0, saveRetryDelays = 0;
void delay(unsigned long milliseconds) {
    assert(milliseconds == 50 || milliseconds == 150);
    if (milliseconds == 50) ++retryDelays; else ++saveRetryDelays;
}
extern "C" bool esp_littlefs_mounted(const char *) { return backendMounted; }
extern "C" esp_err_t esp_vfs_littlefs_register(const esp_vfs_littlefs_conf_t *config) {
    assert(lock.depth > 0);
    assert(!config->format_if_mount_failed && !config->read_only && !config->dont_mount);
    ++registerCalls;
    if (failuresRemaining > 0) { --failuresRemaining; return ESP_ERR_NO_MEM; }
    if (registerError != ESP_OK) return registerError;
    if (backendMounted) return ESP_ERR_INVALID_STATE;
    backendMounted = true;
    return ESP_OK;
}
extern "C" esp_err_t esp_vfs_littlefs_unregister(const char *) {
    assert(lock.depth > 0);
    ++unregisterCalls;
    if (unregisterError != ESP_OK) return unregisterError;
    backendMounted = false;
    return ESP_OK;
}
extern "C" esp_err_t esp_littlefs_format(const char *) {
    assert(lock.depth > 0);
    ++formatCalls;
    return ESP_OK;
}
extern "C" esp_err_t esp_littlefs_info(const char *, size_t *total, size_t *used) {
    *total = 1024 * 1024;
    *used = 128;
    return ESP_OK;
}
extern "C" void esp_log_level_set(const char *, esp_log_level_t) {}
bool renameFile(const char *from, const char *to) { return filesystem.rename(from, to); }
std::string readFile(const std::filesystem::path &path) {
    std::ifstream input(path);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}
void save(const char *filename, const char *payload, bool atomic = true) {
    SafeFile file(filename, atomic);
    assert(file.error() == SettingsSaveError::None);
    assert(file.write(reinterpret_cast<const uint8_t *>(payload), strlen(payload)) == strlen(payload));
    assert(file.close());
    assert(lock.depth == 0);
}
void unmount() {
    concurrency::LockGuard guard(spiLock);
    filesystem.end();
    assert(!filesystem.mountpoint() && !backendMounted);
}
int main(int argc, char **argv) {
    assert(argc == 2);
    mountBase = argv[1];
    const std::filesystem::path base(mountBase);
    std::filesystem::create_directory(base / "prefs");
    const auto original = base / "prefs/uiconfig.proto";
    const auto temporary = base / "prefs/uiconfig.proto.tmp";
    std::ofstream(original) << "COMMITTED";

    registerError = ESP_ERR_NO_MEM;
    {
        concurrency::LockGuard guard(spiLock);
        assert(!filesystem.begin(false));
    }
    assert(!filesystem.mountpoint() && !backendMounted);
    registerError = ESP_OK;
    save("/prefs/uiconfig.proto", "RECOVERED");
    assert(readFile(original) == "RECOVERED" && formatCalls == 0);
    puts("PASS: failed initial mount recovers and commits through actual LittleFS/FS/VFS/SafeFile");

    const unsigned registered = registerCalls, unregistered = unregisterCalls;
    save("/prefs/uiconfig.proto", "FAST PATH");
    assert(registerCalls == registered && unregisterCalls == unregistered && formatCalls == 0);
    puts("PASS: mounted save performs no mount, unmount or format operations");

    unmount();
    std::ofstream(temporary) << "INTERRUPTED";
    registerError = ESP_FAIL;
    for (bool atomic : {true, false}) {
        SafeFile file("/prefs/uiconfig.proto", atomic);
        assert(file.error() == SettingsSaveError::MountUnavailable);
        assert(file.write(uint8_t('x')) == 0 && !file.close());
        assert(readFile(original) == "FAST PATH" && readFile(temporary) == "INTERRUPTED");
    }
    assert(formatCalls == 0 && !filesystem.mountpoint());
    NodeDB database;
    assert(!database.saveToDisk(1));
    assert(database.lastSaveError.load() == SettingsSaveError::MountUnavailable);
    assert(saveRetryDelays == 2 && formatCalls == 0);
    assert(readFile(original) == "FAST PATH" && readFile(temporary) == "INTERRUPTED");
    puts("PASS: persistent mount failure preserves committed and temporary files, including non-atomic saves");
    puts("PASS: actual NodeDB save retry/fallback body does not format unavailable storage");

    registerError = ESP_OK;
    backendMounted = true;
    {
        concurrency::LockGuard guard(spiLock);
        assert(filesystem.begin(false));
    }
    assert(!filesystem.mountpoint());
    const unsigned beforeRebind = unregisterCalls;
    save("/prefs/uiconfig.proto", "REBOUND");
    assert(filesystem.mountpoint() && backendMounted && unregisterCalls == beforeRebind + 1);
    assert(readFile(original) == "REBOUND" && !std::filesystem::exists(temporary) && formatCalls == 0);
    puts("PASS: actual SDK already-mounted success leaves wrapper detached; production helper rebinds without format");

    unmount();
    backendMounted = true;
    unregisterError = ESP_FAIL;
    {
        SafeFile file("/prefs/uiconfig.proto", false);
        assert(file.error() == SettingsSaveError::MountUnavailable && !file.close());
    }
    assert(!filesystem.mountpoint() && readFile(original) == "REBOUND" && formatCalls == 0);
    unregisterError = ESP_OK;
    save("/new/nested/config.proto", "NEW PARENT");
    assert(readFile(base / "new/nested/config.proto") == "NEW PARENT");
    assert(readFile(original) == "REBOUND" && formatCalls == 0);
    puts("PASS: failed detach preserves data; later recovery creates missing parent directories");

    unmount();
    {
        concurrency::LockGuard guard(spiLock);
        assert(filesystem.format());
    }
    assert(!filesystem.mountpoint() && !backendMounted && formatCalls == 1);
    puts("PASS: formatting an unmounted backend does not mount or attach the Arduino wrapper");
    save("/prefs/uiconfig.proto", "FINAL");
    assert(readFile(original) == "FINAL" && formatCalls == 1);
    assert(lock.depth == 0);

    unmount();
    resetBootState();
    failuresRemaining = 1;
    const unsigned beforeBootRegisters = registerCalls, beforeBootFormats = formatCalls;
    const unsigned beforeBootDelay = retryDelays;
    fsInit();
    assert(filesystem.mountpoint() && registerCalls == beforeBootRegisters + 2);
    assert(retryDelays == beforeBootDelay + 1 && formatCalls == beforeBootFormats);
    assert(readFile(original) == "FINAL");
    save("/prefs/uiconfig.proto", "BOOT RECOVERED");
    puts("PASS: actual fsInit retries a transient boot mount before preferences load without formatting");

    unmount();
    resetBootState();
    registerError = ESP_ERR_NO_MEM;
    const unsigned beforeFailedBoot = registerCalls, beforeFailedBootDelay = retryDelays;
    fsInit();
    assert(!filesystem.mountpoint() && registerCalls == beforeFailedBoot + 3);
    assert(retryDelays == beforeFailedBootDelay + 2 && formatCalls == beforeBootFormats);
    registerError = ESP_OK;
    const unsigned beforeBlockedSave = registerCalls;
    {
        SafeFile file("/prefs/uiconfig.proto", false);
        assert(file.error() == SettingsSaveError::MountUnavailable && !file.close());
    }
    assert(registerCalls == beforeBlockedSave && readFile(original) == "BOOT RECOVERED");
    {
        concurrency::LockGuard guard(spiLock);
        assert(filesystem.begin(false));
    }
    {
        SafeFile file("/prefs/uiconfig.proto", false);
        assert(file.error() == SettingsSaveError::MountUnavailable && !file.close());
    }
    assert(readFile(original) == "BOOT RECOVERED" && formatCalls == beforeBootFormats);
    assert(!database.saveToDisk(1));
    assert(database.lastSaveError.load() == SettingsSaveError::MountUnavailable);
    assert(readFile(original) == "BOOT RECOVERED" && formatCalls == beforeBootFormats);
    puts("PASS: exhausted boot retries lock out writes, even after external remount, preserving unread preferences");

    unmount();
    resetBootState();
    backendMounted = true;
    const unsigned beforeBootRebind = unregisterCalls;
    fsInit();
    assert(filesystem.mountpoint() && unregisterCalls == beforeBootRebind + 1);
    save("/prefs/uiconfig.proto", "REBOOT REBOUND");
    assert(readFile(original) == "REBOOT REBOUND" && formatCalls == beforeBootFormats);
    puts("PASS: new boot resets lockout and rebinds an already-mounted backend without formatting");
}
''')
        executable = path / "test"
        subprocess.run(
            [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-DARCH_ESP32", f"-I{path}",
             *(str(path / name) for name in ("test.cpp", "mount.cpp", "database.cpp", "SafeFile.cpp", "FS.cpp", "vfs_api.cpp", "LittleFS.cpp")),
             "-o", str(executable)],
            check=True,
        )
        storage = path / "storage"
        storage.mkdir()
        subprocess.run([str(executable), str(storage)], check=True)
    print("Actual Arduino mount transitions passed; IDF mount results are injected, flash/FreeRTOS are not emulated")


if __name__ == "__main__":
    main()
