#!/usr/bin/env python3
"""Draw sprites and animations on a per-key RGB keyboard.

The board exposes 120 lamps in 6 rows of 20 (see GetLampMap), so it works as a
tiny 20x6 pixel display. Sprites are written as text art and drawn by lighting
lamps, which makes the result independent of keycap shapes and of the keyboard
layout: a lamp is addressed by (row, column), not by key name.

Only needs the omen-space daemon and busctl; no extra libraries.

Examples:
    ./keyboard-sprite.py walk --fps 5
    ./keyboard-sprite.py text "HI" --fps 8
    ./keyboard-sprite.py show art.txt
"""
import argparse
import json
import subprocess
import sys
import time

BUS = "org.hp.omen"
PATH = "/org/hp/omen/Rgb"
IFACE = "org.hp.omen.Rgb"

COLS = 20
ROWS = 6


def call(method, *args):
    """Call a daemon method and return its reply with the 's "..."' framing removed."""
    cmd = ["busctl", "--system", "call", BUS, PATH, IFACE, method, *args]
    done = subprocess.run(cmd, capture_output=True, text=True)
    out = (done.stdout or done.stderr).strip()
    if not out.startswith("s "):
        return out
    # busctl prints the string with the inner quotes escaped: s "{\"a\":1}"
    payload = out[2:].strip()
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        decoded = payload.strip('"').encode().decode("unicode_escape")
    # The payload is itself JSON for the map methods.
    try:
        return json.loads(decoded)
    except (json.JSONDecodeError, TypeError):
        return decoded


def lamp_grid():
    """Return (rows, cols, index_of) for this board, read from the daemon."""
    raw = call("GetLampMap")
    if not isinstance(raw, dict):
        sys.exit(f"unexpected GetLampMap reply: {raw!r}")
    lamps = raw["lamps"]
    ys = sorted({lamp["y"] for lamp in lamps})
    counts = {len([lamp for lamp in lamps if lamp["y"] == y]) for y in ys}
    cols = counts.pop() if len(counts) == 1 else max(counts)
    # Indices are laid out row-major, so (row, col) -> index is a simple offset.
    index_of = {(i // cols, i % cols): lamp["index"] for i, lamp in enumerate(lamps)}
    return len(ys), cols, index_of


def draw(base, index_of, rows, cols, sprite, top, left, colour):
    """Paint sprite cells into base. Out-of-screen cells are simply skipped."""
    for dy, line in enumerate(sprite):
        for dx, cell in enumerate(line):
            if cell == " " or cell == ".":
                continue
            y, x = top + dy, left + dx
            if 0 <= y < rows and 0 <= x < cols:
                idx = index_of[(y, x)]
                if idx < len(base):
                    base[idx] = colour
    return base


def send(frame):
    """Push one full frame. The daemon wants exactly one colour per lamp."""
    reply = call("SetLampColors", "s", json.dumps(frame))
    return reply == "OK"


# A 5x5 walker: two frames so it looks like it is striding.
WALK = [
    [
        " .#. ",
        " ### ",
        " .#. ",
        " #.# ",
        " # # ",
    ],
    [
        " .#. ",
        " ### ",
        " .#. ",
        " #.# ",
        "  # #",
    ],
]

# 5x5 block font, enough for short messages.
FONT = {
    " ": ["     "] * 5,
    "A": [" .#. ", "#  # ", "#### ", "#  # ", "#  # "],
    "B": ["###  ", "#  # ", "###  ", "#  # ", "###  "],
    "C": [" ####", "#    ", "#    ", "#    ", " ####"],
    "D": ["###  ", "#  # ", "#  # ", "#  # ", "###  "],
    "E": ["#####", "#    ", "#### ", "#    ", "#####"],
    "H": ["#  # ", "#  # ", "#####", "#  # ", "#  # "],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "#####"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#####"],
    "O": [" .#. ", "#  # ", "#  # ", "#  # ", " .#. "],
    "S": [" ####", "#    ", " .#. ", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  "],
    "W": ["#   #", "#   #", "# # #", "# # #", " # # "],
}


def text_sprite(message):
    sprite = [[] for _ in range(5)]
    for ch in message.upper():
        glyph = FONT.get(ch, FONT[" "])
        for row in range(5):
            sprite[row].extend(glyph[row])
        for row in range(5):
            sprite[row].append(" ")
    return ["".join(r) for r in sprite]


def off_frame(n):
    return ["000000"] * n


def cmd_walk(rows, cols, index_of, total, fps):
    print("walking… Ctrl-C to stop")
    step = 0
    while True:
        frame = off_frame(total)
        phase = (step // 2) % 2
        left = step % (cols + 5) - 5
        draw(frame, index_of, rows, cols, WALK[phase], top=1, left=left, colour="FF3355")
        send(frame)
        step += 1
        time.sleep(1.0 / fps)


def cmd_text(message, rows, cols, index_of, total, fps):
    full = text_sprite(message)
    width = len(full[0])
    print(f"scrolling {width} px… Ctrl-C to stop")
    pos = cols
    while True:
        frame = off_frame(total)
        draw(frame, index_of, rows, cols, full, top=0, left=pos, colour="33FF66")
        send(frame)
        pos -= 1
        if pos < -width:
            pos = cols
        time.sleep(1.0 / fps)


def cmd_show(path, rows, cols, index_of, total):
    lines = [line.rstrip("\n") for line in open(path, encoding="utf-8")]
    frame = off_frame(total)
    draw(frame, index_of, rows, cols, lines, top=0, left=0, colour="FFCC00")
    print("OK" if send(frame) else "FAILED")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_walk = sub.add_parser("walk", help="walk a small figure across the keyboard")
    p_walk.add_argument("--fps", type=float, default=5.0)

    p_text = sub.add_parser("text", help="scroll a short message")
    p_text.add_argument("message")
    p_text.add_argument("--fps", type=float, default=8.0)

    p_show = sub.add_parser("show", help="draw a text file of up to 6 lines")
    p_show.add_argument("path")

    args = parser.parse_args()
    rows, cols, index_of = lamp_grid()
    total = rows * cols
    print(f"board: {rows} rows x {cols} cols ({max(index_of.values()) + 1} lamps)")

    try:
        if args.cmd == "walk":
            cmd_walk(rows, cols, index_of, total, args.fps)
        elif args.cmd == "text":
            cmd_text(args.message, rows, cols, index_of, total, args.fps)
        elif args.cmd == "show":
            cmd_show(args.path, rows, cols, index_of, total)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        # Hand the keyboard back to the daemon so the saved preset returns.
        call("StopLampCalibration")
        print("restored")


if __name__ == "__main__":
    main()
