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
    state_start = source.index("#if defined(ARCH_ESP32)")
    state = source[state_start:source.index("#endif", state_start) + len("#endif")]
    format_start = source.index("bool fsFormat()")
    format_body = source[format_start:source.index("\n}", format_start) + 2]
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
#define ESP_ERR_NOT_FOUND 0x105
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
        (path / "esp_partition.h").write_text(r'''#pragma once
#include <cstdint>
typedef uint8_t esp_partition_type_t;
typedef uint8_t esp_partition_subtype_t;
constexpr uint8_t ESP_PARTITION_TYPE_APP = 0, ESP_PARTITION_TYPE_DATA = 1;
constexpr uint8_t ESP_PARTITION_SUBTYPE_DATA_NVS = 2, ESP_PARTITION_SUBTYPE_DATA_SPIFFS = 0x82,
                  ESP_PARTITION_SUBTYPE_DATA_LITTLEFS = 0x83, ESP_PARTITION_SUBTYPE_ANY = 0xff;
struct esp_partition_t {
    uint8_t type, subtype;
    char label[17];
    uint32_t address = 0x10000, size = 0x100000;
};
struct PartitionIterator;
typedef PartitionIterator *esp_partition_iterator_t;
const esp_partition_t *esp_partition_find_first(esp_partition_type_t, esp_partition_subtype_t, const char *);
esp_partition_iterator_t esp_partition_find(esp_partition_type_t, esp_partition_subtype_t, const char *);
const esp_partition_t *esp_partition_get(esp_partition_iterator_t);
esp_partition_iterator_t esp_partition_next(esp_partition_iterator_t);
void esp_partition_iterator_release(esp_partition_iterator_t);
''')
        (path / "FSCommon.h").write_text(r'''#pragma once
#include "LittleFS.h"
#include "SettingsSaveError.h"
extern std::string mountBase;
class HostLittleFS : public fs::LittleFSFS {
public:
    bool begin(bool formatOnFail, const char * = "/littlefs", uint8_t maxOpen = 10, const char *label = "spiffs") {
        return LittleFSFS::begin(formatOnFail, mountBase.c_str(), maxOpen, label);
    }
};
extern HostLittleFS filesystem;
#define FSCom filesystem
#define FSBegin() fsBegin()
#define FILE_O_READ "r"
#define FILE_O_WRITE "w"
bool renameFile(const char *, const char *);
bool fsEnsureMounted();
bool fsBegin();
bool fsFormat();
SettingsSaveError fsMountError();
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
            + state + '\n' + helper + '\n' + format_body
            + '\nvoid resetBootState() { fsBootStorageAvailable = true; fsStoragePartition = nullptr; '
            'fsStorageCanonical = false; fsMountFailure = SettingsSaveError::MountUnavailable; }\n'
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
#define RECORD_CRITICALERROR(...) ((void)0)
''' + database_save)
        (path / "test.cpp").write_text(r'''#include "SafeFile.h"
#include "NodeDBTest.h"
#include "esp_partition.h"
extern "C" {
#include "esp_littlefs.h"
}
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <vector>
TestLock lock;
TestLock *spiLock = &lock;
std::string mountBase;
HostLittleFS filesystem;
bool backendMounted = false;
std::string backendLabel = "spiffs", lastRegisteredLabel;
std::vector<esp_partition_t> partitions{{ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, "spiffs"}};
struct PartitionIterator { size_t index; uint8_t type, subtype; std::string label; };
unsigned liveIterators = 0;
bool matches(const esp_partition_t &p, uint8_t type, uint8_t subtype, const char *label) {
    return p.type == type && (subtype == ESP_PARTITION_SUBTYPE_ANY || p.subtype == subtype) &&
           (!label || strcmp(p.label, label) == 0);
}
const esp_partition_t *esp_partition_find_first(uint8_t type, uint8_t subtype, const char *label) {
    for (const auto &p : partitions) if (matches(p, type, subtype, label)) return &p;
    return nullptr;
}
esp_partition_iterator_t esp_partition_find(uint8_t type, uint8_t subtype, const char *label) {
    for (size_t i = 0; i < partitions.size(); ++i) {
        if (matches(partitions[i], type, subtype, label)) {
            ++liveIterators;
            return new PartitionIterator{i, type, subtype, label ? label : ""};
        }
    }
    return nullptr;
}
const esp_partition_t *esp_partition_get(esp_partition_iterator_t iterator) { return &partitions.at(iterator->index); }
void esp_partition_iterator_release(esp_partition_iterator_t iterator) {
    if (iterator) { assert(liveIterators > 0); --liveIterators; delete iterator; }
}
esp_partition_iterator_t esp_partition_next(esp_partition_iterator_t iterator) {
    while (++iterator->index < partitions.size()) {
        if (matches(partitions[iterator->index], iterator->type, iterator->subtype,
                    iterator->label.empty() ? nullptr : iterator->label.c_str())) return iterator;
    }
    esp_partition_iterator_release(iterator);
    return nullptr;
}
int registerError = ESP_OK, unregisterError = ESP_OK, lastRegistrationError = ESP_OK;
unsigned registerCalls = 0, unregisterCalls = 0, formatCalls = 0;
unsigned failuresRemaining = 0, retryDelays = 0, saveRetryDelays = 0;
void delay(unsigned long milliseconds) {
    assert(milliseconds == 50 || milliseconds == 150);
    if (milliseconds == 50) ++retryDelays; else ++saveRetryDelays;
}
extern "C" bool esp_littlefs_mounted(const char *label) { return backendMounted && label && backendLabel == label; }
extern "C" esp_err_t esp_vfs_littlefs_register(const esp_vfs_littlefs_conf_t *config) {
    assert(lock.depth > 0);
    assert(!config->format_if_mount_failed && !config->read_only && !config->dont_mount);
    ++registerCalls;
    lastRegisteredLabel = config->partition_label ? config->partition_label : "";
    const auto *partition = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_ANY, config->partition_label);
    if (!partition) return lastRegistrationError = ESP_ERR_NOT_FOUND;
    if (failuresRemaining > 0) { --failuresRemaining; return ESP_ERR_NO_MEM; }
    if (registerError != ESP_OK) return registerError;
    if (backendMounted) return ESP_ERR_INVALID_STATE;
    backendMounted = true;
    backendLabel = config->partition_label;
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

    auto layout = [&](std::initializer_list<esp_partition_t> entries) {
        if (filesystem.mountpoint() || backendMounted) unmount();
        resetBootState();
        partitions = entries;
        registerError = ESP_OK;
        backendLabel = "spiffs";
        lastRegisteredLabel.clear();
        assert(liveIterators == 0);
    };
    layout({{ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, "nvs"},
            {ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_LITTLEFS, "otherfs"},
            {ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, "spiffs"}});
    const unsigned beforeLayoutFormats = formatCalls;
    fsInit();
    assert(filesystem.mountpoint() && lastRegisteredLabel == "spiffs" && liveIterators == 0);
    save("/prefs/uiconfig.proto", "CANONICAL");
    assert(readFile(original) == "CANONICAL" && formatCalls == beforeLayoutFormats);
    puts("PASS: eligible canonical spiffs partition wins over other filesystem candidates");

    layout({{ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, "app"},
            {ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, "nvs"},
            {ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, "storage"}});
    {
        concurrency::LockGuard guard(spiLock);
        assert(!filesystem.begin(false));
    }
    assert(lastRegistrationError == 261 && !filesystem.mountpoint());
    fsInit();
    assert(filesystem.mountpoint() && lastRegisteredLabel == "storage" && liveIterators == 0);
    save("/prefs/uiconfig.proto", "RENAMED SPIFFS");
    {
        concurrency::LockGuard guard(spiLock);
        assert(!fsFormat());
    }
    assert(readFile(original) == "RENAMED SPIFFS" && formatCalls == beforeLayoutFormats);
    puts("PASS: raw SDK reproduces missing-spiffs error 261; unique renamed SPIFFS mounts and saves without formatting");

    layout({{ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, "spiffs"},
            {ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_LITTLEFS, "littlefs"}});
    fsInit();
    assert(filesystem.mountpoint() && lastRegisteredLabel == "littlefs" && liveIterators == 0);
    save("/prefs/uiconfig.proto", "RENAMED LITTLEFS");
    assert(readFile(original) == "RENAMED LITTLEFS" && formatCalls == beforeLayoutFormats);
    puts("PASS: unique LITTLEFS fallback ignores an unrelated NVS partition named spiffs");

    layout({{ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_LITTLEFS, "littlefs"}});
    registerError = ESP_FAIL;
    fsInit();
    assert(!filesystem.mountpoint() && fsMountError() == SettingsSaveError::MountUnavailable);
    assert(formatCalls == beforeLayoutFormats && liveIterators == 0);
    assert(!database.saveToDisk(1));
    assert(readFile(original) == "RENAMED LITTLEFS" && formatCalls == beforeLayoutFormats);
    puts("PASS: fallback registration ESP_FAIL never triggers boot or NodeDB formatting");

    auto expectLayoutRejection = [&]() {
        const unsigned registrations = registerCalls, delays = retryDelays;
        fsInit();
        assert(!filesystem.mountpoint() && fsMountError() == SettingsSaveError::FilesystemLayout);
        assert(registerCalls == registrations && retryDelays == delays && liveIterators == 0);
        SafeFile file("/prefs/uiconfig.proto", false);
        assert(file.error() == SettingsSaveError::FilesystemLayout && !file.close());
        assert(!database.saveToDisk(1));
        assert(database.lastSaveError.load() == SettingsSaveError::FilesystemLayout);
        assert(readFile(original) == "RENAMED LITTLEFS" && formatCalls == beforeLayoutFormats);
    };
    layout({{ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, "app"},
            {ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, "nvs"}});
    expectLayoutRejection();
    layout({{ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, "spiffs"}});
    expectLayoutRejection();
    puts("PASS: absent filesystem and wrong-subtype canonical label reject without mount, format or data deletion");

    layout({{ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, "first"},
            {ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_LITTLEFS, "second"}});
    expectLayoutRejection();
    puts("PASS: ambiguous filesystem partitions reject without guessing or leaking iterator state");

    layout({{ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, "spiffs"},
            {ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, "spiffs"}});
    expectLayoutRejection();
    layout({{ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, "storage"},
            {ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_SPIFFS, "storage"}});
    expectLayoutRejection();
    puts("PASS: duplicate labels resolving to NVS reject, preserving all stored data");
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
