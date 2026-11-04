#include "SafeFile.h"

#ifdef FSCom

// Only way to work on both esp32 and nrf52
static File openFile(const char *filename, bool fullAtomic)
{
    concurrency::LockGuard g(spiLock);
    LOG_DEBUG("Opening %s, fullAtomic=%d", filename, fullAtomic);
    if (!fullAtomic) {
        FSCom.remove(filename); // Nuke the old file to make space (ignore if it !exists)
    }

    String filenameTmp = filename;
    filenameTmp += ".tmp";

    // FILE_O_WRITE appends on Adafruit_LittleFS (nRF52) and STM32 LittleFS, so a tmp left by an interrupted
    // write must go first. exists() guards it: a bare remove() of a missing file logs on Portduino.
    if (FSCom.exists(filenameTmp.c_str())) {
        LOG_DEBUG("Remove stale %s", filenameTmp.c_str());
        // Opening anyway would append to the stale bytes, and the XOR readback is 8 bits wide, so
        // polluted content has a real chance of verifying and being renamed over the good file.
        if (!FSCom.remove(filenameTmp.c_str())) {
            LOG_ERROR("Can't remove stale %s", filenameTmp.c_str());
            return File();
        }
    }

    // clear any previous LFS errors
    return FSCom.open(filenameTmp.c_str(), FILE_O_WRITE);
}

SafeFile::SafeFile(const char *_filename, bool fullAtomic)
    : filename(_filename), f(openFile(_filename, fullAtomic)), fullAtomic(fullAtomic)
{
    if (!f)
        lastError = SettingsSaveError::Open;
}

size_t SafeFile::write(uint8_t ch)
{
    if (!f)
        return 0;

    hash ^= ch;
    expectedSize++;
    const size_t written = f.write(ch);
    writeFailed |= written != 1;
    if (written != 1)
        lastError = SettingsSaveError::Write;
    return written;
}

size_t SafeFile::write(const uint8_t *buffer, size_t size)
{
    if (!f)
        return 0;

    for (size_t i = 0; i < size; i++) {
        hash ^= buffer[i];
    }
    expectedSize += size;
    const size_t written = f.write((uint8_t const *)buffer, size);
    writeFailed |= written != size;
    if (written != size)
        lastError = SettingsSaveError::Write;
    return written;
}

/**
 * Atomically close the file (overwriting any old version) and readback the contents to confirm the hash matches
 *
 * @return false for failure
 */
bool SafeFile::close(bool commit)
{
    if (!f)
        return false;

    spiLock->lock();
    f.close();
    spiLock->unlock();

    String filenameTmp = filename;
    filenameTmp += ".tmp";
    if (!commit || writeFailed || !testReadback()) {
        concurrency::LockGuard g(spiLock);
        FSCom.remove(filenameTmp.c_str());
        return false;
    }

    // Rename or overwrite (atomic operation)
    if (!renameFile(filenameTmp.c_str(), filename.c_str())) {
        LOG_ERROR("Can't rename new pref file");
        lastError = SettingsSaveError::Rename;
        concurrency::LockGuard g(spiLock);
        FSCom.remove(filenameTmp.c_str());
        return false;
    }

    return true;
}

/// Read our (closed) tempfile back in and compare the hash
bool SafeFile::testReadback()
{
    concurrency::LockGuard g(spiLock);

    String filenameTmp = filename;
    filenameTmp += ".tmp";
    auto f2 = FSCom.open(filenameTmp.c_str(), FILE_O_READ);
    if (!f2) {
        LOG_ERROR("Can't open tmp file for readback");
        lastError = SettingsSaveError::ReadbackOpen;
        return false;
    }
    int c = 0;
    uint8_t test_hash = 0;
    size_t bytesRead = 0;
    while ((c = f2.read()) >= 0) {
        test_hash ^= (uint8_t)c;
        bytesRead++;
    }
    f2.close();

    if (bytesRead != expectedSize) {
        LOG_ERROR("Readback failed length mismatch");
        lastError = SettingsSaveError::ReadbackLength;
        return false;
    }
    if (test_hash != hash) {
        LOG_ERROR("Readback failed hash mismatch");
        lastError = SettingsSaveError::ReadbackHash;
        return false;
    }

    return true;
}

#endif
