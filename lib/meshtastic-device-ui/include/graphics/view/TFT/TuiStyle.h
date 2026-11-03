#pragma once
#include "lvgl.h"
#include <cstring>

namespace Tui {
constexpr uint32_t Background = 0x0b1118;
constexpr uint32_t Surface = 0x17232e;
constexpr uint32_t Border = 0x304352;
constexpr uint32_t Text = 0xeaf2f6;
constexpr uint32_t Muted = 0xa2b4c2;
constexpr uint32_t Accent = 0x62dfc4;

inline void setText(lv_obj_t *label, const char *text)
{
    if (strcmp(lv_label_get_text(label), text) != 0)
        lv_label_set_text(label, text);
}

inline void styleTile(lv_obj_t *tile) {
  static lv_style_t normal, pressed, focused;
  static bool initialized = false;
  if (!initialized) {
    initialized = true;
    lv_style_init(&normal);
    lv_style_set_bg_color(&normal, lv_color_hex(Surface));
    lv_style_set_bg_opa(&normal, LV_OPA_COVER);
    lv_style_set_radius(&normal, 12);
    lv_style_set_border_width(&normal, 1);
    lv_style_set_border_color(&normal, lv_color_hex(Border));
    lv_style_set_pad_all(&normal, 0);
    lv_style_set_text_color(&normal, lv_color_hex(Text));
    lv_style_init(&pressed);
    lv_style_set_bg_color(&pressed, lv_color_hex(0x294c54));
    lv_style_set_border_color(&pressed, lv_color_hex(Accent));
    lv_style_init(&focused);
    lv_style_set_outline_width(&focused, 2);
    lv_style_set_outline_pad(&focused, 2);
    lv_style_set_outline_color(&focused, lv_color_hex(Accent));
  }
  lv_obj_remove_style_all(tile);
  lv_obj_add_style(tile, &normal, LV_PART_MAIN);
  lv_obj_add_style(tile, &pressed, LV_STATE_PRESSED);
  lv_obj_add_style(tile, &focused, LV_STATE_FOCUSED);
}

inline void headerTitle(lv_obj_t *label) {
  lv_obj_set_size(label, 152, 28);
  lv_obj_set_style_text_font(label, &ui_font_montserrat_14, 0);
  lv_obj_set_style_text_color(label, lv_color_hex(Text), 0);
  lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_set_style_pad_top(label, 5, 0);
  lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
  lv_obj_align(label, LV_ALIGN_TOP_MID, 0, 4);
}

inline void headerButton(lv_obj_t *button) {
  styleTile(button);
  lv_obj_set_size(button, 64, 28);
  lv_obj_set_style_radius(button, 8, 0);
  lv_obj_set_style_text_font(button, &ui_font_montserrat_14, 0);
}
} // namespace Tui
