"""Offline original artwork for the 320x240 launcher. Requires Pillow; no runtime rasterizer."""

from math import cos, exp, pi, sin
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
S = 4
N = 48
names = [
    "Mesh",
    "Notes",
    "Gemini",
    "Mail",
    "Chess",
    "Calculator",
    "Breakout",
    "Metronome",
    "Files",
    "Maps",
    "Settings",
    "Get Apps",
    "Snake",
    "Flashlight",
    "Clock",
    "Nodes",
    "Favorites",
    "Chats",
    "Alerts",
    "App",
]
colors = [
    ("9b6bff", "5327c5"),
    ("ffe77c", "efa91c"),
    ("76caff", "5151d5"),
    ("69cfff", "0873e5"),
    ("dde8f0", "778aa6"),
    ("67778a", "263449"),
    ("8d9bff", "3f49ca"),
    ("ff9e88", "d74064"),
    ("72caff", "1769d3"),
    ("a0e984", "34b58c"),
    ("c9d1df", "69788f"),
    ("78b4ff", "3356e3"),
    ("a3e85f", "259c56"),
    ("ffe78b", "ec9d39"),
    ("485166", "141b2c"),
    ("6ddcdd", "167cae"),
    ("ffd774", "ef9430"),
    ("88ed8a", "20ac64"),
    ("ff92ad", "e34569"),
    ("ad9bff", "6653c4"),
]


