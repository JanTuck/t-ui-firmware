// -----------------------------------------------------------------------------
// The persistent top bar. See TuiStatusBar.h for the design and why it is opt-in.
//
// THREADING. Everything here runs on the "tft" task: tui_statusbar_init() from screen setup,
// tui_statusbar_tick() from the existing poll timer. Nothing here touches the SD card or the
// radio, so it takes no locks and cannot stall either.
// -----------------------------------------------------------------------------
#include "graphics/view/TFT/TuiStatusBar.h"

#include "graphics/view/TFT/GlassUI.h"
#include "ui.h" // ui_font_montserrat_12
#include <cstdio>
#include <cstring>

extern "C" void notif_open(void);
extern "C" int notif_count(void);
// The battery figures the launcher already keeps, so the bar and the launcher can never
// disagree about what is left (src/TDeckBatteryBridge is not a thing - these come from the
// view, through a shim, for the same reason every other bridge here does).
extern "C" int tdeck_battery_pct(void);
extern "C" bool tdeck_battery_plugged(void);
extern "C" bool tdeck_clock_text(char *out, int outN); // "9:41 AM" / "21:41", false if unknown

namespace
{
lv_obj_t *bar = nullptr;
lv_obj_t *notifLbl = nullptr;
lv_obj_t *clockLbl = nullptr;
lv_obj_t *batWidget = nullptr;

// Screens that asked for the bar. Sixteen is far more than this UI has; anything past that
// simply does not get the bar rather than overwriting somebody else's entry.
const int kMaxScreens = 16;
lv_obj_t *wanted[kMaxScreens] = {nullptr};
int wantedN = 0;

bool wantsBar(lv_obj_t *scr)
{
    for (int i = 0; i < wantedN; i++)
        if (wanted[i] == scr)
            return true;
    return false;
}

void setText(lv_obj_t *label, const char *text)
{
    if (strcmp(lv_label_get_text(label), text))
        lv_label_set_text(label, text);
}
} // namespace

