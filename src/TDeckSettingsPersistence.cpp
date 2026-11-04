#include "TDeckSettingsPersistence.h"
#include "MeshService.h"
#include "NodeDB.h"
#include "gps/RTC.h"
#include <atomic>
#include <cstring>

static std::atomic<bool> saveFailurePending{false};

void tdeck_settings_save_failed()
{
    saveFailurePending.store(true, std::memory_order_relaxed);
}

bool tdeck_save_settings(int segments)
{
    const bool saved = nodeDB && nodeDB->saveToDisk(segments);
    if (!saved)
        tdeck_settings_save_failed();
    return saved;
}

void tdeck_settings_service()
{
    if (!service || !saveFailurePending.load(std::memory_order_relaxed) ||
        !saveFailurePending.exchange(false, std::memory_order_relaxed))
        return;
    auto *notification = clientNotificationPool.allocZeroed();
    if (!notification) {
        tdeck_settings_save_failed();
        return;
    }
    notification->level = meshtastic_LogRecord_Level_WARNING;
    notification->time = getValidTime(RTCQualityFromNet);
    strcpy(notification->message, "Settings were not saved. Check internal storage.");
    service->sendClientNotification(notification);
}
