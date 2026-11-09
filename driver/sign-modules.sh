#!/usr/bin/env bash
# Sign the DKMS hp-omen-extra and hp-wmi modules with the omen-space MOK and
# register that MOK. Required with Secure Boot: the kernel rejects DKMS modules
# whose signing key is not enrolled. hp-omen-extra is the light bar/RGB driver;
# hp-wmi provides fan control (pwm1_enable / fan*_target) and thermal sysfs.
#
# Usage: sudo ./driver/sign-modules.sh
# Then reboot, choose "Enroll MOK" in the blue MOK manager screen and enter the
# password printed below (default: omen).
set -euo pipefail
trap 'echo "ERROR: signing failed at line $LINENO" >&2' ERR

if [[ ${EUID} -ne 0 ]]; then
    echo "Run as root: sudo $0" >&2
    exit 1
fi

MOK_DIR=${MOK_DIR:-/var/lib/omen-space/mok}
KVER=$(uname -r)
MOK_PASSWORD=${MOK_PASSWORD:-omen}

echo "omen-space: signing hp-omen-extra + hp-wmi for Secure Boot (kernel $KVER)"

find_sign_file() {
    local dirs=()
    for d in \
        "/usr/src/linux-headers-$KVER/scripts" \
        "/usr/src/kernels/$KVER/scripts" \
        "/lib/modules/$KVER/build/scripts" \
        "/usr/lib/modules/$KVER/build/scripts"; do
        [[ -d "$d" ]] && dirs+=("$d")
    done
    [[ ${#dirs[@]} -gt 0 ]] || return 0
    # Some of the candidate directories do not exist on every distro; only
    # pass the ones that do, and do not let find's SIGPIPE/exit status abort
    # the whole script under `set -e -o pipefail`.
    find "${dirs[@]}" -name sign-file -type f 2>/dev/null | head -n 1 || true
}

SIGN_FILE=$(find_sign_file)
if [[ -z "$SIGN_FILE" ]]; then
    echo "ERROR: scripts/sign-file not found in the kernel headers for $KVER." >&2
    echo "Install linux-headers-$KVER and try again." >&2
    exit 1
fi
if ! command -v zstd >/dev/null 2>&1; then
    echo "ERROR: zstd is required to sign compressed kernel modules." >&2
    exit 1
fi

mkdir -p "$MOK_DIR"
if [[ ! -s "$MOK_DIR/MOK.priv" || ! -s "$MOK_DIR/MOK.der" ]]; then
    echo "Generating MOK key in $MOK_DIR ..."
    openssl req -new -x509 -newkey rsa:2048 \
        -keyout "$MOK_DIR/MOK.priv" \
        -outform DER -out "$MOK_DIR/MOK.der" \
        -days 36500 -subj "/CN=omen-space-mok/" -nodes
    chmod 600 "$MOK_DIR/MOK.priv"
fi

# Let DKMS sign future builds with this key too, so a kernel update does not
# lose the signature.
mkdir -p /etc/dkms/framework.conf.d
cat > /etc/dkms/framework.conf.d/omen-space-mok.conf <<EOF
mok_signing_key=$MOK_DIR/MOK.priv
mok_certificate=$MOK_DIR/MOK.der
EOF

sign_module() {
    local path=$1
    [[ -f "$path" ]] || return 0
    local tmp
    tmp=$(mktemp /tmp/omen-sign.XXXXXX.ko)
    if [[ "$path" == *.zst ]]; then
        zstd -q -d -c "$path" > "$tmp"
    else
        cp "$path" "$tmp"
    fi

    # Drop an old signature (DKMS may have signed it with an unenrolled key).
    if command -v objcopy >/dev/null 2>&1; then
        objcopy --remove-section=.module_sig "$tmp" 2>/dev/null || true
    fi

    "$SIGN_FILE" sha256 "$MOK_DIR/MOK.priv" "$MOK_DIR/MOK.der" "$tmp"

    if [[ "$path" == *.zst ]]; then
        zstd -q -19 -f "$tmp" -o "$path"
        chmod 644 "$path"
    else
        cat "$tmp" > "$path"
    fi
    rm -f "$tmp"
    echo "[ok] signed $path"
}

MOD_PATH=$(modinfo -n hp-omen-extra 2>/dev/null || true)
if [[ -z "$MOD_PATH" ]]; then
    echo "ERROR: hp-omen-extra is not installed. Run: sudo ./driver/setup.sh install" >&2
    exit 1
fi
sign_module "$MOD_PATH"

# Fan control/thermal sysfs lives in hp-wmi. It is a separate DKMS module and
# may have been signed by an unenrolled DKMS key, which leaves the app without
# pwm1_enable/fan*_target and breaks Max/EC/manual modes.
HPWMI_PATH=$(modinfo -n hp-wmi 2>/dev/null || true)
if [[ -n "$HPWMI_PATH" ]]; then
    sign_module "$HPWMI_PATH"
else
    echo "[i] hp-wmi is not a loadable module (built-in or not installed); skipping"
fi
depmod -a "$KVER"

# hp-wmi provides fan control/thermal sysfs; hp-omen-extra provides RGB/lightbar.
# Both are separate DKMS modules and must survive a reboot.
printf '%s\n' hp_wmi hp_omen_extra > /etc/modules-load.d/omen-space.conf

echo
echo "Signed modules:"
echo "  hp-omen-extra: $MOD_PATH ($(modinfo -F signer hp-omen-extra 2>/dev/null || true))"
if [[ -n "$HPWMI_PATH" ]]; then
    echo "  hp-wmi:        $HPWMI_PATH ($(modinfo -F signer hp-wmi 2>/dev/null || true))"
fi
echo

if mokutil --test-key "$MOK_DIR/MOK.der" 2>/dev/null | grep -qi "not enrolled"; then
    printf '%s\n%s\n' "$MOK_PASSWORD" "$MOK_PASSWORD" | mokutil --import "$MOK_DIR/MOK.der"
    echo
    echo "MOK imported. Reboot now and complete the blue MOK manager screen:"
    echo "  1. Enroll MOK"
    echo "  2. Continue"
    echo "  3. Yes"
    echo "  4. Password: $MOK_PASSWORD"
    echo "  5. Reboot"
else
    echo "MOK is already enrolled; loading hp-wmi and hp_omen_extra now."
    modprobe hp_wmi || true
    modprobe hp_omen_extra || true
    if [[ -d /sys/devices/platform/hp-wmi ]]; then
        echo "[ok] Fan/thermal driver is loaded: /sys/devices/platform/hp-wmi"
    else
        echo "WARNING: hp-wmi did not create /sys/devices/platform/hp-wmi; check dmesg."
    fi
    if [[ -d /sys/devices/platform/hp-omen-extra ]]; then
        echo "[ok] Light bar driver is loaded: /sys/devices/platform/hp-omen-extra"
    else
        echo "WARNING: hp-omen-extra did not create /sys/devices/platform/hp-omen-extra; check dmesg."
    fi
fi
