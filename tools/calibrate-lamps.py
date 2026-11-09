#!/usr/bin/env python3
"""Interactive physical-lamp calibration for the OMEN MAX LampArray.

Run outside the agent session, as root (needed to read /dev/input/event*):

    sudo python3 /home/dima/omen-space/tools/calibrate-lamps.py

For every physical lamp it lights that lamp white and waits for you to press
the key that lit up. It records the Linux keycode/name next to the lamp id,
saves after every press, and at the end groups lamps by key (so keys with two
LEDs are visible). Ctrl+C stops and restores the configured lighting.

Options:
  --start N      first lamp index (default 0)
  --end N        one past the last lamp index (default all)
  --timeout S    seconds to wait for a press before marking skipped (default 30)
  --out PATH     output JSON (default: /home/dima/omen-space-rgb-notes/lamp-calibration.json)
  --resume       merge with an existing --out file and skip already recorded lamps
"""
import argparse
import json
import os
import re
import select
import struct
import subprocess
import sys
import termios
import time

DBUS = ["busctl", "call", "org.hp.omen", "/org/hp/omen/Rgb", "org.hp.omen.Rgb"]
EVENT = struct.Struct("@llHHi")  # struct input_event on x86_64: 24 bytes


def die(msg):
    print("ERROR:", msg, file=sys.stderr)
    sys.exit(1)


def dbus(method, *args):
    cmd = DBUS + [method] + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("busctl %s failed: %s" % (method, p.stderr.strip() or p.stdout.strip()))
    return p.stdout.strip()


def parse_dbus_string(out):
    # busctl prints: s "escaped json"
    if not out.startswith("s "):
        raise RuntimeError("unexpected busctl output: %r" % out)
    return json.loads(out[2:])


def get_lamp_map():
    return json.loads(parse_dbus_string(dbus("GetLampMap")))


def set_lamp_colors(colors):
    payload = json.dumps(colors)
    dbus("SetLampColors", "s", payload)


def keycode_names():
    names = {}
    path = "/usr/include/linux/input-event-codes.h"
    try:
        with open(path) as f:
            for line in f:
                m = re.match(r"#define\s+(KEY_[A-Z0-9_]+)\s+(\d+)\s*$", line)
                if m:
                    names[int(m.group(2))] = m.group(1)
    except OSError:
        pass
    return names


def find_keyboard_device():
    blocks = open("/proc/bus/input/devices").read().split("\n\n")
    candidates = []
    for block in blocks:
        name = re.search(r'^N: Name="(.*)"$', block, re.M)
        handlers = re.search(r"^H: Handlers=(.*)$", block, re.M)
        if not name or not handlers:
            continue
        if name.group(1) != "HP HP Gaming Keyboard II":
            continue
        if "kbd" not in handlers.group(1):
            continue
        for ev in handlers.group(1).split():
            if ev.startswith("event"):
                candidates.append("/dev/input/" + ev)
    if not candidates:
        die("internal keyboard event device not found (HP HP Gaming Keyboard II)")
    return candidates[0]


def flush_events(fd):
    while True:
        r, _, _ = select.select([fd], [], [], 0)
        if not r:
            return
        try:
            if not os.read(fd, 4096):
                return
        except BlockingIOError:
            return


def wait_key(fd, timeout, refresh=None, refresh_s=2.0):
    """Return the next key press, or None on timeout.

    refresh() is called periodically while waiting. The keyboard firmware turns
    its backlight off after the BIOS idle timeout even while a host frame is
    shown; re-sending the calibration frame keeps the lamp visible.
    """
    deadline = time.monotonic() + timeout
    buf = b""
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            return None
        wait = left if not refresh or refresh_s <= 0 else min(left, refresh_s)
        r, _, _ = select.select([fd], [], [], wait)
        if not r:
            if refresh:
                try:
                    refresh()
                    print(".", end="", flush=True)
                except Exception as e:
                    print("\n  refresh failed: %s" % e, file=sys.stderr)
            continue
        try:
            data = os.read(fd, 24 * 64)
        except BlockingIOError:
            continue
        if not data:
            return None
        buf += data
        while len(buf) >= EVENT.size:
            sec, usec, etype, code, value = EVENT.unpack_from(buf)
            buf = buf[EVENT.size:]
            if etype == 1 and value == 1:  # EV_KEY press
                return code


