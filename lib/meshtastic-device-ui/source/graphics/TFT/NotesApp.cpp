#include "graphics/view/TFT/TuiStyle.h"
// -----------------------------------------------------------------------------
// T-UI Notes — a self-contained notes app for the launcher.
//
// Notes are plain .txt files in /notes on the SD card (created on first save;
// nothing is ever scanned outside that one small folder). Two screens:
//   • List — every note, newest first, previewed by its first line. "+ New"
//     starts a fresh note; tapping a row opens it.
//   • Editor — a full-screen text box typed into with the physical keyboard.
//     Back SAVES and returns to the list (a brand-new empty note is discarded);
//     Delete removes the note for good.
// The textarea is focused via LVGL's default input group (same way the mesh
// chat input gets typed into), with a periodic refocus guard because the
// trackball encoder can wander focus. Trackball double-click = Home still works.
// -----------------------------------------------------------------------------
#include "graphics/view/TFT/TuiLabel.h"     // tui_one_line: LONG_DOT needs a height
#include "graphics/view/TFT/TuiStatusBar.h" // the persistent top bar
#include "lvgl.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>

#if HAS_SDCARD && !HAS_SD_MMC && !ARCH_PORTDUINO
#include "graphics/common/SdCard.h" // SdFat instance (SDFs) shared with maps/files
#define NOTES_HAVE_SD 1
#include <esp_heap_caps.h> // the note scratch buffer lives in PSRAM, not internal RAM
#else
#define NOTES_HAVE_SD 0
#endif

extern "C" void notes_open(void);
extern "C" void notes_open_file(const char *path); // Files app: open any .txt in the editor