void tui_statusbar_init(void)
{
    if (bar)
        return;
    bar = lv_obj_create(lv_layer_top());
    lv_obj_remove_style_all(bar);
    lv_obj_set_size(bar, 320, 20);
    lv_obj_align(bar, LV_ALIGN_TOP_LEFT, 0, 0);
    lv_obj_set_style_bg_color(bar, lv_color_hex(0x294768), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_clear_flag(bar, LV_OBJ_FLAG_SCROLLABLE);
    // A hairline, so the bar reads as chrome rather than as part of the screen under it.
    lv_obj_set_style_border_side(bar, LV_BORDER_SIDE_BOTTOM, LV_PART_MAIN);
    lv_obj_set_style_border_color(bar, lv_color_hex(0x30415a), LV_PART_MAIN);
    lv_obj_set_style_border_width(bar, 0, LV_PART_MAIN);
    lv_obj_add_flag(bar, LV_OBJ_FLAG_HIDDEN);

    notifLbl = lv_label_create(bar);
    lv_obj_set_style_text_font(notifLbl, &ui_font_montserrat_12, LV_PART_MAIN);
    lv_label_set_text(notifLbl, "Notifications");
    lv_obj_align(notifLbl, LV_ALIGN_LEFT_MID, 6, 0);
    // The label itself is the button - a real lv_btn would not fit in 20px with its padding,
    // and there is nothing else up here to mis-tap. The hit area is widened below.
    lv_obj_add_flag(notifLbl, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_ext_click_area(notifLbl, 8);
    lv_obj_add_event_cb(
        notifLbl,
        // Deferred: this handler belongs to a label on the top layer, and opening the page
        // changes the screen underneath it.
        [](lv_event_t *) { lv_async_call([](void *) { notif_open(); }, nullptr); }, LV_EVENT_CLICKED, nullptr);

    clockLbl = lv_label_create(bar);
    lv_obj_set_style_text_font(clockLbl, &ui_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_style_text_color(clockLbl, lv_color_hex(0xffffff), LV_PART_MAIN);
    lv_label_set_text(clockLbl, "");
    lv_obj_align(clockLbl, LV_ALIGN_CENTER, 0, 0);

    batWidget = GlassUI::battery(bar);
}

// ⛔ A DELETED SCREEN MUST LEAVE THE LIST. Chess and Gemini delete their screens a few seconds
// after you leave them (to give the memory back) and build new ones when you return - and each new
// one registered here while the old entry stayed. After ~16 visits in one boot the list was full,
// and the next chess screen got neither the bar nor its 20px of top padding: found by a 51-minute
// stress test (2026-09-30), where chess came back with no bar and everything shifted up.
static void onReservedScreenDeleted(lv_event_t *e)
{
    lv_obj_t *scr = (lv_obj_t *)lv_event_get_current_target(e);
    for (int i = 0; i < wantedN; i++) {
        if (wanted[i] == scr) {
            wanted[i] = wanted[--wantedN];
            wanted[wantedN] = nullptr;
            return;
        }
    }
}

void tui_statusbar_reserve(lv_obj_t *screen)
{
    if (!screen || wantedN >= kMaxScreens || wantsBar(screen))
        return;
    wanted[wantedN++] = screen;
    lv_obj_add_event_cb(screen, onReservedScreenDeleted, LV_EVENT_DELETE, nullptr);
    // The whole trick: LVGL aligns children to the parent's CONTENT area, so padding the
    // screen moves every TOP_*-aligned child down by 20px without touching any of them.
    // BOTTOM_*-aligned children are unaffected, which is what we want for a bar at the top.
    lv_obj_set_style_pad_top(screen, 20, LV_PART_MAIN);
}

void tui_statusbar_tick(void)
{
    if (!bar)
        return;

    lv_obj_t *scr = lv_screen_active();
    const bool show = wantsBar(scr);
    const bool hidden = lv_obj_has_flag(bar, LV_OBJ_FLAG_HIDDEN);
    if (show == hidden) { // state changed
        if (show)
            lv_obj_clear_flag(bar, LV_OBJ_FLAG_HIDDEN);
        else
            lv_obj_add_flag(bar, LV_OBJ_FLAG_HIDDEN);
    }
    if (!show)
        return; // nothing on screen to keep up to date

    // Overlays (the pins list, rename, share) are full-screen objects on this same layer and
    // are created after us, so they sit on top. Keeping the bar in front of them would cover
    // their own Close buttons, so it deliberately stays behind - it is chrome, not a modal.

    const bool light = lv_color_luminance(lv_obj_get_style_bg_color(scr, LV_PART_MAIN)) > 190;
    const uint32_t ink = light ? 0x34455b : 0xffffff;
    static int lastLight = -1;
    if (lastLight != light) {
        lastLight = light;
        lv_obj_set_style_bg_color(bar, lv_color_hex(light ? 0xedf1f7 : 0x294768), 0);
        lv_obj_set_style_text_color(clockLbl, lv_color_hex(ink), 0);
    }
    char buf[24];
    const int unread = notif_count();
    if (unread == 0)
        snprintf(buf, sizeof(buf), "Notifications");
    else if (unread == 1)
        snprintf(buf, sizeof(buf), "1 msg");
    else
        snprintf(buf, sizeof(buf), "%d msgs", unread);
    // LVGL 9.3 reallocates and redraws unchanged label text; update only changed values.
    static uint32_t lastNotifCol = 0xFFFFFFFF;
    setText(notifLbl, buf);
    const uint32_t notifCol = unread ? (light ? 0x167143 : 0x9bffc5) : ink;
    if (notifCol != lastNotifCol) {
        lastNotifCol = notifCol;
        lv_obj_set_style_text_color(notifLbl, lv_color_hex(notifCol), LV_PART_MAIN);
    }

    if (tdeck_clock_text(buf, sizeof(buf)))
        setText(clockLbl, buf);
    else
        setText(clockLbl, "");

    GlassUI::updateBattery(batWidget, tdeck_battery_pct(), tdeck_battery_plugged(), light);
}