def read_name(code):
    return KEY_NAMES.get(code, "KEY_%d" % code)


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)
    try:
        if os.environ.get("SUDO_UID"):
            os.chown(path, int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))
    except OSError:
        pass


def save_markdown(path, data):
    groups = {}
    for rec in data["records"]:
        if rec.get("skipped"):
            continue
        groups.setdefault(rec["key_name"], []).append(rec)
    lines = [
        "# LampArray physical calibration — %s (%s)" % (data["product"], data["board"]),
        "",
        "- lamps: %d" % data["lamp_count"],
        "- recorded: %d" % len([r for r in data["records"] if not r.get("skipped")]),
        "- skipped: %d" % len([r for r in data["records"] if r.get("skipped")]),
        "",
        "| key | keycode | lamps (id) | lamp indices |",
        "| --- | --- | --- | --- |",
    ]
    for key, recs in sorted(groups.items()):
        lines.append("| %s | %s | %s | %s |" % (
            key, recs[0]["keycode"],
            ", ".join(str(r["id"]) for r in recs),
            ", ".join(str(r["index"]) for r in recs),
        ))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    try:
        if os.environ.get("SUDO_UID"):
            os.chown(path, int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))
    except OSError:
        pass


def main():
    global KEY_NAMES
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=None,
                    help="first lamp index; with --resume, explicit --start overrides auto-advance")
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--single", action="store_true",
                    help="record the first non-Shift press (for multi-scancode keys)")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--refresh", type=float, default=2.0,
                    help="re-send the lamp frame every N seconds (0 = off)")

    ap.add_argument("--out", default="/home/dima/omen-space-rgb-notes/lamp-calibration.json")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    if os.geteuid() != 0:
        die("run as root: sudo python3 " + sys.argv[0])

    KEY_NAMES = keycode_names()
    dev = find_keyboard_device()
    print("keyboard event device:", dev)

    try:
        info = get_lamp_map()
    except Exception as e:
        die("cannot get lamp map from daemon: %s" % e)
    lamps = info.get("lamps", [])
    if not lamps:
        die("daemon returned no lamps; is the LampArray available?")
    count = len(lamps)

    data = {
        "board": open("/sys/class/dmi/id/board_name").read().strip(),
        "product": open("/sys/class/dmi/id/product_name").read().strip(),
        "timestamp": int(time.time()),
        "lamp_count": count,
        "lamp_map": lamps,
        "records": [],
    }
    if args.resume and os.path.exists(args.out):
        try:
            old = json.load(open(args.out))
            if old.get("lamp_count") == count:
                data["records"] = old.get("records", [])
        except Exception:
            pass
    recorded = {r["index"] for r in data["records"] if not r.get("skipped")}
    start = args.start if args.start is not None else 0
    if args.resume and args.start is None and recorded:
        start = max(recorded) + 1
    end = args.end if args.end is not None else count
    end = min(end, count)

    fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
    old_attrs = None
    try:
        old_attrs = termios.tcgetattr(sys.stdin.fileno())
        new = termios.tcgetattr(sys.stdin.fileno())
        new[3] &= ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, new)
    except Exception:
        old_attrs = None

    print("Starting lamp calibration: %d..%d of %d" % (start, end - 1, count))
    print("For each lamp: press the lit key twice in a row; Shift is ignored.")
    print("If nothing lights up, press SHIFT 5 times to mark this lamp as nothing.")
    print("No key for %.0fs = skip. Ctrl+C = stop." % args.timeout)
    dbus("StartLampCalibration")
    time.sleep(1.0)
    flush_events(fd)

    try:
        for index in range(start, end):
            lamp = lamps[index]
            colors = ["000000"] * count
            colors[index] = "FFFFFF"
            print("Lamp %d/%d  index=%d id=%d binding=0x%02X  x=%dmm y=%dmm"
                  % (index + 1, count, index, lamp["id"], lamp["binding"],
                     lamp["x"] // 1000, lamp["y"] // 1000))
            allow_shift = lamp["binding"] in (0xE1, 0xE5)
            print("  press the lit key TWICE; SHIFT is ignored; 5x SHIFT = nothing%s"
                  % ("" if not allow_shift else " (Shift allowed for this lamp)"))
            sys.stdout.flush()
            set_lamp_colors(colors)
            flush_events(fd)

            # The first non-Shift press may be the wake-up, the second the
            # answer. Two identical presses in a row confirm the key.
            rec = None
            last = None
            shift_count = 0
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                code = wait_key(
                    fd, max(0.1, deadline - time.monotonic()),
                    refresh=lambda: set_lamp_colors(colors),
                    refresh_s=args.refresh,
                )
                if code is None:
                    rec = {"index": index, "id": lamp["id"], "x": lamp["x"], "y": lamp["y"],
                           "binding": lamp["binding"], "skipped": True}
                    print("  skipped (timeout)")
                    break
                if code in (42, 54):  # KEY_LEFTSHIFT / KEY_RIGHTSHIFT
                    shift_count += 1
                    if shift_count >= 5:
                        rec = {"index": index, "id": lamp["id"], "x": lamp["x"], "y": lamp["y"],
                               "binding": lamp["binding"], "skipped": True, "nothing": True}
                        print("  5x SHIFT -> nothing; next lamp")
                        break
                    if allow_shift:
                        if code == last:
                            rec = {"index": index, "id": lamp["id"], "x": lamp["x"], "y": lamp["y"],
                                   "binding": lamp["binding"], "keycode": code,
                                   "key_name": read_name(code)}
                            print("  recorded %s (code %d)" % (rec["key_name"], code))
                            break
                        last = code
                        deadline = time.monotonic() + args.timeout
                        print("  got SHIFT (%d/5 -> nothing); press SHIFT again" % shift_count)
                    else:
                        print("  SHIFT ignored (%d/5 -> nothing)" % shift_count)
                        last = None
                    continue
                shift_count = 0
                if args.single:
                    rec = {"index": index, "id": lamp["id"], "x": lamp["x"], "y": lamp["y"],
                           "binding": lamp["binding"], "keycode": code, "key_name": read_name(code)}
                    print("  recorded %s (code %d, single)" % (rec["key_name"], code))
                    break
                if code == last:
                    rec = {"index": index, "id": lamp["id"], "x": lamp["x"], "y": lamp["y"],
                           "binding": lamp["binding"], "keycode": code, "key_name": read_name(code)}
                    print("  recorded %s (code %d)" % (rec["key_name"], code))
                    break
                last = code
                deadline = time.monotonic() + args.timeout
                print("  got %s; press the same key again to confirm" % read_name(code))
            data["records"] = [r for r in data["records"] if r["index"] != index] + [rec]
            save_json(args.out, data)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        try:
            dbus("StopLampCalibration")
        except Exception:
            pass
        os.close(fd)
        if old_attrs is not None:
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, old_attrs)
            except Exception:
                pass

    md = args.out.rsplit(".", 1)[0] + ".md"
    save_markdown(md, data)
    print("\nSaved:", args.out)
    print("Report:", md)
    print("Keys with more than one lamp:")
    groups = {}
    for rec in data["records"]:
        if not rec.get("skipped"):
            groups.setdefault(rec["key_name"], []).append(rec["id"])
    for key, ids in sorted(groups.items()):
        if len(ids) > 1:
            print("  %s: %s" % (key, ids))
    print("Done.")


if __name__ == "__main__":
    main()
