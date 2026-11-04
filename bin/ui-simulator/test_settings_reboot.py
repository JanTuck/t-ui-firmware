#!/usr/bin/env python3
"""Execute the production preset callback and reboot presentation without hardware."""

from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    source = (args.source or root / "lib/meshtastic-device-ui/source/graphics/TFT/TFTView_320x240.cpp").read_text()
    callback = source[source.index("case eModemPreset: {"):source.index("case eChannel: {", source.index("case eModemPreset: {"))]
    notify = function(source, "void TFTView_320x240::notifyReboot(bool show)")
    resync = function(source, "void TFTView_320x240::notifyResync(bool show)")
    update_lora = function(source, "void TFTView_320x240::updateLoRaConfig(const meshtastic_Config_LoRaConfig &cfg)")
    controller_source = (root / "lib/meshtastic-device-ui/source/graphics/common/ViewController.cpp").read_text()
    send_lvalue = function(controller_source, "bool ViewController::sendAdminMessage(meshtastic_AdminMessage &config, uint32_t nodeId)")
    send_rvalue = function(controller_source, "bool ViewController::sendAdminMessage(meshtastic_AdminMessage &&config, uint32_t nodeId)")
    refresh = function(controller_source, "void ViewController::requestConfig(void)")
    harness = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdarg>
