#include "graphics/common/LoRaPresets.h"
#include "util/ILog.h"
#include <cmath>

/**
 * LoRa Presets
 * Note: keep order the same as in meshtastic_Config_LoRaConfig_RegionCode and as in settings_region_dropdown
 */
LoRaPresets::RegionInfo LoRaPresets::regionInfo[] = {{"UNSET", 902.0f, 928.0f},
                                                     {"US", 902.0f, 928.0f},
                                                     {"EU_433", 433.0f, 434.0f},
                                                     {"EU_868", 869.4f, 869.65f},
                                                     {"CN", 470.0f, 510.0f},
                                                     {"JP", 920.5f, 923.5f},
                                                     {"ANZ", 915.0f, 928.0f},
                                                     {"KR", 920.0f, 923.0f},
                                                     {"TW", 920.0f, 925.0f},
                                                     {"RU", 868.7f, 869.2f},
                                                     {"IN", 865.0f, 867.0f},
                                                     {"NZ_865", 864.0f, 868.0f},
                                                     {"TH", 920.0f, 925.0f},
                                                     {"LORA_24", 2400.0f, 2483.5f},
                                                     {"UA_433", 433.0f, 434.7f},
                                                     {"UA_868", 868.0f, 868.6f},
                                                     {"MY_433", 433.0f, 435.0f},
                                                     {"MY_919", 919.0f, 924.0f},
                                                     {"SG_923", 917.0f, 925.0f},
                                                     {"PH_433", 433.0f, 434.7f},
                                                     {"PH_868", 868.0f, 869.4f},
                                                     {"PH_915", 915.0f, 918.0f},
                                                     {"ANZ_433", 433.05f, 434.79f},
                                                     {"KZ_433", 433.075f, 434.775f},
                                                     {"KZ_863", 863.0f, 868.0f},
                                                     {"NP_865", 865.0f, 868.0f},
                                                     {"BR_902", 902.0f, 907.5f},
                                                     {"ITU1_2M", 144.0f, 146.0f, 0, .0022f, 26},
                                                     {"ITU2_2M", 144.0f, 148.0f, 0, .0022f, 51},
                                                     {"EU_866", 865.6f, 867.6f, .4f, .0375f},
                                                     {"EU_874", 0, 0},
                                                     {"EU_917", 0, 0},
                                                     {"EU_N_868", 869.4f, 869.65f, 0, .0104f, 1},
                                                     {"ITU3_2M", 144.0f, 148.0f, 0, .0022f, 33},
                                                     {"ITU1_70CM", 430.0f, 440.0f, 0, .01875f, 37},
                                                     {"ITU2_70CM", 420.0f, 450.0f, 0, .01875f, 137},
                                                     {"ITU3_70CM", 430.0f, 450.0f, 0, .01875f, 37},
                                                     {"ITU2_125CM", 220.0f, 225.0f, 0, .01875f, 37}};

LoRaPresets::ModemPreset LoRaPresets::modemPreset[] = {
    {"LongFast", "250", .250f},     {"LongSlow", "125", .125f},     {"VLongSlow", "62.5", .0625f}, {"MediumSlow", "250", .250f},
    {"MediumFast", "250", .250f},   {"ShortSlow", "250", .250f},    {"ShortFast", "250", .250f},   {"LongMod", "125", .125f},
    {"ShortTurbo", "500", .500f},   {"LongTurbo", "500", .500f},    {"LiteFast", "125", .125f},    {"LiteSlow", "125", .125f},
    {"NarrowFast", "62.5", .0625f}, {"NarrowSlow", "62.5", .0625f}, {"TinyFast", "15.6", .0156f},  {"TinySlow", "15.6", .0156f},
    {"MediumTurbo", "500", .500f}};

const LoRaPresets::RegionInfo &LoRaPresets::getRegionInfo(meshtastic_Config_LoRaConfig_RegionCode region)
{
    static const RegionInfo unknown = {"Unknown", 0, 0};
    return (unsigned)region < sizeof(regionInfo) / sizeof(regionInfo[0]) ? regionInfo[region] : unknown;
}

const LoRaPresets::ModemPreset &LoRaPresets::getModemPreset(meshtastic_Config_LoRaConfig_ModemPreset preset)
{
    static const ModemPreset unknown = {"Unknown", "0", 0};
    return (unsigned)preset < sizeof(modemPreset) / sizeof(modemPreset[0]) ? modemPreset[preset] : unknown;
}

const char *LoRaPresets::loRaRegionToString(meshtastic_Config_LoRaConfig_RegionCode region)
{
    return getRegionInfo(region).region;
}

float LoRaPresets::getFrequencyStart(meshtastic_Config_LoRaConfig_RegionCode region)
{
    return getRegionInfo(region).freqStart;
}

float LoRaPresets::getFrequencyEnd(meshtastic_Config_LoRaConfig_RegionCode region)
{
    return getRegionInfo(region).freqEnd;
}

/**
 * Default slot number is generated using the same firmware hash algorithm
 */
uint16_t LoRaPresets::getDefaultSlot(meshtastic_Config_LoRaConfig_RegionCode region,
                                     meshtastic_Config_LoRaConfig_ModemPreset preset, const char *channelName)
{
    auto hash = [](const char *str) -> uint32_t {
        uint32_t hash = 5381;
        unsigned char c;
        while ((c = *str++) != '\0')
            hash += (hash << 5) + c;
        return hash;
    };

    uint32_t numChannels = getNumChannels(region, preset);
    if (numChannels == 0)
        return 0;
    const auto &info = getRegionInfo(region);
    if (info.defaultSlot)
        return info.defaultSlot;
    return hash(channelName && channelName[0] != '\0' ? channelName : getModemPreset(preset).preset) % numChannels + 1;
}

float LoRaPresets::getBandwidth(meshtastic_Config_LoRaConfig_ModemPreset preset)
{
    // TODO: LORA_24 wide mode (3.25 vs. 31/.03125f, 62/.0625f, 200/.203125f, 400/.40625f, 800/.8125f, 1600/1.6250f
    return getModemPreset(preset).bandwidth_MHz;
}

const char *LoRaPresets::getBandwidthString(meshtastic_Config_LoRaConfig_ModemPreset preset)
{
    return getModemPreset(preset).bandwidth_kHz;
}

const char *LoRaPresets::modemPresetToString(meshtastic_Config_LoRaConfig_ModemPreset preset)
{
    return getModemPreset(preset).preset;
}

uint32_t LoRaPresets::getNumChannels(meshtastic_Config_LoRaConfig_RegionCode region,
                                     meshtastic_Config_LoRaConfig_ModemPreset preset)
{
    const float bandwidth = getBandwidth(preset);
    const auto &info = getRegionInfo(region);
    if (region == meshtastic_Config_LoRaConfig_RegionCode_UNSET || bandwidth <= 0 || info.freqEnd <= info.freqStart)
        return 0;
    const float slotWidth = info.spacing + 2 * info.padding + bandwidth;
    return (uint32_t)std::round((info.freqEnd - info.freqStart + info.spacing) / slotWidth);
}

float LoRaPresets::getRadioFreq(meshtastic_Config_LoRaConfig_RegionCode region, meshtastic_Config_LoRaConfig_ModemPreset preset,
                                uint32_t channel)
{
    if (channel == 0 || channel > getNumChannels(region, preset))
        return 0;
    const auto &info = getRegionInfo(region);
    const float bandwidth = getBandwidth(preset);
    return info.freqStart + bandwidth / 2 + info.padding + (channel - 1) * (info.spacing + 2 * info.padding + bandwidth);
}
