#pragma once
#include "PowerFSM.h"
#include "SPILock.h"
#include "concurrency/OSThread.h"
#include "configuration.h"
#include "main.h"
#include "sleep.h"
#include <memory>

#ifdef HAS_I2S
#include <AudioFileSourcePROGMEM.h>
#include <AudioGeneratorRTTTL.h>
#include <AudioGeneratorWAV.h>
#include <AudioOutputI2S.h>
#include <ESP8266SAM.h>

// A board with an I2S amplifier opts in by defining AUDIO_AMP_ENABLE(on) in its variant.h to power the
// amp on/off around playback (e.g. an enable pin on an I/O expander). The includes below expose the
// expander instances (io / mcpIoExpander) those macros typically reference.
#ifdef USE_PCA95X5
#include PCA95X5_INC
extern PCA95X5_CLS io;
#endif

#ifdef USE_MCP23017
#include "platform/esp32/ExtensionIOMCP23017.h"
#endif

#define AUDIO_THREAD_INTERVAL_MS 100

class AudioThread : public concurrency::OSThread
{
  public:
    AudioThread() : OSThread("Audio") { initOutput(); }

    void beginRttl(const void *data, uint32_t len)
    {
        ampEnable(true);
        setCPUFast(true);
        rtttlFile = std::unique_ptr<AudioFileSourcePROGMEM>(new AudioFileSourcePROGMEM(data, len));
        i2sRtttl = std::unique_ptr<AudioGeneratorRTTTL>(new AudioGeneratorRTTTL());
        i2sRtttl->begin(rtttlFile.get(), audioOut.get());
    }

    // Also handles actually playing the RTTTL, needs to be called in loop
    bool isPlaying()
    {
        if (i2sRtttl != nullptr) {
            return i2sRtttl->isRunning() && i2sRtttl->loop();
        }
        return false;
    }

    void stop()
    {
        if (i2sRtttl != nullptr) {
            i2sRtttl->stop();
            i2sRtttl = nullptr;
        }

        rtttlFile = nullptr;

        setCPUFast(false);
        ampEnable(false);
    }

    // Set output gain (0.0–1.0+). Default is 0.2; the timer alarm cranks this up
    // for a much louder beep, then restores it. >1.0 clips (harsher, even louder).
    void setGain(float g)
    {
        if (audioOut)
            audioOut->SetGain(g);
    }

    // Fire-and-forget WAV from flash, for the new-message pop (src/pop_wav.h).
    //
    // Deliberately NOT like beginRttl + the caller spinning on isPlaying(): that blocks
    // whoever called it, and the one thread that must never block here is the radio.
    // Stalls of RadioIf waiting on a lock are exactly what has been rebooting this
    // device. So this only STARTS playback; runOnce() below pumps it to the end and
    // tidies up, and nobody waits.
    void beginWav(const void *data, uint32_t len)
    {
        if (i2sWav != nullptr) // a pop already sounding: let it finish rather than stutter
            return;
#ifdef T_LORA_PAGER
        io.digitalWrite(EXPANDS_AMP_EN, HIGH);
#endif
        setCPUFast(true);
        wavFile = std::unique_ptr<AudioFileSourcePROGMEM>(new AudioFileSourcePROGMEM(data, len));
        i2sWav = std::unique_ptr<AudioGeneratorWAV>(new AudioGeneratorWAV());
        if (!i2sWav->begin(wavFile.get(), audioOut.get()))
            endWav();
    }

    bool wavPlaying() const { return i2sWav != nullptr; }

    void readAloud(const char *text)
    {
        if (i2sRtttl != nullptr) {
            i2sRtttl->stop();
            i2sRtttl = nullptr;
        }

        ampEnable(true);
        auto sam = std::unique_ptr<ESP8266SAM>(new ESP8266SAM);
        sam->Say(audioOut.get(), text);
        setCPUFast(false);
        audioOut->stop();
        ampEnable(false);
    }

  protected:
    int32_t runOnce() override
    {
        canSleep = true; // Assume we should not keep the board awake

        // if (i2sRtttl != nullptr && i2sRtttl->isRunning()) {
        //     i2sRtttl->loop();
        // }

        // Pump a pop that beginWav() started. The I2S buffer needs feeding far more
        // often than every 100 ms or the sound breaks up, so while one is playing this
        // thread asks to be run again almost immediately, and only then goes back to
        // idling. canSleep stays false meanwhile so the board does not doze mid-pop.
        if (i2sWav != nullptr) {
            if (i2sWav->isRunning() && i2sWav->loop()) {
                canSleep = false;
                return 2;
            }
            endWav();
        }
        return AUDIO_THREAD_INTERVAL_MS;
    }

  private:
    // Amps like the NS4150 need time to leave shutdown, longer when the enable is an I/O expander write.
    // Without a variant's AUDIO_AMP_SETTLE_MS the short system tones are over before any audio gets out.
    static void ampEnable(bool on)
    {
#ifdef AUDIO_AMP_ENABLE
        AUDIO_AMP_ENABLE(on);
#ifdef AUDIO_AMP_SETTLE_MS
        if (on)
            delay(AUDIO_AMP_SETTLE_MS);
#endif
#else
        (void)on;
#endif
    }

    void initOutput()
    {
        audioOut = std::unique_ptr<AudioOutputI2S>(new AudioOutputI2S(1, AudioOutputI2S::EXTERNAL_I2S));
        audioOut->SetPinout(DAC_I2S_BCK, DAC_I2S_WS, DAC_I2S_DOUT, DAC_I2S_MCLK);
        audioOut->SetGain(0.2);
    };

    void endWav()
    {
        if (i2sWav != nullptr) {
            i2sWav->stop();
            i2sWav = nullptr;
        }
        wavFile = nullptr;
        setCPUFast(false);
#ifdef T_LORA_PAGER
        io.digitalWrite(EXPANDS_AMP_EN, LOW);
#endif
    }

    std::unique_ptr<AudioGeneratorRTTTL> i2sRtttl = nullptr;
    std::unique_ptr<AudioGeneratorWAV> i2sWav = nullptr;
    std::unique_ptr<AudioFileSourcePROGMEM> wavFile = nullptr;
    std::unique_ptr<AudioOutputI2S> audioOut = nullptr;

    std::unique_ptr<AudioFileSourcePROGMEM> rtttlFile = nullptr;
};

#endif
