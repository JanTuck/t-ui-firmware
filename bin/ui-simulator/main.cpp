#include "graphics/view/TFT/Themes.h"
#include "graphics/view/TFT/TuiLabel.h"
#include "graphics/view/TFT/TuiStatusBar.h"
#include "graphics/view/TFT/TuiStyle.h"
#include "lvgl.h"
#include "screens.h"
#include "styles.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
extern "C" const lv_font_t ui_font_montserrat_12;
#include "icons.inc"

extern "C" void calculator_open();
extern "C" void stopwatch_open();
extern "C" void notes_open();
extern "C" void notif_open() {}
extern "C" int notif_count() { return 0; }
extern "C" int tdeck_battery_pct() { return 84; }
extern "C" bool tdeck_battery_plugged() { return false; }
extern "C" bool tdeck_clock_text(char *out, int n) {
  snprintf(out, n, "21:41");
  return true;
}
void playBeep() {}
void playLongBeep() {}
extern "C" void tdeck_beep_gain(float) {}
extern "C" void tdeck_alarm_get(int *h, int *m, bool *on) {
  *h = 7;
  *m = 0;
  *on = false;
}
extern "C" void tdeck_alarm_set(int, int, bool) {}
extern "C" bool tdeck_alarm_ringing() { return false; }
extern "C" void tdeck_alarm_dismiss() {}
static uint16_t pixels[320 * 240], buffer[320 * 24];
static bool baseline = false;
static int flushes = 0, clicked = -1, held = -1;
static lv_point_t pointer;
static bool down = false;
static void flush(lv_display_t *display, const lv_area_t *a, uint8_t *data) {
  auto src = reinterpret_cast<uint16_t *>(data);
  for (int y = a->y1; y <= a->y2; ++y)
    for (int x = a->x1; x <= a->x2; ++x)
      pixels[y * 320 + x] = *src++;
  ++flushes;
  lv_display_flush_ready(display);
}
static void step(int ms = 100) {
  for (int i = 0; i < ms; i += 5) {
    lv_tick_inc(5);
    if (lv_tick_get() % 60 == 0)
      tui_statusbar_tick();
    lv_timer_handler();
  }
}
static void capture(const char *name) {
  lv_refr_now(nullptr);
  char path[96];
  snprintf(path, sizeof(path), "%s%s", baseline ? "baseline-" : "", name);
  FILE *f = fopen(path, "wb");
  assert(f);
  fprintf(f, "P6\n320 240\n255\n");
  for (uint16_t c : pixels) {
    unsigned char rgb[] = {
        static_cast<unsigned char>(((c >> 11) & 31) * 255 / 31),
        static_cast<unsigned char>(((c >> 5) & 63) * 255 / 63),
        static_cast<unsigned char>((c & 31) * 255 / 31)};
    fwrite(rgb, 1, 3, f);
  }
  fclose(f);
}
static void readPointer(lv_indev_t *, lv_indev_data_t *data) {
  data->point = pointer;
  data->state = down ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
}
struct App {
  const char *name;
  uint32_t color;
  int userIdx = -1;
};
static App launchList[] = {
    {"Mesh", 0xbf5af2},      {"Notes", 0xffd60a},
    {"Gemini", 0x30d158},    {"Mail", 0xff9f0a},
    {"Chess", 0xf2f2f2},     {"Calculator", 0xff9f0a},
    {"Files", 0x62dfc4},     {"Maps", 0x5ac8fa},
    {"Settings", 0xa2b4c2},  {"Get Apps", 0xbf5af2},
    {"Snake", 0x30d158},     {"Flashlight", 0xffd60a},
    {"Clock", 0x64d2ff},     {"Nodes", 0x5ac8fa},
    {"Favorites", 0xffd60a}, {"Chats", 0x30d158},
    {"Alerts", 0xff453a},    {"An unusually long app name", 0x62dfc4}};
