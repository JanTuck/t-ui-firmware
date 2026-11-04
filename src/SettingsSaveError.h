#pragma once
#include <cstdint>

enum class SettingsSaveError : uint8_t {
    None,
    Unknown,
    Power,
    Open,
    Write,
    Encode,
    ReadbackOpen,
    ReadbackLength,
    ReadbackHash,
    Rename,
    Memory,
    Encryption,
    Unavailable,
    NvsOpen,
    NvsWrite
};

inline const char *settingsSaveErrorMessage(SettingsSaveError error)
{
    switch (error) {
    case SettingsSaveError::Power:
        return "Settings not saved: power protection active.";
    case SettingsSaveError::Open:
        return "Settings not saved: cannot open temporary file.";
    case SettingsSaveError::Write:
        return "Settings not saved: file write failed.";
    case SettingsSaveError::Encode:
        return "Settings not saved: configuration encoding failed.";
    case SettingsSaveError::ReadbackOpen:
        return "Settings not saved: cannot reopen verification file.";
    case SettingsSaveError::ReadbackLength:
        return "Settings not saved: verification length mismatch.";
    case SettingsSaveError::ReadbackHash:
        return "Settings not saved: verification data mismatch.";
    case SettingsSaveError::Rename:
        return "Settings not saved: file replacement failed.";
    case SettingsSaveError::Memory:
        return "Settings not saved: insufficient working memory.";
    case SettingsSaveError::Encryption:
        return "Settings not saved: encryption write failed.";
    case SettingsSaveError::Unavailable:
        return "Settings not saved: storage service unavailable.";
    case SettingsSaveError::NvsOpen:
        return "Settings not saved: cannot open NVS preferences.";
    case SettingsSaveError::NvsWrite:
        return "Settings not saved: NVS write failed.";
    default:
        return "Settings not saved: save operation failed.";
    }
}
