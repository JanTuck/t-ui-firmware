#include "graphics/view/TFT/ControlCenter.h"
#include "graphics/view/TFT/ControlCenterGesture.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>

using namespace ControlCenter;
namespace
{
State state;
struct Change {
    Action action;
    int value;
    bool persist;
};
std::vector<Change> changes;
lv_point_t point;
bool pressed;
unsigned flushes;
lv_obj_t *findText(lv_obj_t *root, const char *text)
{
    if (lv_obj_check_type(root, &lv_label_class) && !strcmp(lv_label_get_text(root), text) && lv_obj_is_visible(root))
        return root;
    for (uint32_t i = 0; i < lv_obj_get_child_count(root); ++i)
        if (auto *result = findText(lv_obj_get_child(root, i), text))
            return result;
    return nullptr;
}
lv_obj_t *findSlider(lv_obj_t *root)
{
    if (lv_obj_check_type(root, &lv_slider_class))
        return root;
    for (uint32_t i = 0; i < lv_obj_get_child_count(root); ++i)
        if (auto *result = findSlider(lv_obj_get_child(root, i)))
            return result;
    return nullptr;
}
bool opened()
{
    return findText(lv_layer_top(), "Control Center") != nullptr;
}
void advance(int ms = 90)
{
    for (int i = 0; i < ms; i += 10) {
        lv_tick_inc(10);
        tick();
        lv_timer_handler();
    }
}
void touch(int x, int y, bool down)
{
    point = {static_cast<int16_t>(x), static_cast<int16_t>(y)};
    pressed = down;
    advance();
}
void tap(int x, int y)
{
    touch(x, y, true);
    touch(x, y, false);
}
void drag(int x, int y, int ex, int ey)
{
    touch(x, y, true);
    for (int i = 1; i <= 8; ++i)
        touch(x + (ex - x) * i / 8, y + (ey - y) * i / 8, true);
    touch(ex, ey, false);
}
} // namespace
int main()
{
    CornerGesture g;
    g.begin(290, 5);
    assert(!g.move(290, 32));
    assert(g.move(290, 33));
    g.begin(290, 5);
    assert(!g.move(315, 40));
    assert(!g.move(290, 70));
    g.begin(290, 20);
    assert(!g.move(290, 7));
    assert(!g.move(290, 70));
    g.begin(290, 5);
    assert(g.tap(295, 10));
    assert(!g.tap(302, 5));

    lv_init();
    auto *display = lv_display_create(320, 240);
    static uint8_t buffer[320 * 240 * 4];
    lv_display_set_buffers(display, buffer, nullptr, sizeof(buffer), LV_DISPLAY_RENDER_MODE_FULL);
    lv_display_set_flush_cb(display, [](lv_display_t *d, const lv_area_t *, uint8_t *) {
        ++flushes;
        lv_display_flush_ready(d);
    });
    auto *group = lv_group_create();
    lv_group_set_default(group);
    auto *pointer = lv_indev_create();
    lv_indev_set_type(pointer, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(pointer, [](lv_indev_t *, lv_indev_data_t *data) {
        data->point = point;
        data->state = pressed ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
    });
    auto *keyboard = lv_indev_create();
    lv_indev_set_type(keyboard, LV_INDEV_TYPE_KEYPAD);
    lv_indev_set_group(keyboard, group);
    lv_indev_set_read_cb(keyboard, [](lv_indev_t *, lv_indev_data_t *data) { data->state = LV_INDEV_STATE_RELEASED; });
    auto *underlying = lv_button_create(lv_screen_active());
    lv_group_add_obj(group, underlying);
    state.allowed = state.wifiAvailable = state.wifiConfigured = state.bluetoothAvailable = state.gpsAvailable = true;
    init([] { return state; },
         [](Action action, int value, bool persist) {
             changes.push_back({action, value, persist});
             if (action == Gps)
                 state.gpsEnabled = value;
             if (action == Brightness && persist)
                 state.brightness = value;
         });
    advance();
    tap(292, 9);
    assert(opened());
    assert(lv_indev_get_group(keyboard) != group);
    assert(lv_group_get_default() == group);
    advance(300);
    const unsigned idleFlushes = flushes;
    advance(500);
    assert(flushes == idleFlushes);
    tap(50, 70);
    assert(findText(lv_layer_top(), "Turn on\n& restart"));
    assert(changes.empty());
    tap(288, 20);
    assert(!opened());
    assert(changes.empty());
    assert(lv_indev_get_group(keyboard) == group);
    drag(292, 6, 290, 80);
    assert(opened());
    tap(155, 70);
    tap(265, 200);
    assert(!opened());
    assert(changes.size() == 1 && changes.back().action == Bluetooth && changes.back().value == 1);
    tap(292, 9);
    assert(opened());
    tap(260, 70);
    assert(state.gpsEnabled);
    const auto before = changes.size();
    drag(100, 150, 250, 150);
    assert(opened());
    int saved = 0;
    for (size_t i = before; i < changes.size(); ++i)
        if (changes[i].action == Brightness && changes[i].persist)
            ++saved;
    assert(saved == 1);
    assert(state.brightness > 153);
    assert(close());
    advance();
    assert(!opened());
    tap(292, 9);
    auto *brightness = findSlider(lv_layer_top());
    assert(brightness);
    lv_group_focus_obj(brightness);
    const auto keyBefore = changes.size();
    lv_group_send_data(lv_indev_get_group(keyboard), LV_KEY_LEFT);
    advance();
    close();
    advance();
    int keySaved = 0;
    for (size_t i = keyBefore; i < changes.size(); ++i)
        if (changes[i].action == Brightness && changes[i].persist)
            ++keySaved;
    assert(keySaved == 1);
    drag(292, 9, 240, 70);
    assert(!opened());
    state.allowed = false;
    advance();
    tap(292, 9);
    assert(!opened());
    state.allowed = true;
    auto *modal = lv_obj_create(lv_layer_top());
    lv_obj_set_size(modal, 320, 240);
    advance();
    tap(292, 9);
    assert(!opened());
    lv_obj_delete(modal);
    auto *textarea = lv_textarea_create(lv_screen_active());
    lv_group_add_obj(group, textarea);
    lv_group_focus_obj(textarea);
    advance();
    tap(292, 9);
    assert(!opened());
    lv_obj_delete(textarea);
    advance();
    tap(292, 9);
    assert(opened());
    state.allowed = false;
    advance();
    assert(!opened());
    state.allowed = true;
    advance();
    tap(292, 9);
    assert(opened());
    auto *next = lv_obj_create(nullptr);
    lv_screen_load(next);
    advance();
    assert(!opened());
    assert(lv_indev_get_group(keyboard) == group);
    advance();
    tap(292, 9);
    assert(opened());
    drag(2, 170, 2, 80);
    assert(!opened());
    puts("Control Center: gesture, confirmation, state, persistence, modal, lock, focus and screen-change tests passed");
}
