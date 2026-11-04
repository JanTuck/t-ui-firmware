#pragma once
#include "SettingsSaveError.h"

bool tdeck_save_settings(int segments);
void tdeck_settings_save_failed(SettingsSaveError error = SettingsSaveError::Unknown);
void tdeck_settings_service();
