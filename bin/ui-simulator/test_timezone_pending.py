"""Run the real timezone bridge with a producer interleaving at pending-value consumption."""
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / "src/TDeckTimeZone.cpp").read_text(encoding="utf-8")
source = re.sub(r'^#include "[^\n]+"\n', '', source, flags=re.M)
consume = re.search(r'    (?:const )?int idx = s_tdeckTzPending[^;]*;', source)
assert consume, "Timezone consume statement changed"
source = source[:consume.end()] + '\n    if (injectChoice) { injectChoice = false; tdeck_tz_set(9); }' + source[consume.end():]
fixture = r'''
#include <cassert>
#include <cstring>
#include <string>
#include <vector>
#define LOG_INFO(...) ((void)0)
constexpr int SEGMENT_CONFIG = 1;
struct { struct { char tzdef[64] = {}; } device; } config;
void *nodeDB = &config;
bool injectChoice = false;
std::vector<std::string> saved;
bool tdeck_save_settings(int) { saved.emplace_back(config.device.tzdef); return true; }
'''
checks = r'''
int main() {
    tdeck_tz_service(); assert(saved.empty());
    tdeck_tz_set(0); injectChoice = true;
    tdeck_tz_service(); assert(saved.size() == 1 && saved.back() == "PST8PDT,M3.2.0,M11.1.0");
    tdeck_tz_service(); assert(saved.size() == 2 && saved.back() == "CET-1CEST,M3.5.0,M10.5.0/3");
    tdeck_tz_service(); assert(saved.size() == 2);
    tdeck_tz_set(1); tdeck_tz_set(2); tdeck_tz_set(7);
    tdeck_tz_service(); assert(saved.size() == 3 && saved.back() == "GMT0");
    tdeck_tz_set(-1); tdeck_tz_set(10); tdeck_tz_service(); assert(saved.size() == 3);
}
'''
with tempfile.TemporaryDirectory(prefix="tui-timezone-") as directory:
    path = Path(directory)
    (path / "test.cpp").write_text(fixture + source + checks)
    subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(path / "test.cpp"), "-o", str(path / "test")], check=True)
    subprocess.run([str(path / "test")], check=True)
print("Timezone: concurrent choice retained, latest rapid choice saved, idle and invalid choices do not write")
