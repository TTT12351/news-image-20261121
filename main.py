#!/usr/bin/env python3
"""Draw a one-page newspaper front page summing up the world news of
Saturday 21 November 2026, and write it to /output/entry.png.

Pure Python 3 standard library: the picture is painted into an RGB
framebuffer with a hand-made 5x7 bitmap font and saved with a small
deterministic PNG encoder (zlib + struct). No network, no files read,
same bytes on every run.

News selection (reported 21 Nov 2026, cross-checked across One Turn's
day page, the Japan Times and other outlets): Russia's mass strike on
Ukraine with missiles and a drone landing in Poland, the AI-led stock
sell-off pushing the S&P 500 into correction, tankers hit near Hormuz
as US-Iran talks stall, a pancreatic-cancer pill trial breakthrough,
BepiColombo reaching Mercury orbit, the FBI and USDA hack reports,
the UK-EU post-Brexit agreements, and COP31 running into overtime.
"""

import os
import struct
import zlib

W = 1024
H = 1024

PAPER = (247, 243, 232)
INK = (17, 17, 17)
WHITE = (255, 255, 255)
RED = (185, 28, 28)
BLUE = (29, 78, 216)
GREEN = (21, 128, 61)
AMBER = (180, 83, 9)
PURPLE = (126, 34, 206)
TEAL = (15, 118, 110)
GREY = (90, 90, 90)
LIGHT = (232, 224, 205)

# 5x7 bitmap font: each glyph is 7 rows, each row a 5-bit mask,
# bit 4 is the leftmost pixel.
FONT = {
    "A": (14, 17, 17, 31, 17, 17, 17),
    "B": (30, 17, 17, 30, 17, 17, 30),
    "C": (14, 17, 16, 16, 16, 17, 14),
    "D": (28, 18, 17, 17, 17, 18, 28),
    "E": (31, 16, 16, 30, 16, 16, 31),
    "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 15),
    "H": (17, 17, 17, 31, 17, 17, 17),
    "I": (14, 4, 4, 4, 4, 4, 14),
    "J": (7, 2, 2, 2, 2, 18, 12),
    "K": (17, 18, 20, 24, 20, 18, 17),
    "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 21, 17, 17, 17),
    "N": (17, 17, 25, 21, 19, 17, 17),
    "O": (14, 17, 17, 17, 17, 17, 14),
    "P": (30, 17, 17, 30, 16, 16, 16),
    "Q": (14, 17, 17, 17, 21, 18, 13),
    "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30),
    "T": (31, 4, 4, 4, 4, 4, 4),
    "U": (17, 17, 17, 17, 17, 17, 14),
    "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 21, 21, 21, 10),
    "X": (17, 10, 4, 4, 4, 10, 17),
    "Y": (17, 10, 4, 4, 4, 4, 4),
    "Z": (31, 1, 2, 4, 8, 16, 31),
    "0": (14, 17, 19, 21, 25, 17, 14),
    "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 2, 4, 8, 31),
    "3": (31, 2, 4, 2, 1, 17, 14),
    "4": (2, 6, 10, 18, 31, 2, 2),
    "5": (31, 16, 30, 1, 1, 17, 14),
    "6": (6, 8, 16, 30, 17, 17, 14),
    "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14),
    "9": (14, 17, 17, 15, 1, 2, 12),
    " ": (0, 0, 0, 0, 0, 0, 0),
    ".": (0, 0, 0, 0, 0, 12, 12),
    ",": (0, 0, 0, 0, 12, 4, 8),
    "'": (4, 4, 8, 0, 0, 0, 0),
    "-": (0, 0, 0, 31, 0, 0, 0),
    ":": (0, 12, 12, 0, 12, 12, 0),
    ";": (0, 12, 12, 0, 12, 4, 8),
    "/": (1, 1, 2, 4, 8, 16, 16),
    "%": (25, 26, 2, 4, 8, 11, 19),
    "$": (4, 15, 20, 14, 5, 30, 4),
    "+": (0, 4, 4, 31, 4, 4, 0),
    "!": (4, 4, 4, 4, 4, 0, 4),
    "?": (14, 17, 1, 2, 4, 0, 4),
    "(": (2, 4, 8, 8, 8, 4, 2),
    ")": (8, 4, 2, 2, 2, 4, 8),
    "&": (12, 18, 20, 8, 21, 18, 13),
    '"': (10, 10, 10, 0, 0, 0, 0),
    "*": (0, 21, 14, 31, 14, 21, 0),
}


