#!/usr/bin/env python3
"""Exercise SDK bond storage and firmware boot cleanup with retained fake NVS.

This checks source-level persistence, not radio pairing or physical flash. The ESP32-S3
archive and release ELF independently use the asserted SEC=88/CCCD=16 byte layouts.
"""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def block(source, marker, declaration=False):
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end + int(declaration)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, default=Path("/sdk"))
    parser.add_argument("--baseline", default="265ae5783", help="revision with first-slot-only cleanup")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    nimble = args.sdk / "packages/framework-espidf/components/bt/host/nimble/nimble/nimble"
    compiled_headers = args.sdk / "packages/framework-arduinoespressif32-libs/esp32s3/include/bt/host/nimble/nimble/nimble"
    header = (compiled_headers / "host/include/host/ble_store.h").read_text()
    sdk = (nimble / "host/store/config/src/ble_store_nvs.c").read_text()
    firmware = (root / "src/nimble/NimbleBluetooth.cpp").read_text()
    types = "\n".join(block(header, "struct ble_store_value_" + name, True)
                      for name in ("sec", "cccd", "csfc", "local_irk", "rpa_rec"))
    types += "\n" + block(header, "union ble_store_value {", True)
    constants = "\n".join(re.findall(r"^#define BLE_STORE_OBJ_TYPE_.*$", header, re.M))
    constants += "\n" + "\n".join(re.findall(r"^#define NIMBLE_NVS_.*$", sdk, re.M))
    functions = []
    for name in ("get_nvs_key_string", "get_nvs_matching_index", "get_nvs_max_obj_value",
                 "get_expected_size_for_obj_type", "get_nvs_db_value", "get_nvs_db_attribute",
                 "ble_nvs_write_key_value", "ble_store_nvs_write", "populate_db_from_nvs", "ble_nvs_restore_sec_keys"):
        match = re.search(r"static (?:void|int|size_t)\s+" + name + r"\(", sdk)
        assert match, name
        functions.append(block(sdk, match.group()))
    baseline = subprocess.check_output(["git", "-c", "safe.directory=*", "show",
                                        args.baseline + ":src/nimble/NimbleBluetooth.cpp"], cwd=root, text=True)
    cleanup = block(firmware, "static void repairIncompatibleBleBonds()")
    old_cleanup = block(baseline, "static void purgeIncompatibleBleBonds()")
    source = "\n".join((PRELUDE, constants, types, BACKEND, *functions,
                         old_cleanup.replace("purgeIncompatibleBleBonds", "oldCleanup"), cleanup, TESTS))
    with tempfile.TemporaryDirectory(prefix="ble-bonds-") as directory:
        work = Path(directory)
        (work / "test.cpp").write_text(source)
        subprocess.run(["g++", "-std=c++17", "-O1", "-g", "-fsanitize=address,undefined",
                        "-fno-omit-frame-pointer", str(work / "test.cpp"), "-o", str(work / "test")], check=True)
        subprocess.run([str(work / "test")], check=True)


PRELUDE = r'''#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <set>
#include <string>
#include <vector>
#define MYNEWT_VAL(x) CONFIG_##x
#define CONFIG_BLE_STORE_MAX_BONDS 6
#define CONFIG_BLE_STORE_MAX_CCCDS 8
#define CONFIG_BLE_STORE_MAX_CSFCS 6
#define CONFIG_BLE_GATT_CSFC_SIZE 1
#define CONFIG_ENC_ADV_DATA 0
#define CONFIG_BLE_HOST_BASED_PRIVACY 0
#define BLE_HS_ESTORE_FAIL 100
#define BLE_HS_ESTORE_CAP 101
#define ESP_LOGE(...) ((void)0)
#define ESP_LOGD(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define BLE_HS_LOG(...) ((void)0)
#define LOG_WARN(...) ((void)0)
#define LOG_ERROR(...) ((void)0)
#define LOG_INFO(...) ((void)0)
typedef struct { uint8_t type; uint8_t val[6]; } ble_addr_t;
'''