#include <string>
#include <vector>
#include <functional>
#define _(s) s
int lv_snprintf(char *buffer, size_t size, const char *format, ...) {
    va_list args;
    va_start(args, format);
    const int result = vsnprintf(buffer, size, format, args);
    va_end(args);
    return result;
}
using meshtastic_Config_LoRaConfig_ModemPreset = unsigned;
struct meshtastic_Config_LoRaConfig { bool use_preset; unsigned modem_preset; uint16_t channel_num; unsigned region = 1; };
struct Controller {
    bool standalone = false, acceptSend = true;
    unsigned sends = 0;
    meshtastic_Config_LoRaConfig sent{};
    std::function<bool()> sendHook;
    bool isStandalone() { return standalone; }
    bool sendConfig(meshtastic_Config_LoRaConfig value, unsigned) {
        ++sends; sent = value; return sendHook ? sendHook() : acceptSend;
    }
};
struct {
    int settings_modem_preset_dropdown, frequency_slot_slider, basic_settings_modem_preset_label;
    int settings_modem_preset_panel, basic_settings_modem_preset_button;
    int basic_settings_region_label;
    int alert_label, main_screen;
} objects;
unsigned selectedPreset = 2;
uint16_t selectedSlot = 8;
unsigned timers = 0, visibleNotices = 0, hiddenNotices = 0;
std::string alertText;
const unsigned LV_OBJ_FLAG_HIDDEN = 1;
const unsigned LV_ANIM_OFF = 0, meshtastic_Config_LoRaConfig_RegionCode_UNSET = 0, meshtastic_Channel_Role_DISABLED = 0;
const unsigned LV_SCR_LOAD_ANIM_NONE = 0;
const int c_max_channels = 1;
struct lv_timer_t {};
unsigned lv_dropdown_get_selected(int) { return selectedPreset; }
uint16_t lv_slider_get_value(int) { return selectedSlot; }
void lv_dropdown_get_selected_str(int, char *buffer, size_t count) { snprintf(buffer, count, "MediumFast"); }
void lv_label_set_text(int, const char *) {}
const char *lv_label_get_text(int) { return alertText.c_str(); }
void lv_screen_load_anim(int, unsigned, unsigned, unsigned, bool) {}
void lv_obj_add_flag(int, unsigned) {}
void lv_group_focus_obj(int) {}
void lv_dropdown_set_selected(int, unsigned value) { selectedPreset = value; }
void lv_slider_set_range(int, unsigned, unsigned) {}
void lv_slider_set_value(int, unsigned value, unsigned) { selectedSlot = value; }
struct Channel { bool has_settings = false; unsigned role = 0; struct { char name[1]{}; } settings; };
struct LoRaPresets {
    static unsigned getDefaultSlot(unsigned, unsigned, const char *) { return 1; }
    static unsigned getNumChannels(unsigned, unsigned) { return 16; }
    static const char *loRaRegionToString(unsigned) { return "US"; }
};
void lv_timer_create(void (*)(lv_timer_t *), unsigned delay, void *) { assert(delay == 8000); ++timers; }
class TFTView_320x240 {
public:
    Controller *controller;
    unsigned ownNode = 1;
    struct { struct { meshtastic_Config_LoRaConfig lora{true, 1, 1}; bool has_lora = false; } config; Channel channel[1]; } db;
    unsigned val2preset(unsigned value) { return value; }
    unsigned preset2val(unsigned value) { return value; }
    void showLoRaFrequency(const meshtastic_Config_LoRaConfig &) {}
    void setChannelName(Channel &) {}
    void requestSetup() {}
    void messageAlert(const char *message, bool show) {
        if (show) { ++visibleNotices; alertText = message; }
        else ++hiddenNotices;
    }
    static void timer_event_reboot(lv_timer_t *) {}
    void notifyReboot(bool show);
    void notifyResync(bool show);
    void applyPreset();
    void updateLoRaConfig(const meshtastic_Config_LoRaConfig &);
};
TFTView_320x240 *THIS;
enum { eModemPreset };
enum {
    meshtastic_AdminMessage_store_ui_config_tag,
    meshtastic_AdminMessage_set_owner_tag,
    meshtastic_AdminMessage_set_config_tag,
    meshtastic_AdminMessage_set_module_config_tag,
    meshtastic_AdminMessage_set_channel_tag,
    meshtastic_AdminMessage_set_fixed_position_tag,
    meshtastic_AdminMessage_set_ringtone_message_tag,
    getConfigTag
};
struct meshtastic_AdminMessage { unsigned which_payload_variant; };
struct meshtastic_Data_payload_t { unsigned size; uint8_t bytes[256]; };
constexpr unsigned DATA_PAYLOAD_LEN = 256, meshtastic_PortNum_ADMIN_APP = 6, meshtastic_AdminMessage_msg = 0;
unsigned encodedBytes = 12;
unsigned pb_encode_to_bytes(uint8_t *, unsigned, const unsigned *, const meshtastic_AdminMessage *) { return encodedBytes; }
#define ILOG_ERROR(...) ((void)0)
struct NoticeView {
    std::vector<std::string> messages;
    void notifyClientNotification(const char *message) { messages.emplace_back(message); }
};
struct meshtastic_ToRadio { unsigned which_payload_variant; uint32_t want_config_id; };
const unsigned meshtastic_ToRadio_want_config_id_tag = 1;
struct FakeClient {
    bool connected = true, space = true, accept = true;
    unsigned sends = 0;
    bool isConnected() { return connected; }
    bool available() { return space; }
    bool send(meshtastic_ToRadio) { ++sends; return accept; }
};
class ViewController {
public:
    NoticeView *view = nullptr;
    bool setupDone = true, acceptSend = true;
    bool requestConfigRequired = false;
    unsigned myNodeNum = 1;
    FakeClient *client;
    unsigned sends = 0;
    bool send(unsigned, unsigned, const meshtastic_Data_payload_t &, bool) { ++sends; return acceptSend; }
    bool sendAdminMessage(meshtastic_AdminMessage &, uint32_t);
    bool sendAdminMessage(meshtastic_AdminMessage &&, uint32_t);
    void requestConfig();
};
'''
    harness += notify + "\n" + resync + "\nvoid TFTView_320x240::applyPreset() { switch(eModemPreset) {\n" + callback + "\n} }\n"
    harness += send_lvalue + "\n" + send_rvalue + "\n" + refresh + "\n" + update_lora + "\n"
    harness += r'''