def glyph(name, size=48):
    im = Image.new("RGBA", (size * S, size * S))
    d = ImageDraw.Draw(im)
    k = size * S / 48

    def pts(p):
        return [(round(x * k), round(y * k)) for x, y in p]

    def line(p, fill="white", w=2.5):
        p = pts(p)
        r = w * k / 2
        d.line(p, fill=fill, width=round(w * k), joint="curve")
        for x, y in [p[0], p[-1]]:
            d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

    def box(b, r=3, fill="white", outline=None, w=2):
        d.rounded_rectangle(
            tuple(round(v * k) for v in b),
            round(r * k),
            fill=fill,
            outline=outline,
            width=round(w * k),
        )

    def circle(x, y, r, fill="white", outline=None, w=2):
        d.ellipse(
            tuple(round(v * k) for v in (x - r, y - r, x + r, y + r)),
            fill=fill,
            outline=outline,
            width=round(w * k),
        )

    def poly(p, fill="white"):
        d.polygon(pts(p), fill=fill)

    def arc(b, a, z, w=2.5):
        d.arc(tuple(round(v * k) for v in b), a, z, fill="white", width=round(w * k))

    if name in ("Mesh", "Nodes"):
        line([(13, 31), (24, 14), (36, 31), (13, 31)], "#e1dfff", 2)
        for x, y in [(13, 31), (24, 14), (36, 31)]:
            circle(x, y, 5)
        if name == "Nodes":
            circle(24, 25, 3)
    elif name == "Notes":
        box((10, 9, 38, 39), 4, "#fffef5")
        box((10, 9, 38, 17), 3, "#fff4ae")
        for y in (23, 28, 33):
            line([(15, y), (33, y)], "#b9a875", 1)
    elif name == "Gemini":
        p = []
        for i in range(128):
            a = i * 2 * pi / 128
            p.append((24 + 16 * cos(a) ** 3, 24 + 16 * sin(a) ** 3))
        poly(p)
    elif name == "Mail":
        box((8, 13, 40, 35), 4)
        line([(10, 16), (24, 26), (38, 16)], "#2583dc", 1.7)
    elif name == "Chess":
        poly(
            [
                (13, 36),
                (15, 30),
                (20, 24),
                (14, 24),
                (12, 21),
                (20, 11),
                (26, 10),
                (31, 15),
                (34, 30),
                (36, 36),
            ],
            "#fafcff",
        )
        circle(23, 17, 1.2, "#52647d")
        line([(14, 38), (36, 38)], "#fff", 2)
    elif name == "Calculator":
        box((10, 8, 38, 18), 3, "#d4e2df")
        for x in (14, 24, 34):
            for y in (25, 34):
                circle(x, y, 3.5, "#ffa93d" if x == 34 else "#c3cedb")
    elif name == "Breakout":
        for y in (11, 19):
            for x in (8, 20, 32):
                box((x, y, x + 9, y + 5), 1, "#ffcd7a" if y == 11 else "#a6eeff")
        circle(28, 30, 2.5)
        box((15, 37, 34, 40), 1.5)
    elif name == "Metronome":
        poly([(24, 9), (11, 38), (37, 38)], "#fff3df")
        line([(24, 31), (32, 15)], "#a84357", 2)
        circle(24, 31, 2.5, "#a84357")
    elif name == "Files":
        box((8, 12, 23, 20), 3, "#ccecff")
        box((8, 16, 40, 37), 4, "#f4fbff")
        line([(13, 21), (35, 21)], "#fff", 1)
    elif name == "Maps":
        poly(
            [
                (5, 9),
                (19, 12),
                (32, 7),
                (43, 11),
                (43, 39),
                (30, 36),
                (18, 41),
                (5, 37),
            ],
            "#e7f4dd",
        )
        line([(17, 12), (17, 39)], "#adceaa", 1)
        line([(32, 10), (32, 36)], "#adceaa", 1)
        line([(7, 32), (20, 24), (41, 24)], "#fff", 7)
        line([(7, 32), (20, 24), (41, 24)], "#f3c35f", 3)
        circle(28, 21, 7, "#2889ef")
        poly([(24, 25), (28, 32), (32, 25)], "#2889ef")
        circle(28, 21, 2.5)
    elif name == "Settings":
        p = []
        for i in range(64):
            a = i * 2 * pi / 64
            r = 16 if i % 8 in (1, 2, 3, 4) else 13
            p.append((24 + r * cos(a), 24 + r * sin(a)))
        poly(p, "#eef3fa")
        circle(24, 24, 10, "#6e7d95")
        circle(24, 24, 7, None, "#fff", 2)
        circle(24, 24, 3, "#dbe5f2")
    elif name == "Get Apps":
        line([(24, 10), (24, 29)], w=3)
        line([(17, 23), (24, 30), (31, 23)], w=3)
        line([(11, 31), (11, 37), (37, 37), (37, 31)], w=2.5)
    elif name == "Snake":
        line(
            [
                (12, 34),
                (30, 34),
                (34, 30),
                (34, 23),
                (18, 23),
                (14, 19),
                (14, 14),
                (29, 14),
            ],
            w=6,
        )
        circle(29, 13, 1, "#318745")
    elif name == "Flashlight":
        poly(
            [
                (14, 10),
                (34, 10),
                (31, 20),
                (28, 24),
                (28, 38),
                (20, 38),
                (20, 24),
                (17, 20),
            ],
            "#fff9e4",
        )
        line([(18, 17), (30, 17)], "#d99737", 2)
        box((22, 26, 26, 31), 1, "#d99737")
    elif name == "Clock":
        circle(24, 24, 17, "#f7fafc")
        for i in range(12):
            a = i * pi / 6
            line(
                [
                    (24 + 14 * sin(a), 24 - 14 * cos(a)),
                    (24 + 12.5 * sin(a), 24 - 12.5 * cos(a)),
                ],
                "#768092",
                1,
            )
        line([(24, 14), (24, 24), (31, 28)], "#253148", 2)
        line([(24, 24), (18, 32)], "#f69c38", 1)
        circle(24, 24, 1.7, "#253148")
    elif name == "Favorites":
        poly(
            [
                (
                    24 + (16 if i % 2 == 0 else 7) * sin(i * pi / 5),
                    24 - (16 if i % 2 == 0 else 7) * cos(i * pi / 5),
                )
                for i in range(10)
            ]
        )
    elif name == "Chats":
        box((8, 12, 40, 33), 9)
        poly([(13, 29), (12, 38), (23, 31)])
    elif name == "Alerts":
        box((15, 12, 33, 32), 9)
        poly([(15, 22), (12, 33), (36, 33), (33, 22)])
        circle(24, 36, 3)
        circle(24, 11, 2)
    elif name == "Wifi":
        for r in (17, 11, 5):
            arc((24 - r, 28 - r, 24 + r, 28 + r), 220, 320, 3)
        circle(24, 30, 2)
    elif name == "Bluetooth":
        line([(23, 7), (23, 41), (33, 31), (15, 16)], w=2.5)
        line([(23, 7), (33, 17), (15, 32)], w=2.5)
    elif name == "Gps":
        poly([(9, 23), (38, 10), (27, 39), (22, 27)])
    elif name == "Sun":
        circle(24, 24, 7, None, "white", 2)
        for i in range(8):
            a = i * pi / 4
            line(
                [
                    (24 + 11 * cos(a), 24 + 11 * sin(a)),
                    (24 + 15 * cos(a), 24 + 15 * sin(a)),
                ],
                w=2,
            )
    else:
        for x, y in [(16, 16), (30, 16), (16, 30), (30, 30)]:
            box((x - 5, y - 5, x + 5, y + 5), 3)
    return im


