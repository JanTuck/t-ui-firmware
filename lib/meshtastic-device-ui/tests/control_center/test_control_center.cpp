#include "graphics/view/TFT/ControlCenter.h"
#include "graphics/view/TFT/ControlCenterGesture.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
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
bool keyDown;
uint32_t key;
int encoderDiff;
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
    lv_indev_set_read_cb(keyboard, [](lv_indev_t *, lv_indev_data_t *data) {
        data->key = key;
        data->state = keyDown ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
    });
    auto *encoder = lv_indev_create();
    lv_indev_set_type(encoder, LV_INDEV_TYPE_ENCODER);
    lv_indev_set_group(encoder, group);
    lv_indev_set_read_cb(encoder, [](lv_indev_t *, lv_indev_data_t *data) {
        data->enc_diff = encoderDiff;
        encoderDiff = 0;
        data->state = LV_INDEV_STATE_RELEASED;
    });
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
    assert(!findText(lv_layer_top(), "Settings"));
    assert(changes.empty());
    tap(288, 20);
    assert(!opened());
    assert(changes.empty());
    assert(lv_indev_get_group(keyboard) == group);
    drag(292, 6, 290, 80);
    assert(opened());
    tap(117, 80);
    tap(265, 200);
    assert(!opened());
    assert(changes.size() == 1 && changes.back().action == Bluetooth && changes.back().value == 1);
    tap(292, 9);
    assert(opened());
    tap(187, 80);
    assert(state.gpsEnabled);
    const auto before = changes.size();
    drag(270, 130, 270, 70);
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
    // Real pointer hit testing includes the glyph and both clipped fill children.
    tap(292, 9);
    brightness = findSlider(lv_layer_top());
    auto checkWrites = [](size_t start, int saves) {
        int count = 0;
        for (size_t i = start; i < changes.size(); ++i) {
            assert(changes[i].action == Brightness);
            count += changes[i].persist;
        }
        if (count != saves)
            fprintf(stderr, "write check start=%zu end=%zu count=%d expected=%d\n", start, changes.size(), count, saves);
        assert(count == saves);
    };
    for (int y : {166, 136, 106, 76, 45}) {
        const auto start = changes.size();
        tap(272, y);
        assert(opened());
        const int expected = 10 + (166 - y) * 245 / 121;
        assert(abs(lv_slider_get_value(brightness) - expected) <= 3);
        checkWrites(start, 1);
    }
    for (bool up : {true, false}) {
        const auto start = changes.size();
        const int from = up ? 166 : 45;
        const int to = up ? 45 : 166;
        touch(272, from, true);
        for (int step = 1; step <= 8; ++step) {
            const int y = from + (to - from) * step / 8;
            touch(272, y, true);
            assert(opened());
            assert(abs(lv_slider_get_value(brightness) - (10 + (166 - y) * 245 / 121)) <= 1);
            checkWrites(start, 0);
        }
        touch(272, to, false);
        assert(opened());
        assert(state.brightness == (up ? 255 : 10));
        checkWrites(start, 1);
    }
    auto start = changes.size();
    drag(272, 130, 100, 15);
    assert(opened());
    checkWrites(start, 1);
    start = changes.size();
    touch(272, 120, true);
    touch(272, 80, true);
    // Force LVGL's actual press-lost path by removing the object's press lock.
    lv_obj_remove_flag(brightness, LV_OBJ_FLAG_PRESS_LOCK);
    touch(100, 80, true);
    touch(100, 80, false);
    assert(opened());
    checkWrites(start, 1);
    close();
    advance();
    checkWrites(start, 1);
    tap(292, 9);
    brightness = findSlider(lv_layer_top());
    lv_group_focus_obj(brightness);
    start = changes.size();
    key = LV_KEY_RIGHT;
    keyDown = true;
    advance();
    keyDown = false;
    advance();
    checkWrites(start, 1);
    start = changes.size();
    lv_group_set_editing(lv_indev_get_group(encoder), true);
    encoderDiff = -1;
    advance();
    checkWrites(start, 1);
    key = LV_KEY_ESC;
    keyDown = true;
    advance();
    keyDown = false;
    advance();
    assert(!opened());
    assert(lv_indev_get_group(keyboard) == group && lv_indev_get_group(encoder) == group);
    for (int mode = 0; mode < 3; ++mode) {
        tap(292, 9);
        start = changes.size();
        touch(272, 130, true);
        touch(272, 70 + mode * 10, true);
        lv_obj_t *modalDuringDrag = nullptr;
        if (mode == 0)
            state.allowed = false;
        else if (mode == 1)
            lv_screen_load(lv_obj_create(nullptr));
        else {
            modalDuringDrag = lv_obj_create(lv_layer_top());
            lv_obj_set_size(modalDuringDrag, 320, 240);
        }
        advance();
        assert(!opened());
        touch(272, 60, false);
        checkWrites(start, 1);
        assert(lv_indev_get_group(keyboard) == group && lv_indev_get_group(encoder) == group);
        state.allowed = true;
        if (modalDuringDrag)
            lv_obj_delete(modalDuringDrag);
        advance();
    }
    for (auto end : {lv_point_t{240, 9}, lv_point_t{240, 70}, lv_point_t{319, 36}}) {
        drag(292, 9, end.x, end.y);
        assert(!opened());
    }
    state.wifiAvailable = state.bluetoothAvailable = state.gpsAvailable = false;
    tap(292, 9);
    start = changes.size();
    for (int x : {47, 117, 187})
        tap(x, 80);
    assert(changes.size() == start && opened());
    close();
    advance();
    state.wifiAvailable = state.bluetoothAvailable = state.gpsAvailable = true;
    lv_mem_monitor_t memBefore, memOpen, memAfter;
    lv_mem_monitor(&memBefore);
    tap(292, 9);
    lv_mem_monitor(&memOpen);
    printf("Open panel heap delta=%zu bytes\n", memBefore.free_size - memOpen.free_size);
    close();
    advance();
    lv_mem_monitor(&memBefore);
    for (int i = 0; i < 200; ++i) {
        tap(292, 9);
        assert(opened());
        tap(288, 20);
        assert(!opened());
    }
    lv_mem_monitor(&memAfter);
    assert(memAfter.free_size == memBefore.free_size);
    printf("200 cycles: heap before=%zu after=%zu bytes; idle flush delta=0\n", memBefore.total_size - memBefore.free_size,
           memAfter.total_size - memAfter.free_size);
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
