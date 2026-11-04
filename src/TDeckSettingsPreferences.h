#pragma once
#include "TDeckSettingsPersistence.h"
#include <Preferences.h>

class TDeckSettingsPreferences : public Preferences
{
  public:
    bool begin(const char *name, bool readOnly = false, const char *partition = nullptr)
    {
        const bool opened = Preferences::begin(name, readOnly, partition);
        if (!opened && !readOnly)
            tdeck_settings_save_failed(SettingsSaveError::NvsOpen);
        return opened;
    }

    size_t putBool(const char *key, bool value) { return checked(Preferences::putBool(key, value), 1); }
    size_t putUChar(const char *key, uint8_t value) { return checked(Preferences::putUChar(key, value), 1); }
    size_t putShort(const char *key, int16_t value) { return checked(Preferences::putShort(key, value), 2); }
    size_t putUShort(const char *key, uint16_t value) { return checked(Preferences::putUShort(key, value), 2); }
    size_t putUInt(const char *key, uint32_t value) { return checked(Preferences::putUInt(key, value), 4); }
    size_t putLong(const char *key, int32_t value) { return checked(Preferences::putLong(key, value), 4); }

  private:
    static size_t checked(size_t written, size_t expected)
    {
        if (written != expected)
            tdeck_settings_save_failed(SettingsSaveError::NvsWrite);
        return written;
    }
};
