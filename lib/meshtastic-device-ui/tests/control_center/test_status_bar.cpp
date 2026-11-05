#include "graphics/view/TFT/GlassUI.h"
#include "graphics/view/TFT/TuiStatusBar.h"
#include <cassert>
#include <cstdio>
#include <cstring>

namespace
{
int unread = 0, battery = 84;
bool plugged = false;
const char *clockText = "9:41";
unsigned flushes;
void advance(int ms)
{
    for (int i = 0; i < ms; i += 10) {
        lv_tick_inc(10);
        tui_statusbar_tick();
        lv_timer_handler();
    }
}
bool hasText(lv_obj_t *root, const char *text)
{
    if (lv_obj_check_type(root, &lv_label_class) && !strcmp(lv_label_get_text(root), text))
        return true;
    for (uint32_t i = 0; i < lv_obj_get_child_count(root); ++i)
        if (hasText(lv_obj_get_child(root, i), text))
            return true;
    return false;
}
} // namespace
extern "C" void notif_open() {}
extern "C" int notif_count()
{
    return unread;
}
extern "C" int tdeck_battery_pct()
{
    return battery;
}
extern "C" bool tdeck_battery_plugged()
{
    return plugged;
}
extern "C" bool tdeck_clock_text(char *out, int size)
{
    snprintf(out, size, "%s", clockText ? clockText : "");
    return clockText != nullptr;
}
int main()
{
    lv_init();
    auto *display = lv_display_create(320, 240);
    static uint8_t buffer[320 * 240 * 4];
    lv_display_set_buffers(display, buffer, nullptr, sizeof(buffer), LV_DISPLAY_RENDER_MODE_FULL);
    lv_display_set_flush_cb(display, [](lv_display_t *d, const lv_area_t *, uint8_t *) {
        ++flushes;
        lv_display_flush_ready(d);
    });
    tui_statusbar_init();
    tui_statusbar_reserve(lv_screen_active());
    advance(300);
    assert(hasText(lv_layer_top(), "Notifications") && hasText(lv_layer_top(), "9:41") && hasText(lv_layer_top(), "84%"));
    const unsigned idleFlushes = flushes;
    advance(500);
    assert(flushes == idleFlushes);
    unread = 2;
    battery = 15;
    plugged = true;
    clockText = "9:42";
    advance(100);
    assert(flushes > idleFlushes);
    assert(hasText(lv_layer_top(), "2 msgs") && hasText(lv_layer_top(), "9:42") && hasText(lv_layer_top(), "15%"));
    battery = -1;
    clockText = nullptr;
    unread = 1;
    advance(100);
    assert(hasText(lv_layer_top(), "--") && hasText(lv_layer_top(), "1 msg"));
    assert(!hasText(lv_layer_top(), "9:42"));
    auto *widget = GlassUI::battery(lv_screen_active());
    const int levels[] = {-1, 0, 9, 84, 100, 150};
    const char *expected[] = {"--", "0%", "9%", "84%", "100%", "100%"};
    for (unsigned i = 0; i < sizeof(levels) / sizeof(levels[0]); ++i) {
        GlassUI::updateBattery(widget, levels[i], i % 2, i % 2);
        lv_obj_update_layout(widget);
        assert(hasText(widget, expected[i]));
        lv_area_t bounds;
        lv_obj_get_coords(widget, &bounds);
        assert(bounds.x2 == 313);
        for (uint32_t child = 0; child < lv_obj_get_child_count(widget); ++child) {
            lv_area_t area;
            lv_obj_get_coords(lv_obj_get_child(widget, child), &area);
            assert(area.x1 >= bounds.x1 && area.x2 <= bounds.x2);
            assert(area.y1 >= bounds.y1 && area.y2 <= bounds.y2);
        }
    }
    puts("Status bar: unchanged state causes no redraws; notification, clock and battery changes refresh correctly");
}