int main() {
    Controller controller;
    TFTView_320x240 view;
    view.controller = &controller;
    THIS = &view;
    // Queuing a live LoRa change must not claim a reboot; persistence happens asynchronously.
    view.applyPreset();
    assert(controller.sends == 1 && controller.sent.modem_preset == selectedPreset);
    assert(controller.sent.channel_num == selectedSlot);
    assert(visibleNotices == 0 && timers == 0);
    // Queue failure must not display an impending reboot either.
    controller.acceptSend = false;
    selectedSlot = 9;
    view.applyPreset();
    assert(controller.sends == 2 && visibleNotices == 0 && timers == 0);
    // Rejected persistence must remain free of an optimistic embedded reboot timer.
    view.notifyReboot(true);
    assert(visibleNotices == 0 && timers == 0);
    controller.standalone = true;
    view.notifyReboot(false);
    assert(hiddenNotices == 1 && timers == 0);
    view.notifyReboot(true);
    assert(visibleNotices == 1 && timers == 1);
    NoticeView notices;
    ViewController admin;
    admin.view = &notices;
    meshtastic_AdminMessage settings{meshtastic_AdminMessage_set_config_tag};
    assert(admin.sendAdminMessage(settings, 1));
    assert(admin.sends == 1 && notices.messages.empty());
    encodedBytes = 0;
    assert(!admin.sendAdminMessage(settings, 1));
    assert(admin.sends == 1 && notices.messages.size() == 1);
    assert(notices.messages.back() == "Settings were not sent. Retry.");
    assert(admin.requestConfigRequired);
    admin.requestConfigRequired = false;
    assert(!admin.sendAdminMessage(settings, 2));
    assert(!admin.requestConfigRequired && notices.messages.size() == 2);
    encodedBytes = 12;
    admin.acceptSend = false;
    assert(!admin.sendAdminMessage(meshtastic_AdminMessage{meshtastic_AdminMessage_store_ui_config_tag}, 1));
    assert(admin.sends == 2 && notices.messages.size() == 3);
    assert(notices.messages.back() == "Settings were not sent. Retry.");
    assert(!admin.sendAdminMessage(meshtastic_AdminMessage{getConfigTag}, 1));
    assert(admin.sends == 3 && notices.messages.size() == 4);
    assert(notices.messages.back() == "Request was not sent. Retry.");
    admin.setupDone = false;
    admin.requestConfigRequired = false;
    assert(!admin.sendAdminMessage(settings, 1));
    assert(admin.sends == 4 && notices.messages.size() == 4 && !admin.requestConfigRequired);
    admin.setupDone = true;
    admin.view = nullptr;
    assert(!admin.sendAdminMessage(settings, 1));
    assert(admin.sends == 5);
    admin.view = &notices;
    FakeClient transport;
    admin.client = &transport;
    controller.standalone = false;
    controller.sendHook = [&]() { return admin.sendAdminMessage(settings, 1); };
    const meshtastic_Config_LoRaConfig committed{true, 1, 1};
    view.updateLoRaConfig(committed);
    selectedPreset = 2; selectedSlot = 8;
    view.applyPreset();
    assert(view.db.config.lora.modem_preset == 2 && admin.requestConfigRequired);
    const auto noticesBeforeRefresh = notices.messages.size();
    transport.space = false;
    for (unsigned i = 0; i < 20; ++i) admin.requestConfig();
    assert(transport.sends == 0 && admin.requestConfigRequired);
    assert(notices.messages.size() == noticesBeforeRefresh);
    transport.space = true; transport.accept = false;
    admin.requestConfig();
    assert(transport.sends == 1 && admin.requestConfigRequired);
    transport.accept = true;
    admin.requestConfig();
    assert(transport.sends == 2 && !admin.requestConfigRequired);
    // Inject the backend response through the actual view config update function.
    view.updateLoRaConfig(committed);
    assert(view.db.config.lora.modem_preset == 1 && selectedPreset == 1 && selectedSlot == 1);
    const auto sendsBeforeRetry = controller.sends;
    selectedPreset = 2; selectedSlot = 8; admin.acceptSend = true;
    view.applyPreset();
    assert(controller.sends == sendsBeforeRetry + 1 && controller.sent.modem_preset == 2);
    assert(controller.sent.channel_num == 8 && !admin.requestConfigRequired);
    assert(visibleNotices == 1 && timers == 1);
    const auto hiddenBeforeResync = hiddenNotices;
    view.messageAlert("Settings were not sent. Retry.", true);
    view.notifyResync(false);
    assert(hiddenNotices == hiddenBeforeResync && alertText == "Settings were not sent. Retry.");
    view.messageAlert("Rebooting ...", true);
    view.notifyResync(false);
    assert(hiddenNotices == hiddenBeforeResync && alertText == "Rebooting ...");
    view.notifyResync(true);
    assert(alertText == "Resync ...");
    view.notifyResync(false);
    assert(hiddenNotices == hiddenBeforeResync + 1);
    puts("settings reboot UI: 22 contract checks passed");
}
'''
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        raise SystemExit("C++ compiler required")
    with tempfile.TemporaryDirectory(prefix="settings-reboot-") as temporary:
        folder = Path(temporary)
        cpp = folder / "test.cpp"
        executable = folder / "test"
        cpp.write_text(harness)
        subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
