#pragma once
#include "lvgl.h"

namespace GlassUI
{
void wallpaper(lv_obj_t *screen);
void surface(lv_obj_t *obj, int radius = 20);
void appIcon(lv_obj_t *parent, const char *name);
void symbol(lv_obj_t *parent, const char *name, int x, int y);
void settingsSections(lv_obj_t *screen);
void settingsFinish(lv_obj_t *screen);
lv_obj_t *battery(lv_obj_t *parent);
void updateBattery(lv_obj_t *widget, int percent, bool plugged, bool light = false);
} // namespace GlassUI