static const char *userAppDirs[] = {""};
static lv_obj_t *makeGrid(lv_obj_t *screen) {
  constexpr int kPageW = 320, kPagerH = 188, kPerPage = 6;
  const int launchCount = sizeof(launchList) / sizeof(launchList[0]);
  lv_obj_t *pager = lv_obj_create(screen);
  lv_obj_remove_style_all(pager);
  lv_obj_set_size(pager, kPageW, kPagerH);
  lv_obj_set_pos(pager, 0, 26);
  lv_obj_set_flex_flow(pager, LV_FLEX_FLOW_ROW);
  lv_obj_set_scroll_dir(pager, LV_DIR_HOR);
  lv_obj_set_scroll_snap_x(pager, LV_SCROLL_SNAP_CENTER);
  lv_obj_add_flag(pager, LV_OBJ_FLAG_SCROLL_ONE);
  lv_obj_set_scrollbar_mode(pager, LV_SCROLLBAR_MODE_OFF);
  auto tile_cb = [](lv_event_t *e) {
    clicked = (int)(intptr_t)lv_event_get_user_data(e);
  };
  auto tile_long_cb = [](lv_event_t *) { held = 1; };
#include "grid.inc"
  return pager;
}
static size_t used() {
  lv_mem_monitor_t m;
  lv_mem_monitor(&m);
  return m.total_size - m.free_size;
}
static lv_obj_t *findLabel(lv_obj_t *obj, const char *text) {
  if (lv_obj_has_flag(obj, LV_OBJ_FLAG_HIDDEN))
    return nullptr;
  if (lv_obj_check_type(obj, &lv_label_class) &&
      !strcmp(lv_label_get_text(obj), text))
    return obj;
  for (uint32_t i = 0; i < lv_obj_get_child_count(obj); ++i)
    if (auto found = findLabel(lv_obj_get_child(obj, i), text))
      return found;
  return nullptr;
}
static void tapObject(lv_obj_t *button) {
  lv_area_t a;
  lv_obj_get_coords(button, &a);
  assert(a.x1 >= 0 && a.x2 < 320 && a.y1 >= 0 && a.y2 < 240);
  pointer = {(lv_coord_t)((a.x1 + a.x2) / 2), (lv_coord_t)((a.y1 + a.y2) / 2)};
  down = true;
  step(60);
  down = false;
  step(60);
}
static void tap(const char *text) {
  auto label = findLabel(lv_layer_top(), text);
  if (!label)
    label = findLabel(lv_screen_active(), text);
  assert(label);
  tapObject(lv_obj_get_parent(label));
}
static void separate(lv_obj_t *a, lv_obj_t *b) {
  lv_area_t x, y;
  lv_obj_get_coords(a, &x);
  lv_obj_get_coords(b, &y);
  bool disjoint = x.x2 < y.x1 || y.x2 < x.x1 || x.y2 < y.y1 || y.y2 < x.y1;
  if (!disjoint)
    fprintf(stderr, "Overlap: %s and %s\n",
            lv_obj_check_type(a, &lv_label_class) ? lv_label_get_text(a)
                                                  : "widget",
            lv_obj_check_type(b, &lv_label_class) ? lv_label_get_text(b)
                                                  : "widget");
  if (!disjoint)
    fprintf(stderr, "Bounds: %d,%d-%d,%d and %d,%d-%d,%d\n", x.x1, x.y1, x.x2,
            x.y2, y.x1, y.y1, y.x2, y.y2);
  assert(disjoint);
}
static void collectLabels(lv_obj_t *obj, std::vector<lv_obj_t *> &labels) {
  if (lv_obj_has_flag(obj, LV_OBJ_FLAG_HIDDEN))
    return;
  if (lv_obj_check_type(obj, &lv_label_class) && *lv_label_get_text(obj))
    labels.push_back(obj);
  for (uint32_t i = 0; i < lv_obj_get_child_count(obj); ++i)
    collectLabels(lv_obj_get_child(obj, i), labels);
}
static void checkDialog(lv_obj_t *dialog) {
  std::vector<lv_obj_t *> labels;
  collectLabels(dialog, labels);
  for (size_t i = 0; i < labels.size(); ++i) {
    lv_area_t a, parent;
    lv_obj_get_coords(labels[i], &a);
    lv_obj_get_coords(dialog, &parent);
    assert(a.x1 >= parent.x1 && a.x2 <= parent.x2 && a.y1 >= parent.y1 &&
           a.y2 <= parent.y2);
    for (size_t j = 0; j < i; ++j)
      separate(labels[i], labels[j]);
  }
}
extern "C" void nodes_open();
extern "C" void favorites_open();
extern "C" void channels_open();
static void shellScreens() {
  lv_obj_t *settings_screen = nullptr;
  struct {
    struct {
      int screen_brightness = 153;
    } uiConfig;
    struct {
      struct {
        bool wifi_enabled = false;
      } network;
    } config;
  } db;
  bool gpsEnabled = true;
  lv_obj_t *gps_switch, *loc_precision_label, *wifi_net_btn_lbl, *wifi_switch,
      *wifi_status_label;
  lv_obj_t *timeout_btn_label, *mute_switch, *channel_import_label;
  lv_obj_t *settings_tb_speed_row, *settings_tb_speed_label,
      *settings_tb_style_row, *settings_tb_style_label, *settings_tb_hint;
  lv_obj_t *share_now_hint, *shot_btn, *shot_btn_label, *shot_hint_label;
  bool fixtureCursor = true;
  auto updateTrackballRows = [&]() {
#include "trackball.inc"
  };
#include "settings.inc"
  lv_screen_load(settings_screen);
  step();
  if (!baseline) {
    separate(findLabel(settings_screen, "Settings"),
             lv_obj_get_parent(findLabel(settings_screen, "Back")));
    separate(findLabel(settings_screen, "Lock screen"),
             lv_obj_get_parent(findLabel(settings_screen, "Open")));
  }
  capture("settings-display.ppm");
  if (!baseline) {
    for (uint32_t i = 0; i < lv_obj_get_child_count(settings_screen); ++i) {
      auto child = lv_obj_get_child(settings_screen, i);
      if (lv_obj_has_flag(child, LV_OBJ_FLAG_HIDDEN))
        continue;
      if (lv_obj_check_type(child, &lv_label_class) &&
          !*lv_label_get_text(child))
        continue;
      for (uint32_t j = 0; j < i; ++j) {
        auto other = lv_obj_get_child(settings_screen, j);
        if (lv_obj_has_flag(other, LV_OBJ_FLAG_HIDDEN))
          continue;
        if (lv_obj_check_type(other, &lv_label_class) &&
            !*lv_label_get_text(other))
          continue;
        separate(child, other);
      }
    }
    std::vector<lv_obj_t *> labels;
    collectLabels(settings_screen, labels);
    for (size_t i = 0; i < labels.size(); ++i)
      for (size_t j = 0; j < i; ++j)
        separate(labels[i], labels[j]);
  }
  const int positions[] = {164, 308, 496, 680, 786, 960, 1136};
  const char *names[] = {"settings-location.ppm", "settings-network.ppm",
                         "settings-sound.ppm",    "settings-mesh.ppm",
                         "settings-system.ppm",   "settings-cursor.ppm",
                         "settings-tools.ppm"};
  for (int i = 0; i < 7; ++i) {
    lv_obj_scroll_to_y(settings_screen, positions[i], LV_ANIM_OFF);
    step();
    capture(names[i]);
  }

  fixtureCursor = false;
  updateTrackballRows();
  lv_obj_scroll_to_y(settings_screen, 960, LV_ANIM_OFF);
  step();
  if (!baseline) {
    assert(lv_obj_has_flag(settings_tb_speed_row, LV_OBJ_FLAG_HIDDEN));
    separate(settings_tb_hint, shareNowBtn);
  }
  capture("settings-cursor-off.ppm");
#include "settings-messages.inc"
  lv_label_set_text(share_now_hint, gpsError);
  lv_obj_scroll_to_y(settings_screen, 1136, LV_ANIM_OFF);
  step();
  if (!baseline)
    separate(share_now_hint, shot_btn);
  capture("settings-location-error.ppm");
  lv_obj_scroll_to_y(settings_screen, 786, LV_ANIM_OFF);
  step();
  tapObject(tzDd);
  if (!baseline)
    assert(lv_dropdown_is_open(tzDd));
  capture("settings-zones.ppm");
  if (!baseline) {
    auto list = lv_dropdown_get_list(tzDd);
    lv_obj_scroll_to_y(list, 0, LV_ANIM_OFF);
    step();
    auto options = lv_obj_get_child(list, 0);
    lv_area_t bounds;
    lv_obj_get_coords(options, &bounds);
    const auto font = lv_obj_get_style_text_font(options, LV_PART_MAIN);
    int line = lv_font_get_line_height(font) +
               lv_obj_get_style_text_line_space(options, LV_PART_MAIN);
    pointer = {(lv_coord_t)(bounds.x1 + 20),
               (lv_coord_t)(bounds.y1 + line + line / 2)};
    down = true;
    step(60);
    down = false;
    step(60);
    assert(lv_dropdown_get_selected(tzDd) == 1);
    assert(!lv_dropdown_is_open(tzDd));
  }
  lv_dropdown_close(tzDd);
  step();
  if (!baseline) {
    lv_obj_scroll_to_y(settings_screen, 164, LV_ANIM_OFF);
    step();
    tapObject(gps_switch);
    assert(!lv_obj_has_state(gps_switch, LV_STATE_CHECKED));
    tapObject(gps_switch);
    assert(lv_obj_has_state(gps_switch, LV_STATE_CHECKED));
    lv_obj_scroll_to_y(settings_screen, 0, LV_ANIM_OFF);
    step();
    lv_area_t slider;
    lv_obj_get_coords(briSlider, &slider);
    pointer = {(lv_coord_t)(slider.x1 + 20),
               (lv_coord_t)((slider.y1 + slider.y2) / 2)};
    down = true;
    step(60);
    pointer.x = slider.x2 - 10;
    step(60);
    down = false;
    step(60);
    assert(lv_slider_get_value(briSlider) > 200);
  }
  lv_obj_t *lockpad_screen = nullptr, *lock_title_label = nullptr;
  lv_obj_t *lockpad_unread_label = nullptr, *lock_digits_label = nullptr;
#include "lockpad.inc"
  lv_label_set_text(lock_title_label, "Enter PIN");
  lv_label_set_text(lockpad_unread_label, "12 msgs");
  lv_label_set_text(lock_digits_label, "****");
  lv_screen_load(lockpad_screen);
  step();
  if (!baseline) {
    separate(lock_title_label, lockpad_unread_label);
    separate(lock_digits_label, pad);
  }
  capture("pin-pad.ppm");
#include "pin-messages.inc"
  for (size_t i = 0; i < sizeof(pinMessages) / sizeof(pinMessages[0]); ++i) {
    lv_label_set_text(lock_title_label, pinMessages[i]);
    step();
    if (!baseline) {
      separate(lock_title_label, lockpad_unread_label);
      separate(lock_title_label, lock_digits_label);
    }
    capture(i == 0 ? "pin-too-short.ppm" : "pin-wrong.ppm");
  }

  if (!baseline) {
    lv_area_t bounds;
    lv_obj_get_coords(pad, &bounds);
    for (int row = 0; row < 4; ++row)
      for (int col = 0; col < 3; ++col) {
        pointer = {(lv_coord_t)(bounds.x1 + 4 + 48 + col * 104),
                   (lv_coord_t)(bounds.y1 + 4 + 18 + row * 44)};
        down = true;
        step(60);
        assert(lv_buttonmatrix_get_selected_button(pad) ==
               (uint32_t)(row * 3 + col));
        down = false;
        step(60);
      }
  }
}
static void gallery(lv_obj_t *home) {
  lv_screen_load(home);
  step();
  calculator_open();
  step();
  tap("C");
  capture("calculator.ppm");
  lv_screen_load(home);
  step();
  stopwatch_open();
  step();
  capture("clock.ppm");
  tap("Timer");
  step();
  capture("timer.ppm");
  tap("Alarm");
  step();
  capture("alarm.ppm");
  lv_screen_load(home);
  step();
  notes_open();
  step();
  capture("notes.ppm");
  tap("+ New");
  step();
  capture("note-editor.ppm");
  tap("Delete");
  step();
  if (!baseline)
    checkDialog(
        lv_obj_get_parent(findLabel(lv_screen_active(), "Delete this note?")));
  capture("note-delete.ppm");
  lv_screen_load(home);
  step();
  nodes_open();
  step();
  capture("nodes.ppm");
  auto row = lv_obj_get_parent(findLabel(lv_screen_active(), "Trail base"));
  auto more = lv_obj_get_child(row, lv_obj_get_child_count(row) - 1);
  tapObject(more);
  step();
  if (!baseline)
    checkDialog(lv_obj_get_parent(
        lv_obj_get_parent(findLabel(lv_layer_top(), "Close"))));
  capture("node-actions.ppm");
  if (baseline) {
    lv_obj_send_event(lv_obj_get_parent(findLabel(lv_layer_top(), "Close")),
                      LV_EVENT_CLICKED, nullptr);
    step();
  } else {
    tap("Close");
  }
  lv_screen_load(home);
  step();
  favorites_open();
  step();
  auto favorite = findLabel(lv_screen_active(), "Trail base");
  assert(favorite);
  lv_area_t favoriteArea;
  lv_obj_get_coords(favorite, &favoriteArea);
  if (!baseline)
    assert(favoriteArea.y1 >= 60 && favoriteArea.y2 < 240);
  capture("favorites.ppm");
  lv_screen_load(home);
  step();
  channels_open();
  step();
  capture("chats.ppm");
  create_screen_main_screen();
  Themes::set(Themes::eDark);
  Themes::initStyles();
  auto tabs = lv_tabview_get_tab_bar(objects.controller_tab_view);
  for (uint32_t i = 0; i < lv_obj_get_child_count(tabs); ++i) {
    auto button = lv_obj_get_child(tabs, i);
    lv_obj_add_style(button, &style_btn_default, LV_STATE_DEFAULT);
    lv_obj_add_style(button, &style_btn_active, LV_STATE_CHECKED);
    lv_obj_add_style(button, &style_btn_pressed, LV_STATE_PRESSED);
  }
  lv_screen_load(objects.main_screen);
  step();
  capture("mesh.ppm");
  lv_obj_add_flag(objects.home_panel, LV_OBJ_FLAG_HIDDEN);
  lv_obj_remove_flag(objects.controller_panel, LV_OBJ_FLAG_HIDDEN);
  step();
  capture("mesh-settings.ppm");
  if (!baseline)
    separate(lv_tabview_get_content(objects.controller_tab_view), tabs);
  tap("Tools");
  if (!baseline)
    assert(lv_tabview_get_tab_active(objects.controller_tab_view) == 1);
  capture("mesh-tools.ppm");
  tap("Settings");
  if (!baseline)
    assert(lv_tabview_get_tab_active(objects.controller_tab_view) == 0);
  create_screen_lock_screen();
  lv_screen_load(objects.lock_screen);
  step();
  capture("lock-base.ppm");
  shellScreens();
}
int main() {
  baseline = getenv("SIM_BASELINE") && *getenv("SIM_BASELINE");
  lv_init();
  auto display = lv_display_create(320, 240);
  lv_display_set_color_format(display, LV_COLOR_FORMAT_RGB565);
  lv_display_set_buffers(display, buffer, nullptr, sizeof(buffer),
                         LV_DISPLAY_RENDER_MODE_PARTIAL);
  lv_display_set_flush_cb(display, flush);
  auto input = lv_indev_create();
  lv_indev_set_type(input, LV_INDEV_TYPE_POINTER);
  lv_indev_set_read_cb(input, readPointer);
  auto screen = lv_screen_active();
  lv_obj_set_style_bg_color(
      screen, lv_color_hex(baseline ? 0x000000 : Tui::Background), 0);
  tui_statusbar_init();
  tui_statusbar_reserve(screen);
  lv_obj_set_style_pad_top(screen, 0, 0);
  tui_statusbar_tick();
  auto pager = makeGrid(screen);
  printf("Grid LVGL heap: %zu bytes\n", used());
  step();
  if (baseline) {
    capture("home.ppm");
    auto tile = lv_obj_get_child(lv_obj_get_child(pager, 0), 0);
    lv_obj_add_state(tile, LV_STATE_FOCUSED);
    step();
    capture("focus.ppm");
    lv_obj_add_state(tile, LV_STATE_PRESSED);
    step();
    capture("pressed.ppm");
    lv_obj_remove_state(tile, LV_STATE_FOCUSED | LV_STATE_PRESSED);
    lv_obj_scroll_to_x(pager, 640, LV_ANIM_OFF);
    lv_obj_add_state(lv_obj_get_child(lv_obj_get_child(pager, 2), 5),
                     LV_STATE_FOCUSED);
    step();
    capture("last-page.ppm");
    gallery(screen);
    return 0;
  }
  capture("home.ppm");
  auto group = lv_group_create();
  for (uint32_t p = 0; p < lv_obj_get_child_count(pager); ++p) {
    auto page = lv_obj_get_child(pager, p);
    for (uint32_t t = 0; t < lv_obj_get_child_count(page); ++t) {
      auto tile = lv_obj_get_child(page, t);
      lv_group_add_obj(group, tile);
      lv_area_t a;
      lv_obj_get_coords(tile, &a);
      assert(a.x2 - a.x1 + 1 == 88 && a.y2 - a.y1 + 1 == 84);
      assert(a.y1 >= 26 && a.y2 < 214);
    }
  }
  auto first = lv_obj_get_child(lv_obj_get_child(pager, 0), 0);
  lv_group_focus_obj(first);
  step();
  capture("focus.ppm");
  lv_area_t a;
  lv_obj_get_coords(first, &a);
  pointer = {(lv_coord_t)((a.x1 + a.x2) / 2), (lv_coord_t)((a.y1 + a.y2) / 2)};
  down = true;
  step(100);
  assert(lv_obj_has_state(first, LV_STATE_PRESSED));
  capture("pressed.ppm");
  down = false;
  step(100);
  assert(clicked == 0);
  down = true;
  step(650);
  assert(held == 1);
  down = false;
  step();
  // Navigate all rows and pages through the real LVGL focus group.
  for (int n = 1; n < 18; ++n) {
    lv_group_focus_next(group);
    step(350);
    auto tile = lv_group_get_focused(group);
    assert(tile);
    assert(lv_obj_has_state(tile, LV_STATE_FOCUSED));
    lv_obj_get_coords(tile, &a);
    assert(a.x1 >= 0 && a.x2 < 320);
    clicked = -1;
    lv_obj_send_event(tile, LV_EVENT_CLICKED, nullptr);
    assert(clicked == n);
  }
  capture("last-page.ppm");
  // Swipe left and right using the pointer driver, not a synthetic scroll
  // event.
  lv_group_focus_obj(first);
  step(500);
  pointer = {280, 120};
  down = true;
  step(40);
  for (int x = 280; x >= 40; x -= 20) {
    pointer.x = x;
    step(25);
  }
  down = false;
  step(600);
  assert(lv_obj_get_scroll_x(pager) >= 300);
  capture("swiped.ppm");
  pointer = {40, 120};
  down = true;
  step(40);
  for (int x = 40; x <= 280; x += 20) {
    pointer.x = x;
    step(25);
  }
  down = false;
  step(600);
  assert(lv_obj_get_scroll_x(pager) == 0);
  step(1000);
  flushes = 0;
  step(5000);
  assert(flushes == 0);
  printf("PASS: touch, hold, 18 focus targets, paging both ways, geometry, "
         "idle zero flushes\n");
  lv_group_delete(group);
  lv_obj_delete(pager);
  step();
  const size_t baseline = used();
  for (int i = 0; i < 100; ++i) {
    pager = makeGrid(screen);
    step(30);
    lv_obj_delete(pager);
    step(30);
  }
  assert(used() == baseline);
  printf("PASS: 100 grid rebuilds, no retained LVGL heap (%zu bytes)\n",
         baseline);
  tui_statusbar_init();
  auto keys = lv_group_create();
  lv_group_set_default(keys);
  calculator_open();
  tui_statusbar_tick();
  step();
  capture("calculator.ppm");
  tap("C");
  tap("2");
  tap("+");
  tap("3");
  tap("=");
  assert(findLabel(lv_screen_active(), "5"));
  tap("C");
  tap("8");
  tap("/");
  tap("0");
  tap("=");
  assert(findLabel(lv_screen_active(), "Error"));
  tap("C");
  lv_group_send_data(keys, '7');
  lv_group_send_data(keys, '+');
  lv_group_send_data(keys, '2');
  lv_group_send_data(keys, LV_KEY_ENTER);
  assert(findLabel(lv_screen_active(), "9"));
  tap("Back");
  assert(lv_screen_active() == screen);
  for (int i = 0; i < 20; ++i) {
    calculator_open();
    step();
    tap("Back");
  }
  printf("PASS: calculator touch arithmetic, divide by zero, bottom row and "
         "Back cycles\n");
  lv_screen_load(screen);
  stopwatch_open();
  tui_statusbar_tick();
  step();
  capture("clock.ppm");
  tap("Start");
  step(1500);
  tap("Stop");
  tap("Reset");
  tap("Timer");
  capture("timer.ppm");
  tap("Alarm");
  capture("alarm.ppm");
  tap("Watch");
  printf("PASS: clock Start/Stop/Reset and Timer/Alarm/Watch navigation\n");
  lv_screen_load(screen);
  notes_open();
  tui_statusbar_tick();
  step();
  capture("notes.ppm");
  tap("+ New");
  step();
  capture("note-editor.ppm");
  auto editor = lv_screen_active();
  lv_group_send_data(keys, 'H');
  lv_group_send_data(keys, 'i');
  auto title = lv_group_get_focused(keys);
  assert(lv_obj_check_type(title, &lv_textarea_class));
  assert(!strcmp(lv_textarea_get_text(title), "Hi"));
  tap("Delete");
  assert(findLabel(editor, "Delete this note?"));
  tap("Cancel");
  assert(!findLabel(editor, "Delete this note?"));
  printf("PASS: notes no-SD state and new editor navigation\n");
  gallery(screen);
  size_t themeHeap = used();
  for (int i = 0; i < 100; ++i) {
    Themes::set(i % 2 ? Themes::eDark : Themes::eLight);
    Themes::initStyles();
  }
  fprintf(stderr, "Theme refresh heap: %zu -> %zu bytes\n", themeHeap, used());
  assert(used() == themeHeap);
  puts("PASS: 100 theme refreshes without retained LVGL heap");
  puts("PASS: full Settings, header, PIN, dialog and action-sheet "
       "bounds/non-overlap");
  return 0;
}
