#if defined(VIEW_320x240) || defined(VIEW_240x320)
#include "graphics/view/TFT/GlassUI.h"
#include "fonts.h"
#include <algorithm>
#include <cstdio>
#include <cstring>

namespace GlassUI
{
namespace
{
#include "GlassAssets.inc"
struct Icon {
    const char *name;
    const lv_image_dsc_t *image;
};
const Icon icons[] = {{"Mesh", &imageMesh},         {"Notes", &imageNotes},           {"Gemini", &imageGemini},
                      {"Mail", &imageMail},         {"Chess", &imageChess},           {"Calculator", &imageCalculator},
                      {"Breakout", &imageBreakout}, {"Metronome", &imageMetronome},   {"Files", &imageFiles},
                      {"Maps", &imageMaps},         {"Settings", &imageSettings},     {"Get Apps", &imageGetApps},
                      {"Snake", &imageSnake},       {"Flashlight", &imageFlashlight}, {"Clock", &imageClock},
                      {"Nodes", &imageNodes},       {"Favorites", &imageFavorites},   {"Chats", &imageChats},
                      {"Alerts", &imageAlerts}};
} // namespace
lv_obj_t *battery(lv_obj_t *parent)
{
    lv_obj_t *widget = lv_obj_create(parent);
    lv_obj_remove_style_all(widget);
    lv_obj_remove_flag(widget, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(widget, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_size(widget, 68, 20);
    lv_obj_align(widget, LV_ALIGN_TOP_RIGHT, -6, 0);
    lv_obj_t *label = lv_label_create(widget);
    lv_obj_set_style_text_font(label, &ui_font_montserrat_12, 0);
    lv_obj_set_width(label, 38);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_RIGHT, 0);
    lv_obj_align(label, LV_ALIGN_LEFT_MID, 0, 0);
    lv_obj_t *shell = lv_obj_create(widget);
    lv_obj_remove_style_all(shell);
    lv_obj_remove_flag(shell, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(shell, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_size(shell, 23, 12);
    lv_obj_align(shell, LV_ALIGN_RIGHT_MID, -3, 0);
    lv_obj_set_style_border_width(shell, 1, 0);
    lv_obj_set_style_radius(shell, 3, 0);
    lv_obj_t *fill = lv_obj_create(shell);
    lv_obj_remove_style_all(fill);
    lv_obj_remove_flag(fill, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(fill, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_size(fill, 19, 8);
    lv_obj_align(fill, LV_ALIGN_LEFT_MID, 1, 0);
    lv_obj_set_style_radius(fill, 1, 0);
    lv_obj_t *terminal = lv_obj_create(widget);
    lv_obj_remove_style_all(terminal);
    lv_obj_remove_flag(terminal, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(terminal, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_size(terminal, 2, 5);
    lv_obj_align(terminal, LV_ALIGN_RIGHT_MID, 0, 0);
    lv_obj_set_style_radius(terminal, 1, 0);
    updateBattery(widget, -1, false);
    return widget;
}

void updateBattery(lv_obj_t *widget, int percent, bool plugged, bool light)
{
    lv_obj_t *label = lv_obj_get_child(widget, 0);
    lv_obj_t *shell = lv_obj_get_child(widget, 1);
    lv_obj_t *fill = lv_obj_get_child(shell, 0);
    lv_obj_t *terminal = lv_obj_get_child(widget, 2);
    const int level = std::clamp(percent, 0, 100);
    char text[8];
    if (percent < 0)
        snprintf(text, sizeof(text), "--");
    else
        snprintf(text, sizeof(text), "%d%%", level);
    if (strcmp(lv_label_get_text(label), text))
        lv_label_set_text(label, text);
    const auto ink = lv_color_hex(light ? 0x34455b : 0xffffff);
    const auto color = lv_color_hex(percent < 0   ? (light ? 0x66758a : 0xc2d3e6)
                                    : plugged     ? (light ? 0x167143 : 0x82eba0)
                                    : level <= 15 ? 0xff453a
                                                  : (light ? 0x34455b : 0xffffff));
    if (!lv_color_eq(lv_obj_get_style_text_color(label, 0), color))
        lv_obj_set_style_text_color(label, color, 0);
    if (!lv_color_eq(lv_obj_get_style_border_color(shell, 0), ink))
        lv_obj_set_style_border_color(shell, ink, 0);
    if (!lv_color_eq(lv_obj_get_style_bg_color(terminal, 0), ink))
        lv_obj_set_style_bg_color(terminal, ink, 0);
    if (!lv_color_eq(lv_obj_get_style_bg_color(fill, 0), color))
        lv_obj_set_style_bg_color(fill, color, 0);
    const int width = std::max(1, level * 19 / 100);
    if (lv_obj_get_style_width(fill, 0) != width)
        lv_obj_set_width(fill, width);
    const lv_opa_t opacity = percent < 0 ? LV_OPA_TRANSP : LV_OPA_COVER;
    if (lv_obj_get_style_bg_opa(fill, 0) != opacity)
        lv_obj_set_style_bg_opa(fill, opacity, 0);
    if (lv_obj_get_style_bg_opa(terminal, 0) != LV_OPA_COVER)
        lv_obj_set_style_bg_opa(terminal, LV_OPA_COVER, 0);
}

void wallpaper(lv_obj_t *screen)
{
    lv_obj_set_style_bg_image_src(screen, &imageWallpaper, 0);
    lv_obj_set_style_bg_color(screen, lv_color_hex(0x497fba), 0);
    lv_obj_set_style_pad_all(screen, 0, 0);
    lv_obj_set_style_border_width(screen, 0, 0);
}
void surface(lv_obj_t *obj, int radius)
{
    lv_obj_set_style_bg_color(obj, lv_color_hex(0xe3f2ff), 0);
    lv_obj_set_style_bg_opa(obj, 45, 0);
    lv_obj_set_style_border_color(obj, lv_color_white(), 0);
    lv_obj_set_style_border_opa(obj, 85, 0);
    lv_obj_set_style_border_width(obj, 1, 0);
    lv_obj_set_style_radius(obj, radius, 0);
    lv_obj_set_style_shadow_width(obj, 0, 0);
    lv_obj_set_style_pad_all(obj, 0, 0);
    lv_obj_set_style_text_font(obj, &ui_font_montserrat_12, 0);
    lv_obj_set_style_text_color(obj, lv_color_white(), 0);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_outline_color(obj, lv_color_white(), LV_STATE_FOCUS_KEY);
    lv_obj_set_style_outline_width(obj, 2, LV_STATE_FOCUS_KEY);
    lv_obj_set_style_outline_pad(obj, 2, LV_STATE_FOCUS_KEY);
}
void appIcon(lv_obj_t *parent, const char *name)
{
    const lv_image_dsc_t *source = &imageApp;
    for (const auto &icon : icons)
        if (!strcmp(icon.name, name)) {
            source = icon.image;
            break;
        }
    lv_obj_t *image = lv_image_create(parent);
    lv_image_set_src(image, source);
    lv_obj_align(image, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_remove_flag(image, LV_OBJ_FLAG_CLICKABLE);
}
void symbol(lv_obj_t *parent, const char *name, int x, int y)
{
    const lv_image_dsc_t *source = !strcmp(name, "Wifi")        ? &imageWifi
                                   : !strcmp(name, "Bluetooth") ? &imageBluetooth
                                   : !strcmp(name, "Gps")       ? &imageGps
                                                                : &imageSun;
    lv_obj_t *image = lv_image_create(parent);
    lv_image_set_src(image, source);
    lv_obj_set_style_image_recolor(image, lv_color_white(), 0);
    lv_obj_set_style_image_recolor_opa(image, LV_OPA_COVER, 0);
    lv_obj_set_pos(image, x, y);
    lv_obj_remove_flag(image, LV_OBJ_FLAG_CLICKABLE);
}
void settingsSections(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_hex(0xedf1f7), 0);
    lv_obj_set_style_text_color(screen, lv_color_hex(0x23334a), 0);
    const int sections[][2] = {{68, 88}, {188, 114}, {330, 244}, {604, 60}, {704, 76}, {812, 458}};
    for (const auto &section : sections) {
        lv_obj_t *card = lv_obj_create(screen);
        lv_obj_remove_style_all(card);
        lv_obj_set_pos(card, 8, section[0]);
        lv_obj_set_size(card, 304, section[1]);
        lv_obj_set_style_bg_color(card, lv_color_white(), 0);
        lv_obj_set_style_bg_opa(card, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(card, 18, 0);
        lv_obj_remove_flag(card, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_remove_flag(card, LV_OBJ_FLAG_SCROLLABLE);
    }
}
void settingsFinish(lv_obj_t *screen)
{
    for (uint32_t i = 0; i < lv_obj_get_child_count(screen); ++i) {
        lv_obj_t *obj = lv_obj_get_child(screen, i);
        if (lv_obj_check_type(obj, &lv_label_class)) {
            const bool inButton = lv_obj_check_type(lv_obj_get_parent(obj), &lv_button_class);
            lv_obj_set_style_text_color(obj, lv_color_hex(inButton ? 0x1769c2 : 0x34455b), 0);
        } else if (lv_obj_check_type(obj, &lv_button_class)) {
            lv_obj_set_style_radius(obj, LV_RADIUS_CIRCLE, 0);
            lv_obj_set_style_bg_color(obj, lv_color_hex(0xe8f1ff), 0);
            lv_obj_set_style_text_color(obj, lv_color_hex(0x1769c2), 0);
            lv_obj_set_style_border_width(obj, 0, 0);
            lv_obj_set_style_shadow_width(obj, 0, 0);
        }
        settingsFinish(obj);
    }
}
} // namespace GlassUI
#endif
