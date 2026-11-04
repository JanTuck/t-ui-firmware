"""Run actual Files copy/delete functions against deterministic storage failures."""

from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / "lib/meshtastic-device-ui/source/graphics/TFT/TFTView_320x240.cpp").read_text()


def extract(signature):
    start = source.index(signature)
    return source[start : source.index("\n}", start) + 2]


fixture = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#define HAS_SDCARD 1
#define MALLOC_CAP_SPIRAM 0
#define _(text) text
void *heap_caps_malloc(size_t n, int) { return malloc(n); }
void heap_caps_free(void *p) { free(p); }
static std::map<std::string, std::string> disk;
static std::vector<std::string> removals;
static int readLimit = -1;
static bool readError = false, shortWrite = false, removeError = false, treeError = false, growOnRead = false;
static bool openWriteError = false, openReadError = false, renameError = false, corruptWrite = false;
static int writes = 0;
static std::string key(bool sd, const char *path) { return (sd ? "S:" : "F:") + std::string(path); }
bool volExists(bool sd, const char *path) { return disk.count(key(sd, path)); }
bool volRemove(bool sd, const char *path) {
    removals.push_back(key(sd, path));
    return !removeError && disk.erase(key(sd, path));
}
#define O_RDONLY 0
struct MockFile {
    std::string path, cursor;
    explicit operator bool() const { return disk.count(path); }
    bool isDirectory() const { return disk.count(path) && disk.at(path) == "<directory>"; }
    MockFile openNextFile() {
        for (const auto &entry : disk) {
            std::string prefix = path + "/";
            if (entry.first > cursor && entry.first.compare(0, prefix.size(), prefix) == 0 &&
                entry.first.find('/', prefix.size()) == std::string::npos) {
                cursor = entry.first; return MockFile{entry.first, ""};
            }
        }
        return MockFile{};
    }
    const char *name() const { return path.c_str() + path.rfind('/') + 1; }
    size_t getName(char *out, size_t cap) const {
        snprintf(out, cap, "%s", name()); return strlen(out);
    }
    void close() {}
};
using FsFile = MockFile;
namespace fs { using File = MockFile; }
struct MockFS {
    bool sd;
    MockFile open(const char *path, int = 0) { return treeError ? MockFile{} : MockFile{key(sd, path), ""}; }
    bool rmdir(const char *path) {
        auto dir = open(path);
        return dir.isDirectory() && !dir.openNextFile() && volRemove(sd, path);
    }
};
static MockFS SDFs{true}, fileSystem{false};
bool volRemoveTree(bool sd, const char *path, int depth);
bool volMkdir(bool sd, const char *path) { disk[key(sd, path)] = ""; return true; }
bool volRename(bool sd, const char *from, const char *to) {
    assert(disk[key(sd, (std::string(to) + ".where").c_str())] == from);
    if (renameError) return false;
    auto it = disk.find(key(sd, from));
    if (it == disk.end() || disk.count(key(sd, to))) return false;
    disk[key(sd, to)] = it->second; disk.erase(it); return true;
}
void trashNotePath(char *out, size_t cap, const char *name) { snprintf(out, cap, "/.trash/%s.where", name); }
struct VolFile {
    std::string path;
    size_t pos = 0;
    bool openRead(bool sd, const char *name) { path = key(sd, name); return !openReadError && disk.count(path); }
    bool openWrite(bool sd, const char *name) {
        path = key(sd, name); if (openWriteError) return false;
        disk[path] = ""; ++writes; return true;
    }
    uint64_t size() { return disk[path].size(); }
    int read(uint8_t *out, size_t cap) {
        if (growOnRead && pos == 0) disk[path] += "unexpected growth";
        if (readLimit >= 0 && pos >= (size_t)readLimit) return readError ? -1 : 0;
        size_t n = std::min(cap, disk[path].size() - pos);
        if (readLimit >= 0) n = std::min(n, (size_t)readLimit - pos);
        memcpy(out, disk[path].data() + pos, n); pos += n; return n;
    }
    int write(const uint8_t *in, size_t n) {
        if (shortWrite && n) --n;
        disk[path].append(reinterpret_cast<const char *>(in), n);
        if (corruptWrite && n) disk[path][0] ^= 1;
        return n;
    }
    void close() {}
};
struct TFTView_320x240 {
    enum FilesVol { VOL_ROOT, VOL_SD, VOL_FLASH, VOL_TRASH };
    FilesVol filesVol = VOL_FLASH, copySrcVol = VOL_SD;
    char filesPath[192] = "/", copySrcPath[256] = "/sample.txt", filesSelName[64] = "";
    char filesNames[64][64] = {};
    bool filesCopyArmed = true, filesSelIsDir = false, filesFreeKnown[2] = {true, true};
    uint64_t actualFree = 100000, cachedFree = 100000;
    int refreshes = 0, capacityReads = 0, actionUpdates = 0;
    std::string alert;
    uint64_t filesFreeBytes(bool sd) {
        if (!filesFreeKnown[sd ? 0 : 1]) { ++capacityReads; cachedFree = actualFree; filesFreeKnown[sd ? 0 : 1] = true; }
        return cachedFree;
    }
    void filesRefresh() { ++refreshes; }
    void filesUpdateActionBar() { ++actionUpdates; }
    void messageAlert(const char *text, bool) { alert = text; }
    void filesCopyNow();
    void filesDeleteForever();
    void filesTrashSelected();
};
'''
fixture += extract("void joinPath(") + "\n"
fixture += extract("bool filesNameFits(") + "\n"
fixture += extract("bool volRemoveTree(") + "\n"
fixture += extract("bool writeTrashNote(") + "\n"
fixture += extract("void TFTView_320x240::filesCopyNow(") + "\n"
fixture += extract("void TFTView_320x240::filesDeleteForever(") + "\n"
fixture += extract("void TFTView_320x240::filesTrashSelected(") + "\n"
fixture += r'''
static TFTView_320x240 reset() {
    disk = {{"S:/sample.txt", std::string(9000, 'x')}};
    removals.clear(); readLimit = -1;
    readError = shortWrite = removeError = treeError = growOnRead = false; writes = 0;
    openWriteError = openReadError = renameError = corruptWrite = false;
    return TFTView_320x240{};
}
int main() {
    for (bool error : {false, true}) {
        auto app = reset(); readLimit = 4100; readError = error;
        app.filesCopyNow();
        assert(app.filesCopyArmed && !disk.count("F:/sample.txt"));
        assert(app.alert == "Copy failed" && !app.refreshes && app.capacityReads == 1);
    }
    {
        auto app = reset(); shortWrite = true; app.filesCopyNow();
        assert(app.filesCopyArmed && !disk.count("F:/sample.txt") && app.alert == "Copy failed");
    }
    {
        auto app = reset(); growOnRead = true; app.filesCopyNow();
        assert(app.filesCopyArmed && !disk.count("F:/sample.txt") && app.alert == "Copy failed");
    }
    {
        auto app = reset(); readLimit = 100; removeError = true; app.filesCopyNow();
        assert(app.filesCopyArmed && disk.count("F:/sample.txt"));
        assert(app.alert == "Copy failed; incomplete file remains" && !app.filesFreeKnown[1]);
    }
    {
        auto app = reset(); app.filesCopyNow();
        assert(!app.filesCopyArmed && !app.copySrcPath[0] && app.refreshes == 1);
        assert(disk["F:/sample.txt"] == disk["S:/sample.txt"] && !app.filesFreeKnown[1]);
    }
    {
        auto app = reset(); disk["S:/sample.txt"] = ""; app.filesCopyNow();
        assert(!app.filesCopyArmed && disk.count("F:/sample.txt") && disk["F:/sample.txt"].empty());
    }
    {
        auto app = reset(); app.actualFree = 10000; app.filesCopyNow();
        assert(app.filesCopyArmed && app.alert == "Not enough space here" && writes == 0 && app.capacityReads == 1);
    }
    for (bool directory : {false, true}) {
        auto app = reset(); strcpy(app.filesSelName, "Fsample.txt"); app.filesSelIsDir = directory;
        disk["F:/.trash/sample.txt"] = "data"; disk["F:/.trash/sample.txt.where"] = "/original/sample.txt";
        removeError = !directory; treeError = directory; app.filesDeleteForever();
        assert(disk.count("F:/.trash/sample.txt.where") && disk.count("F:/.trash/sample.txt"));
        assert(app.alert == "Couldn't delete everything" && !app.refreshes && app.actionUpdates == 1);
        for (const auto &path : removals) assert(path != "F:/.trash/sample.txt.where");
    }
    {
        auto app = reset(); strcpy(app.filesSelName, "Fsample.txt");
        disk["F:/.trash/sample.txt"] = "data"; disk["F:/.trash/sample.txt.where"] = "/original/sample.txt";
        app.filesDeleteForever();
        assert(!disk.count("F:/.trash/sample.txt") && !disk.count("F:/.trash/sample.txt.where") && app.refreshes == 1);
    }
    assert(filesNameFits(std::string(63, 'a').c_str(), 64, false));
    assert(!filesNameFits(std::string(64, 'a').c_str(), 64, false));
    assert(filesNameFits(std::string(62, 'a').c_str(), 64, true));
    assert(!filesNameFits(std::string(63, 'a').c_str(), 64, true));
    assert(!filesNameFits("", 64, false));
    for (int failure = 0; failure < 6; ++failure) {
        auto app = reset(); strcpy(app.filesSelName, "sample.txt");
        app.copySrcVol = app.VOL_FLASH; disk["F:/sample.txt"] = "original data";
        openWriteError = failure == 0; shortWrite = failure == 1; renameError = failure == 2;
        openReadError = failure == 3; corruptWrite = failure == 4;
        if (failure == 5) readLimit = 4;
        app.filesTrashSelected();
        assert(disk["F:/sample.txt"] == "original data" && !disk.count("F:/.trash/sample.txt"));
        assert(!disk.count("F:/.trash/sample.txt.where"));
        assert(!app.refreshes && app.filesCopyArmed && !strcmp(app.copySrcPath, "/sample.txt"));
        assert(app.alert == (renameError ? "Couldn't move it to the trash" : "Couldn't save restore information"));
    }
    {
        reset(); disk["F:/.trash/existing.where"] = "existing restore information";
        assert(!writeTrashNote(false, "existing", "/new/location"));
        assert(disk["F:/.trash/existing.where"] == "existing restore information" && writes == 0 && removals.empty());
    }
    for (bool sd : {false, true}) {
        reset(); disk[key(sd, "/folder")] = "<directory>";
        disk[key(sd, "/folder/a")] = "a";
        disk[key(sd, "/folder/sub")] = "<directory>";
        disk[key(sd, "/folder/sub/b")] = "b";
        assert(volRemoveTree(sd, "/folder", 0) && !disk.count(key(sd, "/folder")));
        reset(); disk[key(sd, "/folder")] = "<directory>";
        for (int i = 0; i < 41; ++i) disk[key(sd, ("/folder/" + std::to_string(i)).c_str())] = "data";
        assert(!volRemoveTree(sd, "/folder", 0) && removals.empty());
        reset(); disk[key(sd, "/folder")] = "<directory>";
        disk[key(sd, ("/folder/" + std::string(39, 'a')).c_str())] = "prefix collision";
        disk[key(sd, ("/folder/" + std::string(40, 'a')).c_str())] = "long name";
        assert(!volRemoveTree(sd, "/folder", 0) && removals.empty());
        reset(); disk[key(sd, "/folder")] = "<directory>";
        disk[key(sd, "/folder/a")] = "data"; removeError = true;
        assert(!volRemoveTree(sd, "/folder", 0) && disk.count(key(sd, "/folder/a")));
        assert(!volRemoveTree(sd, "/", 0));
    }
    {
        auto app = reset(); strcpy(app.filesSelName, "foo.where");
        disk["F:/foo.where"] = "keep my data";
        app.filesTrashSelected();
        assert(disk["F:/.trash/foo.where~1"] == "keep my data");
        assert(disk["F:/.trash/foo.where~1.where"] == "/foo.where");
        strcpy(app.filesSelName, "foo"); disk["F:/foo"] = "another file";
        disk["F:/.trash/foo.where"] = "older file from legacy trash";
        app.filesTrashSelected();
        assert(disk["F:/.trash/foo.where"] == "older file from legacy trash");
        assert(disk["F:/.trash/foo~2"] == "another file");
        assert(disk["F:/.trash/foo~2.where"] == "/foo");
    }
    {
        auto app = reset();
        std::string original(63, 'a');
        strcpy(app.filesSelName, original.c_str()); disk["F:/" + original] = "data";
        app.filesTrashSelected();
        std::string name(62, 'a');
        assert(disk["F:/.trash/" + name] == "data");
        assert(disk["F:/.trash/" + name + ".where"] == "/" + original);
        assert(filesNameFits(name.c_str(), sizeof(app.filesNames[0]), true));
        disk["F:/" + original] = "second"; app.filesTrashSelected();
        std::string duplicate = std::string(59, 'a') + "~2";
        assert(disk["F:/.trash/" + duplicate] == "second");
        assert(disk["F:/.trash/" + duplicate + ".where"] == "/" + original);
        assert(filesNameFits(duplicate.c_str(), sizeof(app.filesNames[0]), true));
    }
    puts("Files storage: copy failures, capacity, delete metadata and name bounds passed");
}
'''

with tempfile.TemporaryDirectory(prefix="tui-files-") as directory:
    path = Path(directory)
    cpp = path / "files.cpp"
    cpp.write_text(fixture)
    exe = path / "files-test"
    subprocess.run([os.environ.get("CXX", "g++"), "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
