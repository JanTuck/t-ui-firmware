"""Exercise production SafeFile verification with unreliable file-size metadata."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / "src/SafeFile.cpp").read_text()
start = source.index("bool SafeFile::testReadback()")
body = source[start:source.index("\n}", start) + 2]
harness = r'''
#include <cassert>
#include "SettingsSaveError.h"
#include <cstdint>
#include <string>
#include <vector>
using String = std::string;
#define FILE_O_READ "r"
#define LOG_ERROR(...) ((void)0)
namespace concurrency { struct LockGuard { explicit LockGuard(void *) {} }; }
void *spiLock = nullptr;
struct File {
    std::vector<uint8_t> bytes;
    size_t metadataSize = 0, position = 0, failAfter = SIZE_MAX;
    bool opened = true;
    operator bool() const { return opened; }
    size_t size() const { return metadataSize; }
    int read() { return position < bytes.size() && position < failAfter ? bytes[position++] : -1; }
    void close() {}
};
struct Backend { File file; File open(const char *, const char *) { return file; } } FSCom;
struct SafeFile {
    String filename = "/prefs/config.proto";
    size_t expectedSize = 4;
    uint8_t hash = 1 ^ 2 ^ 3 ^ 4;
    SettingsSaveError lastError = SettingsSaveError::None;
    bool testReadback();
};
BODY
int main() {
    SafeFile file;
    FSCom.file.bytes = {1, 2, 3, 4};
    FSCom.file.metadataSize = 0;
    assert(file.testReadback());
    FSCom.file.metadataSize = 999;
    assert(file.testReadback());
    FSCom.file.metadataSize = 4;
    assert(file.testReadback());
    FSCom.file.bytes = {1, 2, 3, 5};
    assert(!file.testReadback());
    assert(file.lastError == SettingsSaveError::ReadbackHash);
    FSCom.file.bytes = {1, 2};
    file.hash = 1 ^ 2 ^ 7 ^ 7;
    assert(!file.testReadback());
    assert(file.lastError == SettingsSaveError::ReadbackLength);
    FSCom.file.bytes = {1, 2, 7, 7};
    FSCom.file.failAfter = 2;
    assert(!file.testReadback());
    FSCom.file.failAfter = SIZE_MAX;
    FSCom.file.bytes = {1, 2, 7, 7, 8, 8};
    assert(!file.testReadback());
    FSCom.file.opened = false;
    assert(!file.testReadback());
    assert(file.lastError == SettingsSaveError::ReadbackOpen);
    FSCom.file.opened = true;
    FSCom.file.bytes.clear();
    file.expectedSize = 0;
    file.hash = 0;
    assert(file.testReadback());
}
'''.replace("BODY", body)
with tempfile.TemporaryDirectory(prefix="safe-file-readback-") as directory:
    cpp = Path(directory) / "test.cpp"
    executable = Path(directory) / "test"
    cpp.write_text(harness)
    subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I" + str(root / "src"), str(cpp), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
print("SafeFile readback: unavailable metadata, exact length/hash, failed reads and opens passed")
