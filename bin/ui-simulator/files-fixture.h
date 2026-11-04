#pragma once
#include "files-format.inc"
#define snprintf lv_snprintf
#define fmtBytes fmtBytesCompact
#include "files-format.inc"
#undef fmtBytes
#undef snprintf
#include "files-empty.inc"
#include "files-name-fit.inc"
#include "files-row.inc"
struct FilesHarness;
static FilesHarness *filesHarness;
#define THIS filesHarness
struct FilesHarness {
    enum FilesVol { VOL_ROOT, VOL_SD, VOL_FLASH, VOL_TRASH };
    FilesVol filesVol = VOL_ROOT, copySrcVol = VOL_ROOT;
    lv_obj_t *files_screen = nullptr, *launcher_screen;
    lv_obj_t *files_path_label, *files_list, *files_free_label;
    lv_obj_t *files_copy_btn, *files_copy_lbl, *files_del_btn, *files_del_lbl;
    lv_obj_t *files_cancel_btn, *files_newfolder_btn, *files_newfolder_lbl;
    bool filesCopyArmed = false, filesDelConfirm = false, filesSelIsDir = false;
    bool filesSuppressClick = false; // Legacy baseline callback only.
    lv_obj_t *files_sel_row = nullptr;
    char filesNames[6][64] = {};
    bool filesNameIsDir[6] = {};
    char openedNote[256] = "";
    static void notes_open_file(const char *path) { snprintf(filesHarness->openedNote, 256, "%s", path); }
    char filesPath[192] = "/", filesSelName[64] = "", copySrcPath[256] = "";
    bool sdCard = true, expanded = false;
    int copies = 0, restores = 0, trashes = 0, deletes = 0, folders = 0;
    uint64_t flashFree = 2500000;
    struct {
        uint64_t total = 3538944;
        uint64_t totalBytes() { return total; }
    } LittleFS;
    uint64_t filesFreeBytes(bool sd) { return sd ? 30923764531ULL : flashFree; }
    void filesCopyNow() { ++copies; }
    void filesRestoreSelected() { ++restores; }
    void filesTrashSelected() { ++trashes; }
    void filesDeleteForever() { ++deletes; }
    lv_obj_t *files_newfolder_ovl = nullptr, *files_newfolder_ta = nullptr;
    lv_group_t *keys = lv_group_create();
    char createdName[40] = "";
    void filesNewFolderCreate(const char *name)
    {
        ++folders;
        snprintf(createdName, sizeof(createdName), "%s", name);
    }
    void beginTextEntry(lv_obj_t *field)
    {
        lv_group_add_obj(keys, field);
        lv_group_focus_obj(field);
    }
    void endTextEntry() { lv_group_remove_all_objs(keys); }
#include "files-closefolder.inc"
#include "files-newfolder.inc"
    static void joinPath(char *out, size_t cap, const char *dir, const char *name)
    {
        snprintf(out, cap, "%s%s%s", dir, strcmp(dir, "/") ? "/" : "", name);
    }
    enum { LOCK_NONE = 0 };
    int lockState = LOCK_NONE;
    bool tdeck_input_gated = false, tdeck_hold_dark = false;
    lv_obj_t *arrange_overlay = nullptr, *pins_overlay = nullptr;
    void closeArrange() {}
    void closePinsList() {}
    void lockDevice() {}
#include "files-back.inc"
#include "files-build.inc"
#ifndef SIM_OLD_FILES
#include "files-notice.inc"
#endif
#include "files-actions.inc"
#include "files-message.inc"
    void filesRefresh()
    {
        lv_obj_clean(files_list);
        files_sel_row = nullptr;
        filesSelName[0] = 0;
        filesSelIsDir = false;
        filesUpdateActionBar();
        char freeBuf[24], line[96];
#include "files-capacity.inc"
#include "files-entries.inc"
#include "files-root.inc"
#include "files-trash-select.inc"
        if (filesVol == VOL_TRASH) {
            lv_label_set_text(files_path_label, "Trash");
            lv_label_set_text(files_free_label, "");
        }
        const char *names[] = {"Trail notes with a long filename.txt",
                               "/Maps",
                               "Second.txt",
                               "Another.txt",
                               "Last.txt",
                               "Filename beyond the safe row identity capacity should be disabled.txt"};
        for (int i = 0; i < (expanded ? 6 : 3); ++i) {
            filesNameIsDir[i] = names[i][0] == '/';
            snprintf(filesNames[i], sizeof(filesNames[i]), "%s%s", filesVol == VOL_TRASH ? "S" : "",
                     names[i] + ((filesVol == VOL_TRASH && filesNameIsDir[i]) ? 1 : 0));
            auto row = lv_list_add_button(files_list, filesNameIsDir[i] ? LV_SYMBOL_DIRECTORY : LV_SYMBOL_FILE,
                                          names[i] + (filesNameIsDir[i] ? 1 : 0));
            filesStyleRow(row, Tui::Accent);
            if (!filesNameFits(names[i], sizeof(filesNames[i]), filesNameIsDir[i] || filesVol == VOL_TRASH)) {
                filesNames[i][0] = 0;
                lv_obj_add_state(row, LV_STATE_DISABLED);
            } else if (filesVol == VOL_TRASH)
                lv_obj_add_event_cb(row, trash_cb, LV_EVENT_CLICKED, (void *)(intptr_t)i);
            else {
                lv_obj_add_event_cb(row, entry_cb, baseline ? LV_EVENT_CLICKED : LV_EVENT_SHORT_CLICKED, (void *)(intptr_t)i);
                lv_obj_add_event_cb(row, entry_long_cb, LV_EVENT_LONG_PRESSED, (void *)(intptr_t)i);
            }
        }
    }
};
#undef THIS
static void filesGallery(lv_obj_t *home)
{
    size_t beforeFiles = used();
    FilesHarness fixture;
    fixture.launcher_screen = home;
    filesHarness = &fixture;
    fixture.openFiles();
    step();
    printf("Files screen LVGL heap: %zu bytes\n", used() - beforeFiles);
    capture("files-storage.ppm");
    fixture.sdCard = false;
    fixture.filesRefresh();
    step();
    capture("files-no-sd.ppm");
    fixture.sdCard = true;
    fixture.flashFree = 0;
    fixture.filesRefresh();
    step();
    capture("files-full.ppm");
    fixture.LittleFS.total = 0;
    fixture.filesRefresh();
    step();
    capture("files-unavailable.ppm");
    if (!baseline) {
        auto unavailable = lv_obj_get_parent(findLabel(fixture.files_screen, "Internal storage unavailable"));
        assert(lv_obj_has_state(unavailable, LV_STATE_DISABLED));
        tapObject(unavailable);
        assert(fixture.filesVol == FilesHarness::VOL_ROOT);
        fixture.messageAlert("Settings were not saved. Check internal storage.", true);
        step();
        checkDialog(objects.alert_panel);
        capture("settings-save-error.ppm");
        tap("OK");
        assert(lv_obj_has_flag(objects.alert_panel, LV_OBJ_FLAG_HIDDEN));
        char longNotice[400];
        memset(longNotice, 'W', sizeof(longNotice) - 1);
        memcpy(longNotice + sizeof(longNotice) - 5, " END", 5);
        fixture.notifyClientNotification(longNotice);
        step();
        assert(lv_obj_get_scroll_bottom(objects.alert_label) > 0);
        pointer = {150, 150};
        down = true;
        step(60);
        for (int y = 150; y >= 65; y -= 5) {
            pointer.y = y;
            step(25);
        }
        down = false;
        step(200);
        assert(lv_obj_get_scroll_y(objects.alert_label) > 0);
        lv_obj_scroll_to_y(objects.alert_label, LV_COORD_MAX, LV_ANIM_OFF);
        step();
        assert(lv_obj_get_scroll_bottom(objects.alert_label) == 0);
        checkDialog(objects.alert_panel);
        capture("settings-long-error.ppm");
        tap("OK");
        fixture.notifyClientNotification("Settings were not saved. Check internal storage.");
        step();
        size_t noticeHeap = used();
        for (int i = 0; i < 100; ++i)
            fixture.notifyClientNotification("Settings were not saved. Check internal storage.");
        step();
        assert(used() == noticeHeap);
        tap("OK");
    }
    fixture.LittleFS.total = 3538944;
    fixture.flashFree = 2500000;
    fixture.filesRefresh();
    step();
    if (baseline) {
        fixture.messageAlert("Settings were not saved. Check internal storage.", true);
        step();
        capture("settings-save-error.ppm");
        capture("settings-long-error.ppm");
        fixture.messageAlert("", false);
        fixture.filesVol = FilesHarness::VOL_SD;
        fixture.filesRefresh();
        step();
        capture("files-folder.ppm");
        auto row = lv_obj_get_child(fixture.files_list, 0);
        lv_obj_add_state(row, LV_STATE_FOCUSED);
        step();
        capture("files-focused.ppm");
        lv_obj_remove_state(row, LV_STATE_FOCUSED);
        lv_obj_add_state(row, LV_STATE_PRESSED);
        step();
        capture("files-pressed.ppm");
        lv_obj_remove_state(row, LV_STATE_PRESSED);
        lv_obj_send_event(lv_obj_get_child(fixture.files_list, 1), LV_EVENT_LONG_PRESSED, nullptr);
        step();
        capture("files-folder-held.ppm");
        fixture.filesSuppressClick = false;
        fixture.filesRefresh();
        step();
        fixture.filesNewFolderPrompt();
        step();
        capture("files-newfolder.ppm");
        fixture.closeNewFolder();
        step();
        lv_obj_send_event(lv_obj_get_child(fixture.files_list, 0), LV_EVENT_CLICKED, nullptr);
        step();
        capture("files-selected.ppm");
        fixture.filesCopyArmed = true;
        fixture.filesUpdateActionBar();
        step();
        capture("files-paste.ppm");
        fixture.filesCopyArmed = false;
        fixture.filesVol = FilesHarness::VOL_TRASH;
        fixture.filesRefresh();
        lv_obj_send_event(lv_obj_get_child(fixture.files_list, 0), LV_EVENT_CLICKED, nullptr);
        step();
        capture("files-trash.ppm");
        lv_screen_load(home);
        step();
    }
    if (!baseline) {
        char size[24];
        fmtBytes(30923764531ULL, size, sizeof(size));
        assert(!strcmp(size, "28.8 GB"));
        fmtBytesCompact(30923764531ULL, size, sizeof(size));
        assert(!strcmp(size, "28.8 GB"));
        fmtBytes(0, size, sizeof(size));
        assert(!strcmp(size, "0 B"));
        for (auto bytes : {0ULL, 1ULL, 1023ULL, 1024ULL, 1048576ULL}) {
            fmtBytes(bytes, size, sizeof(size));
            assert(!strstr(size, "lu"));
            fmtBytesCompact(bytes, size, sizeof(size));
            assert(!strstr(size, "lu"));
        }
        auto rootRow = lv_obj_get_child(fixture.files_list, 0);
        tapObject(rootRow);
        assert(fixture.filesVol == FilesHarness::VOL_SD);
        step();
        capture("files-folder.ppm");
        checkDialog(fixture.files_screen);
        auto fileRow = lv_obj_get_child(fixture.files_list, 0);
        lv_group_add_obj(lv_group_get_default(), fileRow);
        lv_group_focus_obj(fileRow);
        step();
        capture("files-focused.ppm");
        lv_group_remove_obj(fileRow);
        lv_obj_remove_state(fileRow, LV_STATE_FOCUSED);
        lv_area_t bounds;
        lv_obj_get_coords(fileRow, &bounds);
        pointer = {(lv_coord_t)((bounds.x1 + bounds.x2) / 2), (lv_coord_t)((bounds.y1 + bounds.y2) / 2)};
        down = true;
        step(80);
        capture("files-pressed.ppm");
        down = false;
        step(80);
        tap("Trail notes with a long filename.txt");
        assert(!strcmp(fixture.openedNote, "/Trail notes with a long filename.txt"));
        tap("Second.txt");
        assert(lv_color_eq(lv_obj_get_style_bg_color(fileRow, LV_PART_MAIN), lv_color_hex(Tui::Surface)));
        tap("Maps");
        assert(!strcmp(fixture.filesPath, "/Maps"));
        tap("Back");
        assert(!strcmp(fixture.filesPath, "/"));
        auto folderRow = lv_obj_get_child(fixture.files_list, 1);
        lv_obj_get_coords(folderRow, &bounds);
        pointer = {(lv_coord_t)((bounds.x1 + bounds.x2) / 2), (lv_coord_t)((bounds.y1 + bounds.y2) / 2)};
        down = true;
        step(650);
        down = false;
        step(80);
        assert(fixture.filesSelIsDir && !strcmp(fixture.filesPath, "/"));
        assert(!strcmp(fixture.filesSelName, "Maps"));
        capture("files-folder-held.ppm");
        tap("Second.txt");
        assert(!strcmp(fixture.filesSelName, "Second.txt"));
        fixture.filesRefresh();
        step();
        tap(LV_SYMBOL_PLUS " Folder");
        step();
        checkDialog(fixture.files_newfolder_ovl);
        capture("files-newfolder.ppm");
        for (char c : {'M', 'a', 'p', 's'})
            lv_group_send_data(fixture.keys, c);
        tap("OK");
        assert(!strcmp(fixture.createdName, "Maps") && fixture.folders == 1);
        tap(LV_SYMBOL_PLUS " Folder");
        tap("Cancel");
        assert(fixture.folders == 1);
        tap(LV_SYMBOL_PLUS " Folder");
        fixture.handleBackGesture();
        step();
        assert(!fixture.files_newfolder_ovl && lv_screen_active() == fixture.files_screen);
        tap("Trail notes with a long filename.txt");
        step();
        checkDialog(fixture.files_screen);
        separate(fixture.files_copy_btn, fixture.files_del_btn);
        capture("files-selected.ppm");
        tap("Copy");
        assert(fixture.filesCopyArmed);
        checkDialog(fixture.files_screen);
        assert(!strcmp(fixture.copySrcPath, "/Trail notes with a long filename.txt"));
        separate(fixture.files_copy_btn, fixture.files_cancel_btn);
        capture("files-paste.ppm");
        tap("Paste here");
        assert(fixture.copies == 1);
        tap("X");
        assert(!fixture.filesCopyArmed);
        tap("Back");
        assert(fixture.filesVol == FilesHarness::VOL_ROOT);
        tap("Trash");
        assert(fixture.filesVol == FilesHarness::VOL_TRASH);
        tap("Trail notes with a long filename.txt");
        separate(fixture.files_copy_btn, fixture.files_del_btn);
        capture("files-trash.ppm");
        tap("Restore");
        assert(fixture.restores == 1);
        tap("Delete");
        assert(fixture.filesDelConfirm && fixture.deletes == 0);
        tap("Sure?");
        assert(fixture.deletes == 1);
        tap("Back");
        tap("Back");
        assert(lv_screen_active() == home);
        fixture.openFiles();
        step();
        tapObject(lv_obj_get_child(fixture.files_list, 0));
        assert(fixture.filesVol == FilesHarness::VOL_SD);
        fixture.expanded = true;
        fixture.filesRefresh();
        step();
        pointer = {200, 175};
        down = true;
        step(60);
        for (int y = 175; y >= 85; y -= 10) {
            pointer.y = y;
            step(30);
        }
        down = false;
        step(300);
        assert(lv_obj_get_scroll_y(fixture.files_list) > 0);
        auto disabled = lv_obj_get_child(fixture.files_list, 5);
        lv_obj_scroll_to_view(disabled, LV_ANIM_OFF);
        step();
        assert(lv_obj_has_state(disabled, LV_STATE_DISABLED));
        tapObject(disabled);
        assert(!fixture.filesSelName[0]);
        tap("Last.txt");
        assert(!strcmp(fixture.filesSelName, "Last.txt"));
        fixture.expanded = false;
        tap("Back");
        tap("Back");
        fixture.openFiles();
        step(300);
        size_t filesHeap = used();
        for (int i = 0; i < 100; ++i)
            fixture.filesRefresh();
        step(300);
        assert(used() == filesHeap);
        flushes = 0;
        step(500);
        assert(flushes == 0);
        lv_screen_load(home);
        step();
        puts("PASS: 100 Files list rebuilds retain no heap; idle Files produces no flushes");
        puts("PASS: Files storage, navigation, selection, copy/paste/cancel, restore/delete routing and geometry");
    }
    lv_obj_delete(fixture.files_screen);
    lv_group_delete(fixture.keys);
    filesHarness = nullptr;
}
