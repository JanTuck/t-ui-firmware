"""Build a self-contained before/after gallery from native LVGL captures."""
import argparse
import base64
import html
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path)
args = parser.parse_args()
states = [
    ("settings-display", "Settings: display"),
    ("settings-location", "Settings: location"), ("settings-network", "Settings: network"),
    ("settings-sound", "Settings: sound"), ("settings-mesh", "Settings: mesh"),
    ("settings-system", "Settings: system"), ("settings-zones", "Settings: timezone menu"),
    ("settings-cursor", "Settings: cursor on"), ("settings-cursor-off", "Settings: cursor off"),
    ("settings-tools", "Settings: tools"), ("settings-location-error", "Settings: GPS unavailable"),
    ("pin-pad", "PIN: actual custom layout"), ("pin-too-short", "PIN: too short"), ("pin-wrong", "PIN: incorrect"),
    ("home", "Launcher"), ("focus", "Launcher: widget focus"),
    ("pressed", "Launcher: pressed"), ("last-page", "Launcher: long name"),
    ("calculator", "Calculator"), ("clock", "Stopwatch"), ("timer", "Timer"),
    ("alarm", "Alarm"), ("notes", "Notes: no SD card"),
    ("note-editor", "Notes: editor"), ("note-delete", "Notes: delete dialog"),
    ("node-actions", "Node actions"), ("nodes", "Nodes"), ("favorites", "Favorites"), ("chats", "Chats"),
    ("mesh", "Mesh: base home"), ("mesh-settings", "Mesh: base settings"), ("mesh-tools", "Mesh: base tools"),
    ("lock-base", "Lock: generated base keypad"),
]
sections = []
options = []
for i, (stem, title) in enumerate(states):
    paths = [args.directory / (prefix + stem + ".png") for prefix in ("baseline-", "")]
    if not all(path.exists() for path in paths):
        raise SystemExit(f"Missing old/new captures for {stem}")
    options.append(f'<option value="{i}">{html.escape(title)}</option>')
    frames = []
    for label, path in zip(("Old", "New"), paths):
        uri = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
        frames.append(f'<figure><figcaption>{label}</figcaption><div class="frame"><img src="{uri}" alt="{label}: {html.escape(title)}"><div class="grid"></div></div></figure>')
    sections.append(f'<section data-index="{i}" {"hidden" if i else ""}>' + "".join(frames) + "</section>")
page = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<style>
body { margin: 0; color: var(--foreground, #243444); font-family: var(--font-sans, system-ui); }
.controls { display:flex; flex-wrap:wrap; align-items:center; gap:16px; margin-bottom:12px; }
select,button { font:inherit; padding:8px; border:1px solid var(--border,#80909c); border-radius:6px; background:var(--card,#fff); color:inherit; }
section { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
section[hidden] { display:none; }
figure { margin:0; }
figcaption { margin-bottom:8px; font-weight:600; }
.frame { position:relative; max-width:640px; }
img { width:100%; display:block; image-rendering:pixelated; }
.grid { display:none; position:absolute; inset:0; pointer-events:none; background-image:linear-gradient(to right, #64d2ff44 1px,transparent 1px),linear-gradient(to bottom,#64d2ff44 1px,transparent 1px); background-size:2.5% 3.33333%; }
body.grids .grid { display:block; }
p { font-size:13px; line-height:1.5; color:var(--muted-foreground,#647482); }
</style></head><body><div class="controls"><select aria-label="Screen">OPTIONS</select><label><input type="checkbox"> 8-pixel grid</label></div>
SECTIONS
<p>Native LVGL component renders: original revision cd363f267 versus the PR. Matching fixtures; no hardware emulation. The base mesh/keypad views exclude firmware controller updates. Settings renders the real layout with fixture values and no device callbacks. Lock authorization/glance, Files, Maps, network apps and SD-backed flows are not reproduced here. Focus shows widget states; the legacy physical focus-navigation mode remains disabled.</p>
<script>
document.querySelector('select').onchange=function(){document.querySelectorAll('section').forEach(s=>s.hidden=s.dataset.index!==this.value);};
document.querySelector('input').onchange=function(){document.body.classList.toggle('grids',this.checked);};
</script></body></html>"""
page = page.replace("OPTIONS", "".join(options)).replace("SECTIONS", "".join(sections))
(args.directory / "comparison.html").write_text(page, encoding="utf-8")
