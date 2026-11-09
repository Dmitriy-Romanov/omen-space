# OMEN MAX 16-ak0xxx (board 8D88) fork

This is a personal fork of [yunusemreyl/omen-space](https://github.com/yunusemreyl/omen-space),
based on **v2.2.1 / commit 6a5adae**. It is an opt-in build for one specific
machine, not a replacement upstream release.

## Tested hardware

- HP OMEN MAX Gaming Laptop 16-ak0xxx
- Board: **8D88**
- Keyboard: **0d62:54bf** (HID LampArray, 120 lamps, 6 rows × 20)
- German keycaps, **non-tall Enter**
- 4-zone light bar under the keyboard (hp-omen-extra WMI)

Other boards have not been tested with this fork. Most new keyboard paths are
gated to the 0d62:54bf LampArray and the 8D88 board id, but the GUI changes are
global.

## What this fork adds

- HID LampArray transport: report 5 ranges / report 4 multi-update, acquire
  AutonomousMode=0 once, persistent hidraw, release on stop.
- Per-key mapping by HID InputBinding instead of 104→120 proportional scaling.
- 8D88-specific per-lamp overlay for Fn, Omen, Calculator, Settings, Power, Win,
  Copilot and the second LEDs of wide keys (Esc, Del, grave, Tab, Caps, keypad +,
  keypad Enter). The GUI gains a Settings key in slot 98 and labels Menu as
  Copilot; the top row is aligned over the numpad columns.
- EN/DE key-label switch (QWERTZ, ü/ö/ä/ß, etc.); physical mapping is unchanged.
- Software wave/breathing/cycle for the 4-zone light bar, independent of the
  keyboard mode; the bar has no hardware effect engine.
- Calibration API + tools/calibrate-lamps.py for mapping a board's lamps by
  pressing the lit keys.
- Secure Boot MOK signing helper for the DKMS hp-omen-extra module.

## Install (from this repo)

Build and install the daemon and GUI, then restart the service:

    cargo build --release -p omen-space-daemon -p omen-gui
    sudo install -m 755 target/release/omen-space-daemon /usr/libexec/omen-space/omen-space-daemon
    sudo install -m 755 target/release/omen-gui /usr/bin/omen-gui
    sudo systemctl restart omen-space-daemon

Back up the previous binaries first if you need a rollback. The daemon and GUI
versions must match.

For Secure Boot, driver/sign-modules.sh signs the installed hp-omen-extra
.ko.zst with the local omen-space MOK. The private key is **not** in this
repository.

## Known limitations

- The GUI canvas still uses the project's ANSI/US geometry. German labels are
  available through the EN/DE switch, but the extra <> key is not drawn and the
  Enter is kept wide (this machine does not have a tall Enter).
- The 8D88 special-key overlay is hard-coded for this board; do not expect it to
  be correct on another 8D88 revision without checking.
- Calibration JSON and personal colour/state files are not included.
- Light-bar effects are software-driven; they stop if the daemon stops.

## Upstream and licence

Based on yunusemreyl/omen-space, GPL-3.0. See [LICENSE](LICENSE) and the upstream
project for the original work. Please report generic issues upstream; 8D88-specific
issues can go to this fork.