namespace
{
const int kMaxNotes = 40;
const size_t kMaxNoteBytes = 4000;

lv_obj_t *listScreen = nullptr;
lv_obj_t *listPanel = nullptr; // scrollable column of note rows
lv_obj_t *editScreen = nullptr;
lv_obj_t *editArea = nullptr;     // the textarea (body)
lv_obj_t *titleArea = nullptr;    // one-line editable title, top-middle (was a "type away" hint)
lv_obj_t *editHint = nullptr;     // replaces the title box for view-only files
lv_obj_t *confirmPanel = nullptr; // "Delete this note?" overlay
lv_obj_t *focusTarget = nullptr;  // which box the keyboard is aimed at (title or body)
lv_obj_t *deleteBtn = nullptr;
lv_obj_t *saveBtn = nullptr;
lv_obj_t *prevScreen = nullptr;
lv_timer_t *focusGuard = nullptr;

unsigned noteIds[kMaxNotes];
// ⛔ PSRAM. 1,440 bytes of internal RAM for preview strings shown only on the Notes list.
// A helper rather than a raw array so every use goes through the allocation check.
static char (*notePreviewBuf)[36] = nullptr;

static char (*notePreviewArr(void))[36]
{
    if (!notePreviewBuf) {
        notePreviewBuf = (char(*)[36])heap_caps_calloc(kMaxNotes, 36, MALLOC_CAP_SPIRAM);
        if (!notePreviewBuf)
            notePreviewBuf = (char(*)[36])calloc(kMaxNotes, 36);
    }
    return notePreviewBuf;
}
#define notePreview (notePreviewArr())
int noteCount = 0;
unsigned curId = 0;        // note being edited (list mode)
bool curIsNew = false;     // brand-new note: discard if left empty
char curPath[96] = {};     // file behind the editor (works for any .txt, not just /notes)
bool curFromFiles = false; // opened via the Files app: Back returns there, no Delete
bool curReadOnly = false;  // file was too big to load fully: never save it back truncated
lv_obj_t *filesReturnScreen = nullptr;

void notePath(char *buf, size_t sz, unsigned id)
{
    snprintf(buf, sz, "/notes/n%03u.txt", id);
}

bool noteFits(void)
{
    return strlen(lv_textarea_get_text(editArea)) + (curFromFiles ? 0 : strlen(lv_textarea_get_text(titleArea)) + 1) <=
           kMaxNoteBytes;
}

const char *saveError(void)
{
    return noteFits() ? "Save failed" : "Note too long";
}

#if NOTES_HAVE_SD
bool recoverNoteSave(const char *path)
{
    char temporary[112], backup[112];
    snprintf(temporary, sizeof(temporary), "%s.tui-tmp", path);
    snprintf(backup, sizeof(backup), "%s.tui-bak", path);
    if (SDFs.exists(backup)) {
        if (!SDFs.exists(path)) {
            if (!SDFs.rename(backup, path))
                return false;
        } else if (!SDFs.remove(backup)) {
            return false;
        }
    }
    return !SDFs.exists(temporary) || SDFs.remove(temporary);
}

// scan /notes (and only /notes) for n###.txt files; preview = first line
void scanNotes(void)
{
    noteCount = 0;
    FsFile dir = SDFs.open("/notes", O_RDONLY);
    if (!dir || !dir.isDirectory())
        return;
    if (!notePreviewArr()) {
        dir.close();
        return;
    }
    FsFile entry;
    // Recover app-owned transactions before listing, including originals renamed to backup.
    while ((entry = dir.openNextFile())) {
        char name[32];
        entry.getName(name, sizeof(name));
        unsigned id;
        int consumed = 0;
        bool sidecar = !entry.isDirectory() && sscanf(name, "n%u.txt%n", &id, &consumed) == 1 && consumed > 0 &&
                       (!strcmp(name + consumed, ".tui-bak") || !strcmp(name + consumed, ".tui-tmp"));
        entry.close();
        if (sidecar) {
            char path[64];
            name[consumed] = 0;
            snprintf(path, sizeof(path), "/notes/%s", name);
            recoverNoteSave(path);
        }
    }
    dir.close();
    dir = SDFs.open("/notes", O_RDONLY);
    if (!dir)
        return;
    while ((entry = dir.openNextFile()) && noteCount < kMaxNotes) {
        char name[32];
        entry.getName(name, sizeof(name));
        unsigned id;
        int consumed = 0;
        if (!entry.isDirectory() && sscanf(name, "n%u.txt%n", &id, &consumed) == 1 && name[consumed] == 0) {
            char head[40] = {};
            int n = entry.read(head, sizeof(head) - 1);
            if (n < 0)
                n = 0;
            head[n] = 0;
            // First line = the note's title. If it was left blank, fall through to the first
            // line of the body so the row still says something useful.
            char *line = head;
            for (char *c = head; *c; c++)
                if (*c == '\r' || *c == '\n') {
                    bool blank = (c == line);
                    *c = 0;
                    if (!blank)
                        break;
                    line = c + 1; // skip the empty title and try the next line
                }
            noteIds[noteCount] = id;
            snprintf(notePreview[noteCount], sizeof(notePreview[0]), "%s", line[0] ? line : "(empty note)");
            noteCount++;
        }
        entry.close();
    }
    dir.close();
    // newest (highest id) first
    for (int i = 0; i < noteCount; i++)
        for (int j = i + 1; j < noteCount; j++)
            if (noteIds[j] > noteIds[i]) {
                unsigned t = noteIds[i];
                noteIds[i] = noteIds[j];
                noteIds[j] = t;
                char tmp[36];
                strcpy(tmp, notePreview[i]);
                strcpy(notePreview[i], notePreview[j]);
                strcpy(notePreview[j], tmp);
            }
}

unsigned nextFreeId(void)
{
    unsigned maxId = 0;
    for (int i = 0; i < noteCount; i++)
        if (noteIds[i] > maxId)
            maxId = noteIds[i];
    char path[32], temporary[48], backup[48];
    do {
        ++maxId;
        notePath(path, sizeof(path), maxId);
        snprintf(temporary, sizeof(temporary), "%s.tui-tmp", path);
        snprintf(backup, sizeof(backup), "%s.tui-bak", path);
    } while (SDFs.exists(path) || SDFs.exists(temporary) || SDFs.exists(backup));
    return maxId;
}

// Scratch space for reading a note off the card. ONE buffer, shared by both loaders, and out
// in PSRAM: at 4KB apiece these are far too big for internal RAM, which on this device has been
// measured down to under 2KB free. Freed the moment the read is done.
char *readNote(void)
{
    curReadOnly = true;
    char *buf = (char *)heap_caps_malloc(kMaxNoteBytes + 1, MALLOC_CAP_SPIRAM);
    if (!buf)
        return nullptr;
    buf[0] = 0;
    if (!curFromFiles && !recoverNoteSave(curPath))
        return buf;
    FsFile f = SDFs.open(curPath, O_RDONLY);
    if (f) {
        curReadOnly = f.size() > kMaxNoteBytes; // too big: show the start, never save back
        int n = f.read(buf, kMaxNoteBytes);
        if (n < 0 || (size_t)n != (f.size() < kMaxNoteBytes ? f.size() : kMaxNoteBytes)) {
            curReadOnly = true;
            n = n < 0 ? 0 : n;
        }
        if (memchr(buf, 0, n))
            curReadOnly = true;
        buf[n] = 0;
        f.close();
    }
    return buf;
}

// pull curPath into the title + body boxes
void loadCurPathIntoEditor(void)
{
    char *buf = readNote();
    if (!buf) {
        lv_textarea_set_text(titleArea, "");
        lv_textarea_set_text(editArea, "");
        return;
    }
    // The first line IS the title — it always was, in the sense that the list preview shows it.
    // Now it gets its own box at the top instead of sitting invisibly at the start of the body.
    char *nl = strchr(buf, '\n');
    size_t titleCharacters = 0;
    for (const char *c = buf; *c && *c != '\n'; ++c)
        if ((*c & 0xc0) != 0x80)
            ++titleCharacters;
    if (curReadOnly || titleCharacters > 40) {
        curReadOnly = true;
        lv_textarea_set_text(titleArea, "");
        lv_textarea_set_text(editArea, buf);
    } else if (nl) {
        *nl = 0;
        lv_textarea_set_text(titleArea, buf);
        lv_textarea_set_text(editArea, nl + 1);
    } else {
        lv_textarea_set_text(titleArea, buf);
        lv_textarea_set_text(editArea, "");
    }
    heap_caps_free(buf);
}

// Files app: the whole file goes in the body. Splitting a first line off an arbitrary .txt
// would silently move a line of somebody's file into a title box it can't even see.
void loadFileIntoEditor(void)
{
    char *buf = readNote();
    lv_textarea_set_text(editArea, buf ? buf : "");
    if (buf)
        heap_caps_free(buf);
}

bool saveCurrentNote(bool createEmpty = false)
{
    if (curReadOnly)
        return true;
    const char *text = lv_textarea_get_text(editArea);
    const char *title = curFromFiles ? "" : lv_textarea_get_text(titleArea);
    if (!createEmpty && curIsNew && !*text && !*title)
        return true;
    if (!noteFits())
        return false;
    if (!curFromFiles && !recoverNoteSave(curPath))
        return false;
    if (!curFromFiles && !SDFs.exists("/notes") && !SDFs.mkdir("/notes"))
        return false;
    char temporary[112], backup[112];
    snprintf(temporary, sizeof(temporary), "%s.tui-tmp", curPath);
    snprintf(backup, sizeof(backup), "%s.tui-bak", curPath);
    if (SDFs.exists(backup) || SDFs.exists(temporary))
        return false;
    FsFile f = SDFs.open(temporary, O_WRONLY | O_CREAT | O_EXCL);
    if (!f)
        return false;
    bool okay = true;
    if (!curFromFiles) {
        okay = f.write((const uint8_t *)title, strlen(title)) == strlen(title);
        okay = f.write((const uint8_t *)"\n", 1) == 1 && okay;
    }
    okay = f.write((const uint8_t *)text, strlen(text)) == strlen(text) && okay;
    okay = f.sync() && okay;
    okay = f.close() && okay;
    if (!okay) {
        SDFs.remove(temporary);
        return false;
    }
    const bool existed = SDFs.exists(curPath);
    if (existed && !SDFs.rename(curPath, backup)) {
        SDFs.remove(temporary);
        return false;
    }
    if (!SDFs.rename(temporary, curPath)) {
        if (existed)
            SDFs.rename(backup, curPath);
        SDFs.remove(temporary);
        return false;
    }
    if (existed)
        SDFs.remove(backup);
    curIsNew = false;
    return true;
}

bool deleteCurrentNote(void)
{
    if (!curFromFiles && !recoverNoteSave(curPath))
        return false;
    return !SDFs.exists(curPath) || SDFs.remove(curPath);
}
#else
void scanNotes(void)
{
    noteCount = 0;
}
unsigned nextFreeId(void)
{
    return 1;
}
void loadCurPathIntoEditor(void)
{
    lv_textarea_set_text(editArea, "");
    if (titleArea)
        lv_textarea_set_text(titleArea, "");
}
void loadFileIntoEditor(void)
{
    lv_textarea_set_text(editArea, "");
}
bool saveCurrentNote(bool createEmpty = false)
{
    return !createEmpty && curIsNew && !*lv_textarea_get_text(editArea) && !*lv_textarea_get_text(titleArea);
}
bool deleteCurrentNote(void)
{
    return curIsNew;
}
#endif

// ---------------- UI ----------------
lv_obj_t *barBtn(lv_obj_t *parent, const char *txt, int w, lv_align_t align, int xofs, uint32_t color, lv_event_cb_t cb)
{
    lv_obj_t *btn = lv_btn_create(parent);
    Tui::headerButton(btn);
    lv_obj_set_width(btn, w);
    lv_obj_align(btn, align, xofs, 4);
    lv_obj_set_style_radius(btn, 8, LV_PART_MAIN);
    lv_obj_set_style_bg_color(btn, lv_color_hex(color), LV_PART_MAIN);
    lv_obj_add_event_cb(btn, cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *lbl = lv_label_create(btn);
    lv_label_set_text(lbl, txt);
    lv_obj_center(lbl);
    return btn;
}

void rebuildList(void);
void openEditor(unsigned id, bool isNew);

// "Delete this note?" — a child of editScreen, hidden until Delete is tapped. A child rather
// than lv_layer_top on purpose: the layer is shared with the mesh pop-ups, and the launcher's
// "am I typing?" test has been caught out by it before.
void buildConfirmPanel(void)
{
    confirmPanel = lv_obj_create(editScreen);
    lv_obj_set_size(confirmPanel, 272, 120);
    lv_obj_center(confirmPanel);
    lv_obj_set_style_pad_all(confirmPanel, 12, 0);
    lv_obj_set_style_bg_color(confirmPanel, lv_color_hex(Tui::Border), LV_PART_MAIN);
    lv_obj_set_style_border_color(confirmPanel, lv_color_hex(0x636366), LV_PART_MAIN);
    lv_obj_set_style_border_width(confirmPanel, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(confirmPanel, 12, LV_PART_MAIN);
    lv_obj_clear_flag(confirmPanel, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(confirmPanel, LV_OBJ_FLAG_HIDDEN);

    lv_obj_t *q = lv_label_create(confirmPanel);
    lv_label_set_text(q, "Delete this note?");
    lv_obj_set_style_text_color(q, lv_color_hex(Tui::Text), LV_PART_MAIN);
    lv_obj_align(q, LV_ALIGN_TOP_MID, 0, 0);

    lv_obj_t *sub = lv_label_create(confirmPanel);
    lv_label_set_text(sub, "This cannot be undone.");
    lv_obj_set_style_text_color(sub, lv_color_hex(Tui::Muted), LV_PART_MAIN);
    lv_obj_set_style_text_font(sub, &ui_font_montserrat_12, 0);
    lv_obj_align(sub, LV_ALIGN_TOP_MID, 0, 26);

    lv_obj_t *cancel = barBtn(confirmPanel, "Cancel", 92, LV_ALIGN_BOTTOM_LEFT, 0, Tui::Surface,
                              [](lv_event_t *) { lv_obj_add_flag(confirmPanel, LV_OBJ_FLAG_HIDDEN); });
    lv_obj_t *del = barBtn(confirmPanel, "Delete", 92, LV_ALIGN_BOTTOM_RIGHT, 0, 0xff453a, [](lv_event_t *) {
        lv_obj_add_flag(confirmPanel, LV_OBJ_FLAG_HIDDEN);
        if (!deleteCurrentNote()) {
            lv_label_set_text(editHint, "Delete failed");
            lv_obj_clear_flag(editHint, LV_OBJ_FLAG_HIDDEN);
            return;
        }
        rebuildList();
        lv_screen_load_anim(listScreen, LV_SCR_LOAD_ANIM_NONE, 0, 0, false);
    });
    // barBtn aligns with a +4 y-offset meant for a top bar; pull both back onto the panel floor.
    lv_obj_set_y(cancel, 0);
    lv_obj_set_y(del, 0);
}

void buildListScreen(void)
{
    listScreen = lv_obj_create(NULL);
    tui_statusbar_reserve(listScreen); // note item A4: the persistent top bar
    lv_obj_set_style_bg_color(listScreen, lv_color_hex(Tui::Background), LV_PART_MAIN);
    lv_obj_clear_flag(listScreen, LV_OBJ_FLAG_SCROLLABLE);

    barBtn(listScreen, "Back", 64, LV_ALIGN_TOP_LEFT, 8, Tui::Surface, [](lv_event_t *) {
        if (prevScreen)
            lv_screen_load_anim(prevScreen, LV_SCR_LOAD_ANIM_NONE, 0, 0, false);
    });

    lv_obj_t *title = lv_label_create(listScreen);
    lv_label_set_text(title, "Notes");
    lv_obj_set_style_text_color(title, lv_color_hex(Tui::Text), LV_PART_MAIN);
    Tui::headerTitle(title);

    barBtn(listScreen, "+ New", 64, LV_ALIGN_TOP_RIGHT, -8, 0x294c54, [](lv_event_t *) { openEditor(nextFreeId(), true); });

    listPanel = lv_obj_create(listScreen);
    lv_obj_remove_style_all(listPanel);
    lv_obj_set_pos(listPanel, 8, 40);
    lv_obj_set_size(listPanel, 304, 172);
    lv_obj_set_flex_flow(listPanel, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_all(listPanel, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_row(listPanel, 6, LV_PART_MAIN);
    lv_obj_set_scroll_dir(listPanel, LV_DIR_VER);
}

void rebuildList(void)
{
    lv_obj_clean(listPanel);
    scanNotes();

#if NOTES_HAVE_SD
    if (noteCount == 0) {
        lv_obj_t *empty = lv_label_create(listPanel);
        lv_label_set_text(empty, notePreviewArr() ? "No notes yet" : "Not enough memory");
        lv_obj_set_style_text_color(empty, lv_color_hex(Tui::Muted), LV_PART_MAIN);
    }
#else
    lv_obj_t *empty = lv_label_create(listPanel);
    lv_label_set_text(empty, "Notes needs the SD card");
    lv_obj_set_style_text_color(empty, lv_color_hex(Tui::Muted), LV_PART_MAIN);
#endif

    for (int i = 0; i < noteCount; i++) {
        lv_obj_t *row = lv_btn_create(listPanel);
        lv_obj_set_size(row, LV_PCT(100), 36);
        lv_obj_set_style_bg_color(row, lv_color_hex(Tui::Surface), LV_PART_MAIN);
        lv_obj_set_style_radius(row, 10, LV_PART_MAIN);
        lv_obj_add_event_cb(
            row,
            [](lv_event_t *e) {
                int idx = (int)(intptr_t)lv_event_get_user_data(e);
                if (idx < noteCount)
                    openEditor(noteIds[idx], false);
            },
            LV_EVENT_CLICKED, (void *)(intptr_t)i);
        lv_obj_t *lbl = lv_label_create(row);
        lv_label_set_text(lbl, notePreview[i]);
        lv_obj_set_style_text_color(lbl, lv_color_hex(Tui::Text), LV_PART_MAIN);
        lv_label_set_long_mode(lbl, LV_LABEL_LONG_DOT);
        tui_one_line(lbl); // LONG_DOT needs a pinned height - see TuiLabel.h
        lv_obj_set_width(lbl, LV_PCT(100));
        lv_obj_align(lbl, LV_ALIGN_LEFT_MID, 0, 0);
    }
}

void buildEditScreen(void)
{
    editScreen = lv_obj_create(NULL);
    tui_statusbar_reserve(editScreen); // note item A4: the persistent top bar
    lv_obj_set_style_bg_color(editScreen, lv_color_hex(Tui::Background), LV_PART_MAIN);
    lv_obj_clear_flag(editScreen, LV_OBJ_FLAG_SCROLLABLE);

    // Back = save + return to wherever the note was opened from (list or Files)
    barBtn(editScreen, "Back", 64, LV_ALIGN_TOP_LEFT, 8, Tui::Surface, [](lv_event_t *) {
        if (!saveCurrentNote()) {
            lv_label_set_text(editHint, saveError());
            lv_obj_clear_flag(editHint, LV_OBJ_FLAG_HIDDEN);
            return;
        }
        if (curFromFiles && filesReturnScreen) {
            lv_screen_load_anim(filesReturnScreen, LV_SCR_LOAD_ANIM_NONE, 0, 0, false);
            return;
        }
        rebuildList();
        lv_screen_load_anim(listScreen, LV_SCR_LOAD_ANIM_NONE, 0, 0, false);
    });

    // The note's TITLE, editable, where the grey "type away" hint used to be. It is the first
    // line of the file, so nothing about the on-card format changes and the list preview still
    // shows exactly what this box shows.
    titleArea = lv_textarea_create(editScreen);
    lv_textarea_set_one_line(titleArea, true);
    lv_obj_set_size(titleArea, 304, 28);
    lv_obj_align(titleArea, LV_ALIGN_TOP_MID, 0, 40);
    lv_obj_set_style_bg_color(titleArea, lv_color_hex(Tui::Surface), LV_PART_MAIN);
    lv_obj_set_style_text_color(titleArea, lv_color_hex(Tui::Text), LV_PART_MAIN);
    lv_obj_set_style_border_width(titleArea, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(titleArea, 6, LV_PART_MAIN);
    lv_obj_set_style_pad_all(titleArea, 3, LV_PART_MAIN);
    lv_obj_set_style_bg_color(titleArea, lv_color_hex(Tui::Text), LV_PART_CURSOR);
    lv_obj_set_style_bg_opa(titleArea, LV_OPA_50, LV_PART_CURSOR);
    lv_obj_set_style_anim_duration(titleArea, 0, LV_PART_CURSOR);
    // ⛔ AND DELETE THE ANIMATION THAT ALREADY EXISTS. lv_textarea_create() starts a
    // blinking cursor during construction using the DEFAULT time, so setting the duration to
    // zero above does not stop it - start_cursor_blink only re-reads that on focus, or on a
    // style change delivered to the label child. An active LVGL animation then forces a
    // refresh EVERY FRAME: measured 17-18 fps and 124-280 KB/s pushed while sitting idle,
    // against 2 fps once it is gone. Any later focus re-runs the check, finds the zero and
    // deletes it itself, so this one call is all that is needed.
    lv_anim_delete(titleArea, nullptr);
    lv_textarea_set_max_length(titleArea, 40);
    lv_textarea_set_placeholder_text(titleArea, "Title");
    if (lv_group_get_default())
        lv_group_add_obj(lv_group_get_default(), titleArea);
    // Tapping a box aims the keyboard at it. Without this the focus guard below would drag
    // focus straight back to the body and the title could never be typed into.
    lv_obj_add_event_cb(
        titleArea, [](lv_event_t *) { focusTarget = titleArea; }, LV_EVENT_CLICKED, NULL);

    // Kept for view-only files, which have no editable title (see notes_open_file).
    editHint = lv_label_create(editScreen);
    lv_label_set_text(editHint, "");
    lv_obj_set_style_text_color(editHint, lv_color_hex(Tui::Muted), LV_PART_MAIN);
    lv_obj_set_style_text_font(editHint, &ui_font_montserrat_12, 0);
    lv_obj_set_size(editHint, 304, 16);
    lv_obj_align(editHint, LV_ALIGN_BOTTOM_MID, 0, -8);
    lv_obj_add_flag(editHint, LV_OBJ_FLAG_HIDDEN);

    // only shown for notes opened from the list; Files has its own Trash button.
    // Deleting is permanent, so it asks first (Jake, 2026-09-18).
    deleteBtn = barBtn(editScreen, "Delete", 64, LV_ALIGN_TOP_RIGHT, -8, 0xff453a, [](lv_event_t *) {
        lv_obj_move_foreground(confirmPanel);
        lv_obj_clear_flag(confirmPanel, LV_OBJ_FLAG_HIDDEN);
    });

    saveBtn = barBtn(editScreen, "Save", 72, LV_ALIGN_TOP_MID, 0, 0x294c54, [](lv_event_t *) {
        if (curReadOnly)
            return;
        const bool saved = saveCurrentNote(true);
        lv_label_set_text(editHint, saved ? "Saved" : saveError());
        lv_obj_clear_flag(editHint, LV_OBJ_FLAG_HIDDEN);
    });
    buildConfirmPanel();

    editArea = lv_textarea_create(editScreen);
    lv_obj_set_pos(editArea, 8, 76);
    lv_obj_set_size(editArea, 304, 116);
    lv_obj_set_style_bg_color(editArea, lv_color_hex(Tui::Surface), LV_PART_MAIN);
    lv_obj_set_style_text_color(editArea, lv_color_hex(Tui::Text), LV_PART_MAIN);
    lv_obj_set_style_border_width(editArea, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(editArea, 0, LV_PART_MAIN);
    // Visible caret. A blinking thin line proved unreliable — it only repainted
    // when the screen changed (so it seemed to appear only on Back). Use a SOLID,
    // non-blinking, semi-transparent white block over the character position: it's
    // clearly visible and doesn't depend on the blink timer firing a repaint.
    // (anim_duration 0 => LVGL keeps the cursor shown solid whenever focused.)
    lv_obj_set_style_bg_color(editArea, lv_color_hex(Tui::Text), LV_PART_CURSOR);
    lv_obj_set_style_bg_opa(editArea, LV_OPA_50, LV_PART_CURSOR);
    lv_obj_set_style_anim_duration(editArea, 0, LV_PART_CURSOR);
    lv_anim_delete(editArea, nullptr);
    lv_textarea_set_max_length(editArea, kMaxNoteBytes);
    lv_textarea_set_placeholder_text(editArea, "Note");
    if (lv_group_get_default())
        lv_group_add_obj(lv_group_get_default(), editArea);
    lv_obj_add_event_cb(
        editArea, [](lv_event_t *) { focusTarget = editArea; }, LV_EVENT_CLICKED, NULL);

    // keep the physical keyboard aimed at the textarea while the editor is up
    focusGuard = lv_timer_create(
        [](lv_timer_t *) {
            if (curReadOnly)
                return;
            lv_group_t *g = lv_group_get_default();
            lv_obj_t *want = focusTarget ? focusTarget : editArea;
            if (g && lv_group_get_focused(g) != want)
                lv_group_focus_obj(want);
        },
        300, NULL);
    lv_timer_pause(focusGuard);

    lv_obj_add_event_cb(
        editScreen,
        [](lv_event_t *) {
            if (curReadOnly)
                return;
            lv_timer_resume(focusGuard);
            if (lv_group_get_default())
                lv_group_focus_obj(focusTarget ? focusTarget : editArea);
        },
        LV_EVENT_SCREEN_LOADED, NULL);
    lv_obj_add_event_cb(
        editScreen, [](lv_event_t *) { lv_timer_pause(focusGuard); }, LV_EVENT_SCREEN_UNLOADED, NULL);
}

void updateEditorMode(void)
{
    const bool bodyOnly = curFromFiles || curReadOnly;
    if (bodyOnly)
        lv_obj_add_flag(titleArea, LV_OBJ_FLAG_HIDDEN);
    else
        lv_obj_clear_flag(titleArea, LV_OBJ_FLAG_HIDDEN);
    lv_obj_set_pos(editArea, 8, bodyOnly ? 40 : 76);
    lv_obj_set_size(editArea, 304, bodyOnly ? 152 : 116);
    lv_obj_t *fields[] = {titleArea, editArea};
    for (lv_obj_t *field : fields) {
        if (curReadOnly) {
            lv_group_remove_obj(field);
            lv_obj_clear_flag(field, LV_OBJ_FLAG_CLICK_FOCUSABLE);
            lv_obj_remove_state(field, LV_STATE_FOCUSED);
        } else {
            lv_obj_add_flag(field, LV_OBJ_FLAG_CLICK_FOCUSABLE);
            if (lv_group_get_default())
                lv_group_add_obj(lv_group_get_default(), field);
        }
    }
    if (curReadOnly) {
        lv_obj_add_state(saveBtn, LV_STATE_DISABLED);
        lv_label_set_text(editHint, "Read only");
        lv_obj_clear_flag(editHint, LV_OBJ_FLAG_HIDDEN);
        lv_timer_pause(focusGuard);
    } else {
        lv_obj_remove_state(saveBtn, LV_STATE_DISABLED);
    }
}

void openEditor(unsigned id, bool isNew)
{
    if (!editScreen)
        buildEditScreen();
    curId = id;
    curIsNew = isNew;
    curFromFiles = false;
    curReadOnly = false;
    notePath(curPath, sizeof(curPath), id);
    lv_obj_clear_flag(deleteBtn, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(editHint, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(titleArea, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(confirmPanel, LV_OBJ_FLAG_HIDDEN);
    // A new note starts with the cursor in the title; an existing one in the body, where you are
    // far more likely to be adding to it.
    focusTarget = isNew ? titleArea : editArea;
    if (isNew) {
        lv_textarea_set_text(titleArea, "");
        lv_textarea_set_text(editArea, "");
    } else {
        loadCurPathIntoEditor();
    }
    updateEditorMode();
    lv_screen_load_anim(editScreen, LV_SCR_LOAD_ANIM_NONE, 0, 0, false);
}
} // namespace

extern "C" void notes_open(void)
{
    lv_obj_t *active = lv_screen_active();
    if (active != listScreen && active != editScreen)
        prevScreen = active; // remember the launcher, not our own screens
    if (!listScreen)
        buildListScreen();
    rebuildList();
    lv_screen_load_anim(listScreen, LV_SCR_LOAD_ANIM_NONE, 0, 0, false);
}

// Files app hook: open any .txt on the SD card in the editor. Back saves and
// returns to the Files screen; oversized files open view-only (never saved back).
extern "C" void notes_open_file(const char *path)
{
#if NOTES_HAVE_SD
    if (!path || !*path || strlen(path) >= sizeof(curPath))
        return;
    if (!editScreen)
        buildEditScreen();
    snprintf(curPath, sizeof(curPath), "%s", path);
    curId = 0;
    curIsNew = false;
    curFromFiles = true;
    filesReturnScreen = lv_screen_active();
    lv_obj_add_flag(deleteBtn, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(confirmPanel, LV_OBJ_FLAG_HIDDEN);
    // A file from the Files app is not a note: its first line is just its first line, so hide the
    // title box and load the whole thing into the body, exactly as before.
    lv_obj_add_flag(titleArea, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(editHint, LV_OBJ_FLAG_HIDDEN);
    focusTarget = editArea;
    loadFileIntoEditor();
    lv_label_set_text(editHint, curReadOnly ? "Read only" : "");
    updateEditorMode();
    lv_screen_load_anim(editScreen, LV_SCR_LOAD_ANIM_NONE, 0, 0, false);
#else
    (void)path;
#endif
}
