#!/usr/bin/env bash
# Sign the DKMS hp-omen-extra module with the omen-space MOK and register that
# MOK. Required for the 4-zone light bar on systems with Secure Boot enabled:
# the kernel rejects the DKMS module when its signing key is not enrolled.
#
# Usage: sudo ./driver/sign-modules.sh
# Then reboot, choose "Enroll MOK" in the blue MOK manager screen and enter the
# password printed below (default: omen).
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run as root: sudo $0" >&2
    exit 1
fi

MOK_DIR=${MOK_DIR:-/var/lib/omen-space/mok}
KVER=$(uname -r)
MOK_PASSWORD=${MOK_PASSWORD:-omen}

find_sign_file() {
    find \
        "/usr/src/linux-headers-$KVER/scripts" \
        "/usr/src/kernels/$KVER/scripts" \
        "/lib/modules/$KVER/build/scripts" \
        "/usr/lib/modules/$KVER/build/scripts" \
        -name sign-file -type f 2>/dev/null | head -n 1
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
depmod -a "$KVER"

# The light bar driver is independent of the custom hp-wmi; load it on boot.
echo "hp_omen_extra" > /etc/modules-load.d/omen-space-lightbar.conf

echo
echo "Signed module: $MOD_PATH"
echo "Signer: $(modinfo -F signer hp-omen-extra 2>/dev/null || true)"
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
    echo "MOK is already enrolled; loading hp_omen_extra now."
    modprobe hp_omen_extra || true
    if [[ -d /sys/devices/platform/hp-omen-extra ]]; then
        echo "[ok] Light bar driver is loaded: /sys/devices/platform/hp-omen-extra"
    else
        echo "WARNING: module did not create /sys/devices/platform/hp-omen-extra; check dmesg."
    fi
fi
