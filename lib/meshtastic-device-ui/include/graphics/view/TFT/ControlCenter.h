#pragma once

#include <lvgl.h>

namespace ControlCenter
{
enum Action { Wifi, Bluetooth, Gps, Brightness, Settings };
struct State {
    bool allowed = false;
    bool wifiAvailable = false;
    bool bluetoothAvailable = false;
    bool gpsAvailable = false;
    bool wifiEnabled = false;
    bool wifiConfigured = false;
    bool bluetoothEnabled = false;
    bool gpsEnabled = false;
    bool wifiConnected = false;
    bool bluetoothActive = false;
    int brightness = 153;
};
using Read = State (*)();
using Write = void (*)(Action, int, bool);
void init(Read read, Write write);
void tick();
bool close();
bool isOpen();
} // namespace ControlCenter