assets = []
for name, (top, bottom) in zip(names, colors):
    a = tuple(bytes.fromhex(top))
    b = tuple(bytes.fromhex(bottom))
    im = Image.new("RGBA", (N * S, N * S))
    pix = im.load()
    for y in range(N * S):
        for x in range(N * S):
            xx = (x + 0.5) / (N * S)
            yy = (y + 0.5) / (N * S)
            edge = abs((xx - 0.5) / 0.485) ** 4 + abs((yy - 0.5) / 0.485) ** 4
            if edge > 1:
                continue
            t = yy * 0.85 + xx * 0.15
            shine = 16 * exp(-((xx - 0.3) ** 2 + (yy - 0.12) ** 2) / 0.09)
            rim = 40 * max(0, (edge - 0.86) / 0.14) * (1 - yy)
            pix[x, y] = tuple(
                min(255, round(a[i] * (1 - t) + b[i] * t + shine + rim))
                for i in range(3)
            ) + (255,)
    g = glyph(name)
    shadow = Image.new("RGBA", im.size)
    shadow.paste(g, (0, 3 * S))
    shadow.putalpha(shadow.getchannel("A").point(lambda v: v // 6))
    # The foreground's fine shadow is baked; no runtime shadows or blur.
    im.alpha_composite(shadow)
    im.alpha_composite(g)
    im = im.resize((N, N), Image.Resampling.LANCZOS)
    assets.append((name.replace(" ", ""), im, "ARGB8888"))

wall = Image.new("RGB", (320, 240))
px = wall.load()
for y in range(240):
    for x in range(320):
        u = x / 319
        v = y / 239
        base = [44 + 40 * (1 - v), 79 + 51 * (1 - v), 147 + 43 * (1 - v)]
        for cx, cy, col, spread in [
            (1, 0.05, (133, 112, 213), 0.24),
            (0.02, 0.95, (39, 177, 174), 0.3),
            (0.66, 0.62, (74, 137, 220), 0.16),
        ]:
            w = exp(-((u - cx) ** 2 + (v - cy) ** 2) / spread)
            base = [base[i] * (1 - w) + col[i] * w for i in range(3)]
        curve = 0.76 - 0.55 * u + 0.12 * sin(u * 5)
        band = exp(-(((v - curve) / 0.085) ** 2))
        lip = exp(-(((v - curve + 0.07) / 0.014) ** 2))
        base = [
            base[i] * (1 - 0.42 * band) + [107, 211, 233][i] * 0.42 * band + lip * 18
            for i in range(3)
        ]
        px[x, y] = tuple(min(255, max(0, round(c))) for c in base)
assets.insert(0, ("Wallpaper", wall, "RGB565"))
for name in ("Wifi", "Bluetooth", "Gps", "Sun"):
    assets.append(
        (name, glyph(name, 28).resize((28, 28), Image.Resampling.LANCZOS), "A8")
    )

out = ["// Generated by tools/generate_glass_assets.py; original offline artwork.\n"]
for name, im, fmt in assets:
    if fmt == "RGB565":
        data = bytearray()
        for r, g, b in im.getdata():
            i = len(data) // 2
            x = i % im.width
            y = i // im.width
            noise = (((x * 73 + y * 151) ^ (x * y * 19)) & 7) - 3
            r = max(0, min(255, r + noise))
            g = max(0, min(255, g + noise // 2))
            b = max(0, min(255, b + noise))
            c = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            data.extend((c & 255, c >> 8))
        stride = im.width * 2
    elif fmt == "A8":
        data = im.getchannel("A").tobytes()
        stride = im.width
    else:
        data = im.tobytes("raw", "BGRA")
        stride = im.width * 4
    out.append("alignas(4) static const uint8_t data%s[] = {\n" % name)
    out.extend(
        "    " + ",".join("0x%02x" % b for b in data[i : i + 24]) + ",\n"
        for i in range(0, len(data), 24)
    )
    out.append(
        "};\nstatic const lv_image_dsc_t image%s = {{LV_IMAGE_HEADER_MAGIC, LV_COLOR_FORMAT_%s, 0, %d, %d, %d, 0}, sizeof(data%s), data%s, nullptr, nullptr};\n"
        % (name, fmt, im.width, im.height, stride, name, name)
    )
(ROOT / "source/graphics/TFT/GlassAssets.inc").write_text("".join(out))
print(
    "Generated",
    sum(
        im.width * im.height * ({"RGB565": 2, "ARGB8888": 4, "A8": 1}[fmt])
        for _, im, fmt in assets
    ),
    "asset bytes",
)
