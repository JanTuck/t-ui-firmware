#!/usr/bin/env python3
"""Run production SafeFile and Arduino ESP32 FS/VFS code on a POSIX filesystem."""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arduino-core",
        type=Path,
        default=Path.home() / ".platformio/packages/framework-arduinoespressif32",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sdk = args.arduino_core / "libraries/FS/src"
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler or not (sdk / "vfs_api.cpp").is_file():
        raise SystemExit("A C++ compiler and cached Arduino ESP32 core are required")
    with tempfile.TemporaryDirectory(prefix="safe-file-esp32-") as scratch:
        path = Path(scratch)
        for name in ("SafeFile.h", "SafeFile.cpp", "SettingsSaveError.h"):
            shutil.copyfile(root / "src" / name, path / name)
        for name in ("FS.h", "FSImpl.h", "FS.cpp", "vfs_api.h", "vfs_api.cpp"):
            shutil.copyfile(sdk / name, path / name)
        (path / "Arduino.h").write_text(r'''#pragma once
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <string>
using boolean = bool;
class String : public std::string {
public:
    using std::string::string;
    String(const std::string &value) : std::string(value) {}
    bool startsWith(const char *value) const { return find(value) == 0; }
    bool endsWith(const char *value) const {
        const size_t n = strlen(value);
        return size() >= n && compare(size() - n, n, value) == 0;
    }
};
class Print {
public:
    virtual ~Print() = default;
    virtual size_t write(uint8_t) = 0;
    virtual size_t write(const uint8_t *, size_t) = 0;
};
class Stream : public Print {
protected:
    unsigned long _timeout = 0;
public:
    virtual int available() = 0;
    virtual int read() = 0;
    virtual int peek() = 0;
    virtual void flush() = 0;
};
inline const char *pathToFileName(const char *path) {
    const char *slash = strrchr(path, '/');
    return slash ? slash + 1 : path;
}
inline char *arduinoStrchr(const char *text, int character) {
    return const_cast<char *>(::strchr(text, character));
}
#define strchr arduinoStrchr
#define log_e(...) ((void)0)
#define log_w(...) ((void)0)
''')
        (path / "FSCommon.h").write_text('''#pragma once
#include "FS.h"
extern fs::FS filesystem;
#define FSCom filesystem
#define FILE_O_READ "r"
#define FILE_O_WRITE "w"
bool renameFile(const char *, const char *);
''')
        (path / "configuration.h").write_text('''#pragma once
#define LOG_DEBUG(...) ((void)0)
#define LOG_ERROR(...) ((void)0)
''')
        (path / "SPILock.h").write_text('''#pragma once
struct TestLock { void lock() {} void unlock() {} };
extern TestLock *spiLock;
namespace concurrency {
struct LockGuard { explicit LockGuard(TestLock *) {} };
}
''')
        (path / "test.cpp").write_text(r'''#include "SafeFile.h"
#include "vfs_api.h"
#include <cassert>
#include <cerrno>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <sys/resource.h>
#include <vector>
TestLock lock;
TestLock *spiLock = &lock;
auto implementation = std::make_shared<VFSImpl>();
fs::FS filesystem(implementation);
struct FailedOpen { std::string path; std::string mode; int error; };
std::vector<FailedOpen> failedOpens;
extern "C" FILE *__real_fopen(const char *, const char *);
extern "C" FILE *__wrap_fopen(const char *path, const char *mode) {
    FILE *file = __real_fopen(path, mode);
    if (!file) {
        const int error = errno;
        failedOpens.push_back({path, mode, error});
        errno = error;
    }
    return file;
}
bool renameFile(const char *from, const char *to) { return filesystem.rename(from, to); }
std::string readFile(const std::filesystem::path &path) {
    std::ifstream input(path);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}
void save(const char *payload) {
    SafeFile file("/prefs/config.proto", true);
    assert(file.error() == SettingsSaveError::None);
    assert(file.write(reinterpret_cast<const uint8_t *>(payload), strlen(payload)) == strlen(payload));
    assert(file.close());
}
int main(int argc, char **argv) {
    assert(argc == 2);
    const std::filesystem::path base(argv[1]);
    const std::string mount = base.string();
    implementation->mountpoint(mount.c_str());
    std::filesystem::create_directory(base / "prefs");
    const auto target = base / "prefs/config.proto";
    const auto temp = base / "prefs/config.proto.tmp";
    save("FIRST");
    assert(readFile(target) == "FIRST" && !std::filesystem::exists(temp));
    save("SECOND");
    assert(readFile(target) == "SECOND" && !std::filesystem::exists(temp));
    std::ofstream(temp) << "STALE BYTES";
    save("FRESH");
    assert(readFile(target) == "FRESH" && !std::filesystem::exists(temp));
    puts("PASS: fresh, replacement and stale regular temporary-file saves");

    std::filesystem::create_directory(temp);
    failedOpens.clear();
    SafeFile blocked("/prefs/config.proto", true);
    assert(blocked.error() == SettingsSaveError::Open);
    assert(blocked.write(uint8_t('x')) == 0 && !blocked.close());
    assert(readFile(target) == "FRESH" && std::filesystem::is_directory(temp));
    for (const auto &failure : failedOpens) assert(failure.mode != "w");
    std::filesystem::remove(temp);
    puts("PASS: stale directory reports Open before write-open; committed file survives");

    failedOpens.clear();
    SafeFile missing("/missing/config.proto", true);
    assert(missing.error() == SettingsSaveError::Open && !missing.close());
    assert(!failedOpens.empty() && failedOpens.back().error == ENOENT);
    assert(readFile(target) == "FRESH");
    puts("PASS: missing parent reproduces genuine fopen ENOENT");

    implementation->mountpoint(nullptr);
    failedOpens.clear();
    SafeFile unmounted("/prefs/config.proto", true);
    assert(unmounted.error() == SettingsSaveError::Open && !unmounted.close());
    assert(failedOpens.empty());
    implementation->mountpoint(mount.c_str());
    puts("PASS: unmounted filesystem reports Open without calling fopen");

    struct rlimit oldLimit, lowLimit;
    assert(getrlimit(RLIMIT_NOFILE, &oldLimit) == 0);
    lowLimit = oldLimit;
    lowLimit.rlim_cur = 32;
    assert(setrlimit(RLIMIT_NOFILE, &lowLimit) == 0);
    std::vector<int> descriptors;
    for (;;) {
        const int descriptor = open("/dev/null", O_RDONLY);
        if (descriptor < 0) break;
        descriptors.push_back(descriptor);
    }
    assert(errno == EMFILE);
    failedOpens.clear();
    SafeFile exhausted("/prefs/config.proto", true);
    const int observedErrno = errno;
    assert(exhausted.error() == SettingsSaveError::Open);
    bool writeFailedWithEmfile = false;
    for (const auto &failure : failedOpens)
        writeFailedWithEmfile |= failure.mode == "w" && failure.error == EMFILE;
    assert(writeFailedWithEmfile);
    assert(observedErrno == ENOENT);
    for (int descriptor : descriptors) close(descriptor);
    assert(setrlimit(RLIMIT_NOFILE, &oldLimit) == 0);
    assert(readFile(target) == "FRESH");
    save("RECOVERED");
    assert(readFile(target) == "RECOVERED");
    puts("PASS: actual descriptor exhaustion fails fopen with EMFILE; later stat masks errno as ENOENT; save recovers");
}
''')
        executable = path / "test"
        subprocess.run(
            [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", f"-I{path}",
             str(path / "test.cpp"), str(path / "SafeFile.cpp"), str(path / "FS.cpp"),
             str(path / "vfs_api.cpp"), "-Wl,--wrap=fopen", "-o", str(executable)],
            check=True,
        )
        storage = path / "storage"
        storage.mkdir()
        subprocess.run([str(executable), str(storage)], check=True)
    print("Actual Arduino FS/VFS host tests passed; ESP32 flash and FreeRTOS are not emulated")


if __name__ == "__main__":
    main()