def norm(text):
    out = []
    for ch in text.upper():
        if ch in FONT:
            out.append(ch)
        elif ch in "\u2019\u2018":
            out.append("'")
        elif ch in "\u2013\u2014":
            out.append("-")
        elif ch == "\u2022":
            out.append("*")
        else:
            out.append(" ")
    return "".join(out)


def text_width(text, scale, bold=False):
    text = norm(text or "")
    if not text:
        return 0
    adv = 6 * scale + (scale if bold else 0)
    return len(text) * adv - scale


class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bytes(bg) * (w * h))

    def rect(self, x, y, rw, rh, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + rw)
        y1 = min(self.h, y + rh)
        if x0 >= x1 or y0 >= y1:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            off = (yy * self.w + x0) * 3
            self.px[off:off + len(row)] = row

    def draw_text(self, x, y, text, scale, color, bold=False):
        text = norm(text)
        adv = 6 * scale + (scale if bold else 0)
        cx = x
        for ch in text:
            glyph = FONT.get(ch, FONT[" "])
            for r in range(7):
                bits = glyph[r]
                for c in range(5):
                    if bits & (16 >> c):
                        self.rect(cx + c * scale, y + r * scale,
                                  scale + (scale if bold else 0), scale, color)
            cx += adv
        return cx - x

    def draw_centered(self, cx, y, text, scale, color, bold=False):
        w = text_width(text, scale, bold)
        return self.draw_text(cx - w // 2, y, text, scale, color, bold)


def wrap(text, scale, max_width, bold=False):
    words = norm(text).split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if cur and text_width(trial, scale, bold) > max_width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def para(cv, x, y, text, scale, color, max_width, bold=False, leading=12):
    lines = wrap(text, scale, max_width, bold)
    step = 7 * scale + leading
    for line in lines:
        cv.draw_text(x, y, line, scale, color, bold)
        y += step
    return y


def story_box(cv, x, y, w, tag, tag_color, headline, body):
    cv.rect(x, y, w, 4, tag_color)
    tw = text_width(tag, 2, True)
    cv.rect(x, y + 10, tw + 16, 22, tag_color)
    cv.draw_text(x + 8, y + 14, tag, 2, WHITE, True)
    y += 42
    y = para(cv, x, y, headline, 3, INK, w, True, 6)
    y += 3
    y = para(cv, x, y, body, 2, GREY, w, False, 5)
    return y


def build():
    cv = Canvas(W, H, PAPER)
    m = 36
    right = W - m

    # Masthead
    cv.rect(0, 0, W, 52, INK)
    cv.draw_text(m, 14, "THE WORLD IN ONE DAY", 3, WHITE, True)
    rtxt = "ONE IMAGE - ALL THE NEWS"
    cv.draw_text(right - text_width(rtxt, 2), 18, rtxt, 2, LIGHT)
    cv.draw_centered(W // 2, 62, "GLOBAL DAILY", 5, INK, True)
    cv.draw_centered(W // 2, 108, "SATURDAY - NOVEMBER 21 - 2026", 4, RED, True)
    cv.rect(m, 144, right - m, 3, INK)
    cv.rect(m, 151, right - m, 1, INK)

    # Lead story: Russia strikes Ukraine, projectiles land in Poland
    y = 164
    cv.rect(m, y, 150, 26, RED)
    cv.draw_text(m + 8, y + 6, "TOP STORY", 2, WHITE, True)
    cv.draw_text(m + 170, y + 6, "KYIV - WAR IN EUROPE", 2, RED, True)
    y += 40
    y = para(cv, m, y,
             "RUSSIA FIRES 400 DRONES AND 110 MISSILES AT UKRAINE - "
             "MISSILES LAND IN POLAND",
             4, INK, right - m, True, 8)
    y += 2
    y = para(cv, m, y,
             "AT LEAST 8 DIED IN KYIV AS BRIDGES, RAIL STATIONS AND "
             "ENERGY SITES WERE HIT AND POWER FAILED IN TEN REGIONS. "
             "TWO MISSILES AND A SUSPECTED DRONE CAME DOWN IN EASTERN "
             "POLAND; NATO CALLED IT A GRAVE AIRSPACE VIOLATION AND "
             "PM TUSK CALLED IT A DELIBERATE PROVOCATION.",
             2, GREY, right - m, False, 5)
    cv.rect(m, y + 2, right - m, 2, INK)
    y += 14

    # Second story: AI sell-off, full width band
    cv.rect(m, y, right - m, 92, (235, 240, 250))
    cv.rect(m, y, 6, 92, BLUE)
    yy = para(cv, m + 20, y + 10,
              "AI SELL-OFF PUSHES S&P 500 INTO CORRECTION",
              3, BLUE, right - m - 40, True, 6)
    para(cv, m + 20, yy + 1,
         "AI AND CHIP SHARES TUMBLED WORLDWIDE: THE S&P 500 FELL "
         "3.7%, JAPAN'S NIKKEI LOST 5.1%, GOLD DROPPED 4.6% AND "
         "BITCOIN SLID TO ABOUT $57,850.",
         2, INK, right - m - 40, False, 5)
    y += 94

    # Two-column story grid
    col_w = (right - m - 24) // 2
    lx = m
    rx = m + col_w + 24
    gy = y
    y1 = story_box(cv, lx, gy, col_w, "MIDDLE EAST", AMBER,
                   "TANKERS HIT NEAR HORMUZ, TALKS STALL",
                   "TANKERS WERE HIT BY PROJECTILES NEAR THE STRAIT "
                   "OF HORMUZ AS US-IRAN TALKS STALLED; IRAN'S FOREIGN "
                   "MINISTER SOUGHT DIPLOMACY, TRUMP CALLED IRAN'S "
                   "TERMS UNACCEPTABLE.")
    y2 = story_box(cv, rx, gy, col_w, "HEALTH", GREEN,
                   "CANCER PILL MAKES TUMORS VANISH",
                   "A DAILY PILL, DARAXONRASIB, MADE PANCREATIC "
                   "CANCER UNDETECTABLE ON SCANS IN ONE IN 12 "
                   "PATIENTS IN A TRIAL - A RARE BREAKTHROUGH FOR "
                   "A HARD-TO-TREAT CANCER.")
    gy = max(y1, y2) + 8
    y1 = story_box(cv, lx, gy, col_w, "CYBER", PURPLE,
                   "FBI AND USDA DATABASES HACKED",
                   "HACKERS REPORTEDLY ENTERED THE FBI'S NATIONAL "
                   "CRIME DATABASE AND A USDA PAYMENT SYSTEM; TRUMP "
                   "OUSTED THE US CYBER DIRECTOR AMID OUTAGE "
                   "CRITICISM.")
    y2 = story_box(cv, rx, gy, col_w, "EUROPE", BLUE,
                   "UK AND EU SIGN BREXIT DEALS",
                   "PM BURNHAM AND EU LEADERS SIGNED THREE POST-"
                   "BREXIT AGREEMENTS IN BRUSSELS ON FOOD EXPORTS, "
                   "CARBON MARKETS AND YOUTH MOBILITY.")
    gy = max(y1, y2) + 6

    # Numbers strip
    cv.rect(m, gy, right - m, 2, INK)
    gy += 8
    stats = [("400+", "DRONES FIRED"),
             ("110", "MISSILES AT UKRAINE"),
             ("-3.7%", "S&P 500 FALL"),
             ("8 DEAD", "IN KYIV")]
    sw = (right - m) // 4
    for i, (big, small) in enumerate(stats):
        sx = m + i * sw
        cv.draw_centered(sx + sw // 2, gy, big, 3, RED, True)
        cv.draw_centered(sx + sw // 2, gy + 26, small, 1, GREY, True)
    gy += 34

    # Briefing lines: COP31 and Mercury
    cv.rect(m, gy, right - m, 1, INK)
    gy += 6
    cv.draw_centered(W // 2, gy,
                     "COP31: TALKS IN ANTALYA RUN PAST DEADLINE "
                     "OVER FOSSIL FUELS", 2, GREEN, True)
    gy += 20
    cv.draw_centered(W // 2, gy,
                     "SPACE: BEPICOLOMBO REACHES MERCURY ORBIT "
                     "AFTER EIGHT YEARS", 2, TEAL, True)

    # Footer ticker
    cv.rect(0, H - 58, W, 58, INK)
    ticker = ("ALSO TODAY: STUDENT PROTESTS IN 25 EUROPEAN COUNTRIES * "
              "PERU MAGNITUDE 6.7 QUAKE * US LOSES MEASLES STATUS")
    lines = wrap(ticker, 2, right - m)
    ty = H - 46
    for line in lines[:2]:
        cv.draw_centered(W // 2, ty, line, 2, WHITE)
        ty += 24
    return cv


def png_bytes(cv):
    raw = bytearray()
    stride = cv.w * 3
    for yy in range(cv.h):
        raw.append(0)
        raw += cv.px[yy * stride:(yy + 1) * stride]

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = png_bytes(build())
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as fh:
        fh.write(data)
    try:
        os.chmod(path, 0o644)
    except OSError:
        pass
    print("wrote", path, len(data), "bytes")


if __name__ == "__main__":
    main()
