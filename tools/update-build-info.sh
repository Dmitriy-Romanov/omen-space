#!/usr/bin/env bash
# Refresh /etc/omen-space/build_info.json after a manual daemon/GUI install.
# This is MANDATORY for this fork: the update center compares the recorded
# upstream SHA with GitHub and otherwise reports a stale build.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run as root: sudo $0 [repo-path]" >&2
    exit 1
fi

ROOT="/home/dima/omen-space"
if [[ $# -ge 1 ]]; then
    ROOT=$1
fi
cd "$ROOT"
[[ -d .git ]] || { echo "Not a git checkout: $ROOT" >&2; exit 1; }

VERSION=$(awk -F'"' '/^version[[:space:]]*=/{print $2; exit}' src/omen-gui/Cargo.toml)
if [[ -z "$VERSION" ]]; then
    VERSION="2.2.1"
fi
FORK_SHA=$(git rev-parse HEAD)
UPSTREAM_SHA=$(git rev-parse origin/main 2>/dev/null || echo "$FORK_SHA")
UP_SHORT=$(printf '%.7s' "$UPSTREAM_SHA")
FORK_SHORT=$(printf '%.7s' "$FORK_SHA")
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)

mkdir -p /etc/omen-space
cat > /etc/omen-space/build_info.json <<EOF
{
  "version": "$VERSION",
  "commit_sha": "$UPSTREAM_SHA",
  "commit_short": "$UP_SHORT",
  "fork_commit_sha": "$FORK_SHA",
  "fork_commit_short": "$FORK_SHORT",
  "updated_at": "$NOW",
  "repo_path": "$ROOT"
}
EOF
chmod 644 /etc/omen-space/build_info.json

echo "[ok] /etc/omen-space/build_info.json"
cat /etc/omen-space/build_info.json
