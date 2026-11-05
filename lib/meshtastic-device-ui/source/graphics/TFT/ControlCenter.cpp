#if defined(VIEW_320x240) || defined(VIEW_240x320)
#include "graphics/view/TFT/ControlCenter.h"
#include "graphics/view/TFT/ControlCenterGesture.h"
#include "graphics/view/TFT/GlassUI.h"
#include "ui.h"
#include <cstring>

namespace ControlCenter
{
namespace
{
Read readState;
Write writeState;
lv_obj_t *handle, *panel, *origin, *slider, *hint, *confirm, *settingsButton;
lv_obj_t *tiles[3], *labels[3];
lv_obj_t *brightnessFill, *brightnessSun;
int drawnBrightness = -1;
lv_group_t *savedGroup;
lv_obj_t *savedFocus;
lv_group_t *panelGroup;
CornerGesture gesture;
lv_point_t dismissStart;
bool dismissArmed = false;
int pending = -1;
bool pendingValue = false;
State last;
bool haveLast = false;
bool dragging = false;
bool brightnessDirty = false;
int previewBrightness = 153;
const char *lastText[3] = {};

bool overlaysPresent()
{
    lv_obj_t *top = lv_layer_top();
    for (uint32_t i = 0; i < lv_obj_get_child_count(top); ++i) {
        lv_obj_t *child = lv_obj_get_child(top, i);
        if (child != handle && child != panel && lv_obj_is_visible(child) && lv_obj_get_height(child) > 30 &&
            lv_obj_has_flag(child, LV_OBJ_FLAG_CLICKABLE))
            return true;
    }
    return false;
}

bool allowed()
{
    if (!readState || !readState().allowed || overlaysPresent())
        return false;
    lv_obj_t *focused = lv_group_get_focused(panel ? panelGroup : lv_group_get_default());
    return !focused || !lv_obj_is_visible(focused) || !lv_obj_check_type(focused, &lv_textarea_class);
}

void surface(lv_obj_t *obj)
{
    GlassUI::surface(obj);
}

lv_obj_t *button(lv_obj_t *parent, const char *text, int x, int y, int w, int h, lv_event_cb_t cb)
{
    lv_obj_t *obj = lv_button_create(parent);
    lv_obj_set_pos(obj, x, y);
    lv_obj_set_size(obj, w, h);
    surface(obj);
    lv_obj_set_style_bg_color(obj, lv_color_hex(0x3b506e), LV_STATE_PRESSED);
    lv_obj_t *label = lv_label_create(obj);
    lv_label_set_text(label, text);
    lv_obj_center(label);
    lv_obj_add_flag(obj, LV_OBJ_FLAG_EVENT_BUBBLE);
    lv_obj_add_event_cb(obj, cb, LV_EVENT_CLICKED, nullptr);
    lv_group_add_obj(panelGroup, obj);
    return obj;
}

void dismiss(lv_event_t *)
{
    close();
}

void updateBrightnessFill()
{
    const int value = lv_slider_get_value(slider);
    if (value == drawnBrightness)
        return;
    drawnBrightness = value;
    const int height = (value - 10) * 121 / 245;
    lv_obj_set_height(brightnessFill, height);
    lv_obj_set_y(brightnessFill, 121 - height);
    lv_obj_set_y(brightnessSun, 74 - (121 - height));
}

void refresh()
{
    State state = readState();
    const bool enabled[] = {state.wifiEnabled, state.bluetoothEnabled, state.gpsEnabled};
    const bool available[] = {state.wifiAvailable, state.bluetoothAvailable, state.gpsAvailable};
    const bool oldEnabled[] = {last.wifiEnabled, last.bluetoothEnabled, last.gpsEnabled};
    const char *texts[] = {!state.wifiAvailable    ? "Wi-Fi\nNo radio"
                           : state.wifiConnected   ? (state.wifiEnabled ? "Wi-Fi\nConnected" : "Wi-Fi\nIn app")
                           : !state.wifiConfigured ? "Wi-Fi\nSet up"
                           : state.wifiEnabled     ? "Wi-Fi\nJoining"
                                                   : "Wi-Fi\nOff",
                           !state.bluetoothAvailable ? "Bluetooth\nNo radio"
                           : state.bluetoothActive   ? "Bluetooth\nEnabled"
                           : state.bluetoothEnabled  ? "Bluetooth\nRestart"
                                                     : "Bluetooth\nOff",
                           !state.gpsAvailable ? "GPS\nNo GPS"
                           : state.gpsEnabled  ? "GPS\nOn"
                                               : "GPS\nOff"};
    for (int i = 0; i < 3; ++i) {
        if (!haveLast || !lastText[i] || strcmp(lastText[i], texts[i])) {
            lv_label_set_text(labels[i], texts[i]);
            lastText[i] = texts[i];
        }
        if (!haveLast || enabled[i] != oldEnabled[i]) {
            lv_obj_set_style_bg_color(tiles[i], lv_color_hex(enabled[i] ? 0x168cf5 : 0xc8e0fa), 0);
            lv_obj_set_style_bg_opa(tiles[i], enabled[i] ? 230 : 65, 0);
        }
        if (available[i])
            lv_obj_remove_state(tiles[i], LV_STATE_DISABLED);
        else
            lv_obj_add_state(tiles[i], LV_STATE_DISABLED);
    }
    if (!dragging && !brightnessDirty && (!haveLast || state.brightness != last.brightness))
        lv_slider_set_value(slider, state.brightness, LV_ANIM_OFF);
    updateBrightnessFill();
    last = state;
    haveLast = true;
}

void choose(lv_event_t *e)
{
    if (!allowed()) {
        close();
        return;
    }
    const int action = static_cast<int>(reinterpret_cast<intptr_t>(lv_event_get_user_data(e)));
    State state = readState();
    if (action == Gps) {
        writeState(Gps, !state.gpsEnabled, true);
        refresh();
        return;
    }
    if (action == Wifi && (!state.wifiConfigured || (state.wifiConnected && !state.wifiEnabled))) {
        pending = -1;
        lv_obj_add_flag(confirm, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(settingsButton, LV_OBJ_FLAG_HIDDEN);
        lv_label_set_text(hint, !state.wifiConfigured ? "Set a Wi-Fi network name\nand password in Settings."
                                                      : "An app is using Wi-Fi.\nDisconnect from that app.");
        return;
    }
    pending = action;
    pendingValue = action == Wifi ? !state.wifiEnabled : !state.bluetoothEnabled;
    lv_label_set_text(lv_obj_get_child(confirm, 0), pendingValue ? "Turn on\n& restart" : "Turn off\n& restart");
    const char *message =
        action == Wifi ? (pendingValue ? "Restart to enable Wi-Fi.\nBluetooth will pause." : "Restart to disable Wi-Fi.")
                       : (pendingValue ? "Restart to enable Bluetooth.\nWi-Fi will turn off." : "Restart to disable Bluetooth.");
    lv_label_set_text(hint, message);
    lv_obj_add_flag(settingsButton, LV_OBJ_FLAG_HIDDEN);
    lv_obj_remove_flag(confirm, LV_OBJ_FLAG_HIDDEN);
}

void apply(lv_event_t *)
{
    if (pending < 0 || !allowed()) {
        close();
        return;
    }
    State state = readState();
    if ((pending == Wifi && (!state.wifiAvailable || !state.wifiConfigured || (state.wifiConnected && !state.wifiEnabled))) ||
        (pending == Bluetooth && !state.bluetoothAvailable)) {
        close();
        return;
    }
    Action action = static_cast<Action>(pending);
    const bool value = pendingValue;
    close();
    writeState(action, value, true);
}

void open()
{
    if (panel || !allowed())
        return;
    origin = lv_screen_active();
    savedGroup = lv_group_get_default();
    savedFocus = lv_group_get_focused(savedGroup);
    panelGroup = lv_group_create();
    for (lv_indev_t *dev = lv_indev_get_next(nullptr); dev; dev = lv_indev_get_next(dev))
        if (lv_indev_get_group(dev) == savedGroup)
            lv_indev_set_group(dev, panelGroup);
    panel = lv_obj_create(lv_layer_top());
    lv_obj_set_size(panel, 320, 240);
    lv_obj_set_pos(panel, 0, 0);
    surface(panel);
    lv_obj_set_style_radius(panel, 0, 0);
    lv_obj_set_style_border_width(panel, 0, 0);
    GlassUI::wallpaper(panel);
    lv_obj_set_style_bg_opa(panel, LV_OPA_COVER, 0);
    lv_obj_t *title = lv_label_create(panel);
    lv_label_set_text(title, "Control Center");
    lv_obj_set_style_text_font(title, &ui_font_montserrat_16, 0);
    lv_obj_set_pos(title, 12, 15);
    button(panel, "Done", 260, 7, 52, 30, dismiss);
    lv_obj_t *connections = lv_obj_create(panel);
    surface(connections);
    lv_obj_set_pos(connections, 10, 46);
    lv_obj_set_size(connections, 214, 121);
    lv_obj_remove_flag(connections, LV_OBJ_FLAG_CLICKABLE);
    const char *symbols[] = {"Wifi", "Bluetooth", "Gps"};
    for (int i = 0; i < 3; ++i) {
        tiles[i] = button(panel, "", 20 + i * 70, 57, 54, 54, [](lv_event_t *) {});
        lv_obj_set_style_radius(tiles[i], LV_RADIUS_CIRCLE, 0);
        GlassUI::symbol(tiles[i], symbols[i], 12, 12);
        labels[i] = lv_label_create(panel);
        lv_obj_set_pos(labels[i], 12 + i * 70, 118);
        lv_obj_set_width(labels[i], 70);
        lv_obj_set_style_text_align(labels[i], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_add_event_cb(tiles[i], choose, LV_EVENT_CLICKED, reinterpret_cast<void *>(static_cast<intptr_t>(i)));
    }
    slider = lv_slider_create(panel);
    lv_obj_remove_style_all(slider);
    lv_obj_set_pos(slider, 240, 46);
    lv_obj_set_size(slider, 64, 121);
    lv_obj_set_ext_click_area(slider, 6);
    lv_slider_set_range(slider, 10, 255);
    lv_obj_set_style_radius(slider, 32, LV_PART_MAIN);
    lv_obj_set_style_clip_corner(slider, true, LV_PART_MAIN);
    lv_obj_set_style_bg_color(slider, lv_color_hex(0x355a8c), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(slider, 160, LV_PART_MAIN);
    lv_obj_set_style_outline_color(slider, lv_color_white(), LV_STATE_FOCUS_KEY);
    lv_obj_set_style_outline_width(slider, 2, LV_STATE_FOCUS_KEY);
    lv_obj_set_style_outline_pad(slider, 2, LV_STATE_FOCUS_KEY);
    lv_obj_remove_flag(slider, LV_OBJ_FLAG_OVERFLOW_VISIBLE);
    GlassUI::symbol(slider, "Sun", 18, 74);
    brightnessFill = lv_obj_create(slider);
    lv_obj_remove_style_all(brightnessFill);
    lv_obj_remove_flag(brightnessFill, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(brightnessFill, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_width(brightnessFill, 64);
    lv_obj_set_style_bg_color(brightnessFill, lv_color_hex(0xe9f6ff), 0);
    lv_obj_set_style_bg_opa(brightnessFill, LV_OPA_COVER, 0);
    GlassUI::symbol(brightnessFill, "Sun", 18, 0);
    brightnessSun = lv_obj_get_child(brightnessFill, 0);
    lv_obj_set_style_image_recolor(brightnessSun, lv_color_hex(0x355a8c), 0);
    drawnBrightness = -1;
    lv_obj_add_flag(slider, LV_OBJ_FLAG_EVENT_BUBBLE);
    lv_group_add_obj(panelGroup, slider);
    lv_obj_add_event_cb(
        slider,
        [](lv_event_t *e) {
            const auto code = lv_event_get_code(e);
            if (!panel)
                return;
            if (code == LV_EVENT_PRESSED)
                dragging = true;
            if (code == LV_EVENT_VALUE_CHANGED ||
                ((code == LV_EVENT_RELEASED || code == LV_EVENT_PRESS_LOST) && brightnessDirty)) {
                if (!allowed()) {
                    close();
                    return;
                }
                updateBrightnessFill();
                previewBrightness = lv_slider_get_value(slider);
                brightnessDirty = true;
                lv_indev_t *dev = lv_indev_active();
                const bool persist = code == LV_EVENT_RELEASED || code == LV_EVENT_PRESS_LOST ||
                                     (dev && lv_indev_get_type(dev) != LV_INDEV_TYPE_POINTER);
                writeState(Brightness, previewBrightness, persist);
                if (persist)
                    brightnessDirty = false;
            }
            if (code == LV_EVENT_RELEASED || code == LV_EVENT_PRESS_LOST)
                dragging = false;
        },
        LV_EVENT_ALL, nullptr);
    hint = lv_label_create(panel);
    lv_obj_set_pos(hint, 12, 180);
    lv_obj_set_size(hint, 198, 48);
    lv_label_set_text(hint, "");
    settingsButton = button(panel, "Settings", 218, 178, 94, 48, [](lv_event_t *) {
        close();
        writeState(Settings, 0, false);
    });
    confirm = button(panel, "Restart", 218, 178, 94, 48, apply);
    lv_obj_set_style_bg_color(confirm, lv_color_hex(0x1678dd), 0);
    lv_obj_set_style_bg_opa(confirm, LV_OPA_COVER, 0);
    lv_obj_set_style_text_align(lv_obj_get_child(confirm, 0), LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_add_flag(confirm, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(panel, LV_OBJ_FLAG_PRESS_LOCK);
    lv_obj_add_event_cb(
        panel,
        [](lv_event_t *e) {
            lv_indev_t *dev = lv_event_get_indev(e);
            if (!dev || lv_event_get_target(e) != panel)
                return;
            lv_point_t p;
            lv_indev_get_point(dev, &p);
            if (lv_event_get_code(e) == LV_EVENT_PRESSED) {
                dismissStart = p;
                dismissArmed = true;
            } else if (lv_event_get_code(e) == LV_EVENT_PRESSING && dismissArmed) {
                const int dx = p.x - dismissStart.x;
                if (dx > 24 || dx < -24)
                    dismissArmed = false;
                else if (p.y - dismissStart.y <= -28) {
                    lv_indev_wait_release(dev);
                    close();
                }
            }
        },
        LV_EVENT_ALL, nullptr);
    lv_obj_add_event_cb(
        panel,
        [](lv_event_t *e) {
            if (lv_event_get_key(e) == LV_KEY_ESC)
                close();
        },
        LV_EVENT_KEY, nullptr);
    haveLast = false;
    refresh();
    lv_obj_add_flag(handle, LV_OBJ_FLAG_HIDDEN);
}
} // namespace

bool close()
{
    if (!panel)
        return false;
    if (brightnessDirty)
        writeState(Brightness, previewBrightness, true);
    brightnessDirty = false;
    dragging = false;
    for (lv_indev_t *dev = lv_indev_get_next(nullptr); dev; dev = lv_indev_get_next(dev))
        if (lv_indev_get_group(dev) == panelGroup)
            lv_indev_set_group(dev, savedGroup);
    if (savedFocus && lv_obj_is_valid(savedFocus) && lv_obj_is_visible(savedFocus))
        lv_group_focus_obj(savedFocus);
    lv_group_delete(panelGroup);
    lv_obj_delete_async(panel);
    panel = nullptr;
    pending = -1;
    return true;
}

bool isOpen()
{
    return panel != nullptr;
}

void init(Read read, Write write)
{
    if (handle)
        return;
    readState = read;
    writeState = write;
    handle = lv_obj_create(lv_layer_top());
    lv_obj_remove_style_all(handle);
    lv_obj_set_pos(handle, 272, 0);
    lv_obj_set_size(handle, 48, 22);
    lv_obj_add_flag(handle, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_flag(handle, LV_OBJ_FLAG_PRESS_LOCK);
    lv_obj_add_flag(handle, LV_OBJ_FLAG_HIDDEN);
    lv_obj_remove_flag(handle, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_event_cb(
        handle,
        [](lv_event_t *e) {
            lv_indev_t *dev = lv_event_get_indev(e);
            if (!dev)
                return;
            lv_point_t p;
            lv_indev_get_point(dev, &p);
            switch (lv_event_get_code(e)) {
            case LV_EVENT_PRESSED:
                gesture.begin(p.x, p.y);
                break;
            case LV_EVENT_PRESSING:
                if (gesture.move(p.x, p.y)) {
                    lv_indev_wait_release(dev);
                    open();
                }
                break;
            case LV_EVENT_RELEASED:
                if (gesture.tap(p.x, p.y))
                    open();
                break;
            default:
                break;
            }
        },
        LV_EVENT_ALL, nullptr);
}

void tick()
{
    if (!handle)
        return;
    const bool ready = allowed();
    if (panel && (!ready || origin != lv_screen_active()))
        close();
    const bool show = ready && !panel;
    if (show == lv_obj_has_flag(handle, LV_OBJ_FLAG_HIDDEN)) {
        if (show) {
            lv_obj_remove_flag(handle, LV_OBJ_FLAG_HIDDEN);
            lv_obj_move_foreground(handle);
        } else
            lv_obj_add_flag(handle, LV_OBJ_FLAG_HIDDEN);
    }
    if (panel)
        refresh();
}
} // namespace ControlCenter
#endif
