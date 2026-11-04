#include "TDeckSettingsPersistence.h"
#include "MeshService.h"
#include "NodeDB.h"
#include "gps/RTC.h"
#include <atomic>
#include <cstring>

static std::atomic<SettingsSaveError> saveFailurePending{SettingsSaveError::None};

void tdeck_settings_save_failed(SettingsSaveError error)
{
    auto expected = SettingsSaveError::None;
    saveFailurePending.compare_exchange_strong(expected, error == SettingsSaveError::None ? SettingsSaveError::Unknown : error,
                                               std::memory_order_relaxed);
}

bool tdeck_save_settings(int segments)
{
    const bool saved = nodeDB && nodeDB->saveToDisk(segments);
    if (!saved)
        tdeck_settings_save_failed(nodeDB ? nodeDB->getLastSaveError() : SettingsSaveError::Unavailable);
    return saved;
}

void tdeck_settings_service()
{
    if (!service || saveFailurePending.load(std::memory_order_relaxed) == SettingsSaveError::None)
        return;
    const auto error = saveFailurePending.exchange(SettingsSaveError::None, std::memory_order_relaxed);
    if (error == SettingsSaveError::None)
        return;
    auto *notification = clientNotificationPool.allocZeroed();
    if (!notification) {
        tdeck_settings_save_failed(error);
        return;
    }
    notification->level = meshtastic_LogRecord_Level_WARNING;
    notification->time = getValidTime(RTCQualityFromNet);
    strcpy(notification->message, settingsSaveErrorMessage(error));
    service->sendClientNotification(notification);
}