BACKEND = r'''
static_assert(sizeof(ble_store_value_sec) == 88, "must match linked ESP32-S3 SEC layout");
static_assert(sizeof(ble_store_value_cccd) == 16, "must match linked ESP32-S3 CCCD layout");
using Blob = std::vector<uint8_t>;
using Namespace = std::map<std::string, Blob>;
static std::map<std::string, Namespace> flash;
struct Handle { std::string name; int mode; };
static std::map<int, Handle> handles;
using nvs_handle_t = int;
using esp_err_t = int;
enum { ESP_OK=0, ESP_ERR_NVS_NOT_FOUND=1, ESP_ERR_NVS_INVALID_LENGTH=2,
       ESP_FAIL=3, ESP_ERR_NVS_TYPE_MISMATCH=4, NVS_READWRITE=1, NVS_READONLY=0 };
static int nextHandle=1, restarts=0, erases=0, commits=0, writeOpens=0;
static bool failInit=false, failOpen=false, failRead=false, failSet=false, failCommit=false, failErase=false, failWriteOpen=false;
static std::set<std::string> wrongType;
static esp_err_t nvs_flash_init() { return failInit ? ESP_FAIL : ESP_OK; }
static esp_err_t nvs_open(const char *name, int mode, nvs_handle_t *out) {
    if (failOpen || (failWriteOpen && mode==NVS_READWRITE)) return ESP_FAIL;
    if (mode==NVS_READONLY && !flash.count(name)) return ESP_ERR_NVS_NOT_FOUND;
    if (mode==NVS_READWRITE) ++writeOpens;
    *out=nextHandle++; handles[*out]={name,mode}; flash[name]; return ESP_OK;
}
static esp_err_t nvs_get_blob(nvs_handle_t h, const char *key, void *out, size_t *size) {
    if (failRead) return ESP_FAIL;
    if (wrongType.count(key)) return ESP_ERR_NVS_TYPE_MISMATCH;
    const auto &data=flash.at(handles.at(h).name);
    const auto it=data.find(key);
    if (it==data.end()) return ESP_ERR_NVS_NOT_FOUND;
    size_t requested=*size; *size=it->second.size();
    if (!out) return ESP_OK;
    if (requested < *size) return ESP_ERR_NVS_INVALID_LENGTH;
    if (*size) std::memcpy(out, it->second.data(), *size);
    return ESP_OK;
}
static esp_err_t nvs_set_blob(nvs_handle_t h, const char *key, const void *data, size_t size) {
    if (failSet) return ESP_FAIL;
    assert(handles.at(h).mode==NVS_READWRITE);
    const auto *p=static_cast<const uint8_t *>(data);
    flash.at(handles.at(h).name)[key]=Blob(p,p+size); return ESP_OK;
}
static esp_err_t nvs_commit(nvs_handle_t h) {
    if (failCommit) return ESP_FAIL;
    handles.at(h); ++commits; return ESP_OK;
}
static esp_err_t nvs_erase_all(nvs_handle_t h) { ++erases; flash.at(handles.at(h).name).clear(); return ESP_OK; }
static void nvs_close(nvs_handle_t h) { assert(handles.erase(h)==1); }
static esp_err_t nvs_erase_key(nvs_handle_t h, const char *key) {
    assert(handles.at(h).mode==NVS_READWRITE);
    if (failErase) return ESP_FAIL;
    wrongType.erase(key);
    return flash.at(handles.at(h).name).erase(key) ? ESP_OK : ESP_ERR_NVS_NOT_FOUND;
}
struct FakeESP { void restart() { ++restarts; } } ESP;
static ble_store_value_sec ble_store_config_our_secs[6], ble_store_config_peer_secs[6];
static ble_store_value_cccd ble_store_config_cccds[8];
static ble_store_value_csfc ble_store_config_csfcs[6];
static ble_store_value_local_irk ble_store_config_local_irks[6];
static ble_store_value_rpa_rec ble_store_config_rpa_recs[6];
static int ble_store_config_num_our_secs, ble_store_config_num_peer_secs, ble_store_config_num_cccds;
static int ble_store_config_num_csfcs, ble_store_config_num_local_irks, ble_store_config_num_rpa_recs;
static int ble_store_config_our_bond_count, ble_store_config_peer_bond_count;
int ble_store_config_compare_bond_count(const void *a, const void *b) {
    return static_cast<const ble_store_value_sec *>(a)->bond_count-static_cast<const ble_store_value_sec *>(b)->bond_count;
}
static void coldRAM() {
    ble_store_config_num_our_secs=ble_store_config_num_peer_secs=ble_store_config_num_cccds=0;
    ble_store_config_num_csfcs=ble_store_config_num_local_irks=ble_store_config_num_rpa_recs=0;
    memset(ble_store_config_our_secs,0,sizeof(ble_store_config_our_secs));
    memset(ble_store_config_peer_secs,0,sizeof(ble_store_config_peer_secs));
    memset(ble_store_config_cccds,0,sizeof(ble_store_config_cccds));
    memset(ble_store_config_local_irks,0,sizeof(ble_store_config_local_irks));
}
'''

