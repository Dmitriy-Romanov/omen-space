# Fresh install — 8D88 fork

This is the minimal, AI-followable install path for this fork. Use it after a
clean Linux install. It installs **this fork**, not upstream.

## One command (recommended)

    curl -sSL https://raw.githubusercontent.com/Dmitriy-Romanov/omen-space/main/install-8d88.sh | bash

The script clones the fork to a temporary directory, runs the project installer
with sudo, and prints the Secure Boot note. It expects a normal user account
with sudo; do not run the pipe as root.

## Manual install

    git clone https://github.com/Dmitriy-Romanov/omen-space.git
    cd omen-space
    sudo ./setup.sh install --non-interactive
    sudo systemctl status omen-space-daemon

The project installer detects apt/dnf/pacman, installs the GTK4/libadwaita and
DKMS dependencies, builds the workspace, installs the daemon/GUI/CLI/tray and
registers hp-wmi + hp-omen-extra.

## Secure Boot

If the hp-omen-extra module is not loaded after install because Secure Boot is
enabled, sign and enrol it with the local MOK:

    sudo ./driver/sign-modules.sh

Then reboot and complete the MOK enrolment screen if prompted. The private key
stays in /var/lib/omen-space/mok and is not part of the repository.

Check:

    mokutil --sb-state
    lsmod | grep hp_omen_extra
    systemctl is-active omen-space-daemon

## Verify

    busctl call org.hp.omen /org/hp/omen/Rgb org.hp.omen.Rgb GetState
    omen-gui

Set the keyboard to Per-Key and test A/S/D/Space/numpad 0. On 8D88 the special
keys Fn/Omen/Calc/Settings/Power/Copilot should light individually.

## Update this fork

    cd omen-space
    git pull fork main
    sudo ./setup.sh install --non-interactive

## Uninstall

    sudo ./setup.sh uninstall

## Notes

- The upstream one-line installer (yunusemreyl/omen-space) installs upstream,
  not this fork. Use the commands above.
- Other boards are not tested; see FORK-8D88.md.
- If the build fails, install the dependencies first with the distro commands
  that setup.sh prints, then rerun sudo ./setup.sh install.
