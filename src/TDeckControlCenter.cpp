#include "configuration.h"

#if HAS_BLUETOOTH && !MESHTASTIC_EXCLUDE_BLUETOOTH
#include "main.h"
#include "mesh/NodeDB.h"
#include "modules/AdminModule.h"
#endif
#if !MESHTASTIC_EXCLUDE_GPS
#include "gps/GPS.h"
#endif

extern "C" bool tdeck_control_bluetooth_active(void)
{
#if HAS_BLUETOOTH && !MESHTASTIC_EXCLUDE_BLUETOOTH
    if (!config.bluetooth.enabled || bluetoothTornDown)
        return false;
#if defined(ARCH_ESP32) && !defined(CONFIG_IDF_TARGET_ESP32S2)
    return nimbleBluetooth && nimbleBluetooth->isActive() && !nimbleBluetooth->isDeInit;
#else
    return true;
#endif
#else
    return false;
#endif
}

extern "C" bool tdeck_control_gps_available(void)
{
#if !MESHTASTIC_EXCLUDE_GPS
    return gps != nullptr;
#else
    return false;
#endif
}

extern "C" bool tdeck_control_wifi_available(void)
{
#if HAS_WIFI && !MESHTASTIC_EXCLUDE_WIFI
    return true;
#else
    return false;
#endif
}

extern "C" bool tdeck_control_bluetooth_available(void)
{
#if HAS_BLUETOOTH && !MESHTASTIC_EXCLUDE_BLUETOOTH
    return true;
#else
    return false;
#endif
}