TESTS = r'''
static void reset() {
    assert(handles.empty()); flash.clear(); wrongType.clear(); nextHandle=1; restarts=erases=commits=writeOpens=0;
    failInit=failOpen=failRead=failSet=failCommit=failErase=failWriteOpen=false;
    flash["user_settings"]["screen"]={42,17,255};
}
static void boot() { assert(handles.empty()); repairIncompatibleBleBonds(); assert(handles.empty()); }
static ble_store_value value(int seed) {
    ble_store_value v{}; v.sec.peer_addr.type=1; v.sec.peer_addr.val[0]=seed;
    v.sec.key_size=16; v.sec.bond_count=seed; v.sec.ediv=100+seed;
    v.sec.rand_num=0x123456789abcdef0ULL+seed; v.sec.ltk_present=1; v.sec.irk_present=1;
    for (int i=0;i<16;++i) { v.sec.ltk[i]=seed+i; v.sec.irk[i]=seed+2*i; }
    v.sec.authenticated=1; v.sec.sc=1; return v;
}
static Blob bytes(const void *data, size_t size) {
    auto *p=static_cast<const uint8_t *>(data); return Blob(p,p+size);
}
static void verify(int type, const std::vector<Blob> &expected) {
    std::vector<uint8_t> ram(88*8,0); int count=0;
    assert(populate_db_from_nvs(type,ram.data(),&count)==0);
    assert(count==static_cast<int>(expected.size()));
    size_t stride=get_expected_size_for_obj_type(type);
    for (int i=0;i<count;++i) assert(bytes(ram.data()+stride*i,stride)==expected[i]);
}
int main() {
    reset(); boot(); verify(BLE_STORE_OBJ_TYPE_OUR_SEC,{}); assert(!erases && !restarts);
    puts("PASS empty store: no erase or restart");
    reset();
    std::vector<Blob> sec,cccd,irk;
    for (int i=1;i<=6;++i) {
        auto v=value(i); sec.push_back(bytes(&v.sec,sizeof(v.sec)));
        assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_OUR_SEC,&v)==0);
        assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_PEER_SEC,&v)==0);
        ble_store_value c{}; c.cccd.peer_addr=v.sec.peer_addr; c.cccd.chr_val_handle=20+i; c.cccd.flags=1;
        cccd.push_back(bytes(&c.cccd,sizeof(c.cccd)));
        assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_CCCD,&c)==0);
    }
    ble_store_value local{}; local.local_irk.addr.type=1; local.local_irk.irk[0]=17;
    assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_LOCAL_IRK,&local)==0);
    irk.push_back(bytes(&local.local_irk,sizeof(local.local_irk)));
    const auto before=flash;
    for (int reboot=0;reboot<10;++reboot) {
        oldCleanup(); assert(flash==before && !erases && !restarts);
        coldRAM(); boot(); assert(ble_nvs_restore_sec_keys()==0);
        assert(ble_store_config_num_our_secs==6 && ble_store_config_num_peer_secs==6);
        assert(ble_store_config_num_cccds==6 && ble_store_config_num_local_irks==1);
        boot(); verify(BLE_STORE_OBJ_TYPE_OUR_SEC,sec); verify(BLE_STORE_OBJ_TYPE_PEER_SEC,sec);
        verify(BLE_STORE_OBJ_TYPE_CCCD,cccd); verify(BLE_STORE_OBJ_TYPE_LOCAL_IRK,irk);
        assert(flash==before && !erases && !restarts);
    }
    puts("PASS six current bonds, CCCDs and local IRK survive old and current cleanup with 10 cold-RAM reloads");
    auto extra=value(7); assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_OUR_SEC,&extra)==BLE_HS_ESTORE_CAP);
    flash["nimble_bond"].erase("our_sec_1"); sec.erase(sec.begin()); boot(); verify(BLE_STORE_OBJ_TYPE_OUR_SEC,sec);
    puts("PASS full capacity and sparse slots restore without losing later bonds");
    for (int failure=0;failure<3;++failure) {
        reset(); auto v=value(1); assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_PEER_SEC,&v)==0);
        const auto saved=flash; failOpen=failure==0; failSet=failure==1; failCommit=failure==2;
        assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_OUR_SEC,&v)==BLE_HS_ESTORE_FAIL);
        assert(flash["nimble_bond"]["peer_sec_1"]==saved.at("nimble_bond").at("peer_sec_1") && handles.empty());
        if (failure!=2) assert(flash==saved);
        else assert(flash["nimble_bond"]["our_sec_1"]==bytes(&v.sec,sizeof(v.sec)));
    }
    puts("PASS SDK failure closes handles and preserves existing keys; set_blob is immediate, commit has no rollback");
    for (int failure=0;failure<3;++failure) {
        reset(); auto v=value(1); assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_OUR_SEC,&v)==0);
        const auto saved=flash; failInit=failure==0; failOpen=failure==1; failRead=failure==2;
        boot(); assert(flash==saved && !erases && !restarts);
    }
    puts("PASS cleanup init/open/read errors preserve existing storage");
    for (size_t badSize : {size_t(0),size_t(80),size_t(100)}) {
        reset(); auto v=value(2); assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_PEER_SEC,&v)==0);
        flash["nimble_bond"]["our_sec_1"]=Blob(badSize,0x5a);
        const auto unrelated=flash["user_settings"]; oldCleanup();
        assert(flash["nimble_bond"].empty() && restarts==1 && erases==1);
        assert(flash["user_settings"]==unrelated);
        oldCleanup(); assert(restarts==1 && erases==1);
    }
    puts("CHARACTERIZED existing cleanup: malformed/legacy first slot erases all bonds once, preserves other namespaces");
    reset(); auto v=value(1); assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_OUR_SEC,&v)==0);
    assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_PEER_SEC,&v)==0);
    assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_LOCAL_IRK,&local)==0);
    flash["nimble_bond"]["our_sec_2"]=Blob(80,0x5a); const auto corrupt=flash;
    oldCleanup(); assert(flash==corrupt && !erases && !restarts);
    ble_store_value_sec restored[6]{}; int count=0;
    assert(populate_db_from_nvs(BLE_STORE_OBJ_TYPE_OUR_SEC,restored,&count)==-1 && count==1);
    coldRAM(); assert(ble_nvs_restore_sec_keys()==-1);
    assert(ble_store_config_num_our_secs==1 && !ble_store_config_num_peer_secs && !ble_store_config_num_local_irks);
    auto newBond=value(3);
    assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_OUR_SEC,&newBond)==BLE_HS_ESTORE_FAIL);
    assert(flash==corrupt);
    nvs_handle_t repair; assert(nvs_open("nimble_bond",NVS_READWRITE,&repair)==0);
    assert(nvs_erase_key(repair,"our_sec_2")==0); assert(nvs_commit(repair)==0); nvs_close(repair);
    count=0; assert(populate_db_from_nvs(BLE_STORE_OBJ_TYPE_OUR_SEC,restored,&count)==0 && count==1);
    coldRAM(); assert(ble_nvs_restore_sec_keys()==0);
    assert(ble_store_config_num_peer_secs==1 && ble_store_config_num_local_irks==1);
    assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_OUR_SEC,&newBond)==0);
    verify(BLE_STORE_OBJ_TYPE_OUR_SEC,{bytes(&v.sec,sizeof(v.sec)),bytes(&newBond.sec,sizeof(newBond.sec))});
    puts("NEGATIVE CONTROL: old cleanup misses malformed slot2; SDK restore and write fail; targeted deletion restores both");
    const int types[]={BLE_STORE_OBJ_TYPE_OUR_SEC,BLE_STORE_OBJ_TYPE_PEER_SEC,BLE_STORE_OBJ_TYPE_CCCD,
                       BLE_STORE_OBJ_TYPE_CSFC,BLE_STORE_OBJ_TYPE_LOCAL_IRK,BLE_STORE_OBJ_TYPE_PEER_ADDR};
    for (int type:types) for (int slot:{1,2,get_nvs_max_obj_value(type)}) for (int malformed=0;malformed<4;++malformed) {
        reset();
        for (int other:types) {
            auto record=value(other); assert(ble_store_nvs_write(other,&record)==0);
            assert(ble_store_nvs_write(other,&record)==0);
            assert(ble_store_nvs_write(other,&record)==0);
        }
        flash["nimble_bond"]["future_key"]={91,23};
        char key[16]; get_nvs_key_string(type,slot,key);
        flash["nimble_bond"][key]=Blob(malformed==0 ? 0 : malformed==1 ? 1 : 200,0xa5);
        if (malformed==3) wrongType.insert(key);
        auto expected=flash; expected["nimble_bond"].erase(key);
        int initialCommits=commits, initialOpens=writeOpens;
        boot(); assert(flash==expected && !erases && !restarts && wrongType.empty());
        assert(commits==initialCommits+1 && writeOpens==initialOpens+1);
        coldRAM(); assert(ble_nvs_restore_sec_keys()==0);
        auto next=value(23); assert(ble_store_nvs_write(type,&next)==0);
        auto repaired=flash;
        for (int reboot=0;reboot<3;++reboot) {
            initialCommits=commits; initialOpens=writeOpens;
            coldRAM(); boot();
            assert(flash==repaired && commits==initialCommits && writeOpens==initialOpens);
            assert(ble_nvs_restore_sec_keys()==0 && flash==repaired);
        }
    }
    puts("PASS targeted production repair: six record types, first/second/last slots, empty/short/oversized/wrong-type blobs; preserves all other keys and resumes SDK persistence");
    reset();
    for (int type:types) { auto good=value(type); assert(ble_store_nvs_write(type,&good)==0); }
    auto expected=flash;
    flash["nimble_bond"]["our_sec_2"]={}; flash["nimble_bond"]["peer_sec_6"]={9};
    flash["nimble_bond"]["cccd_sec_8"]={42}; wrongType.insert("cccd_sec_8");
    int initialCommits=commits, initialOpens=writeOpens;
    boot(); assert(flash==expected && commits==initialCommits+1 && writeOpens==initialOpens+1);
    coldRAM(); assert(ble_nvs_restore_sec_keys()==0);
    puts("PASS several damaged types repaired with one write handle and one commit, preserving all healthy records");
    for (int failure=0;failure<4;++failure) {
        reset(); auto good=value(1); assert(ble_store_nvs_write(BLE_STORE_OBJ_TYPE_PEER_SEC,&good)==0);
        flash["nimble_bond"]["our_sec_2"]=Blob(1,0);
        auto saved=flash;
        failRead=failure==0; failWriteOpen=failure==1; failErase=failure==2; failCommit=failure==3;
        boot(); assert(!erases && !restarts);
        if (failure==3) saved["nimble_bond"].erase("our_sec_2");
        assert(flash==saved);
    }
    puts("PASS repair read/reopen/erase/commit failures preserve valid keys; immediate erase is not rolled back by commit failure");
    reset(); flash["nimble_bond"]["our_sec_1"]=Blob(88,0xff); boot();
    verify(BLE_STORE_OBJ_TYPE_OUR_SEC,{Blob(88,0xff)}); assert(!erases && !restarts);
    puts("CHARACTERIZED same-size corruption is accepted by size-only SDK validation; no semantic integrity claim");
    puts("PASS host SDK/NVS boundary checks; physical BLE reconnection and flash hardware are not emulated");
}
'''


if __name__ == "__main__":
    main()
