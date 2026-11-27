# Keeping this fork in sync with upstream

Remotes in the working copy:

    origin  https://github.com/yunusemreyl/omen-space.git   (upstream, read-only)
    fork    https://github.com/Dmitriy-Romanov/omen-space.git (this fork)

## Regular sync

    git switch main
    git fetch origin
    git log --oneline --decorate origin/main..HEAD   # our additions
    git merge origin/main
    # resolve conflicts; keep the 8D88 overlay on top
    cargo test -p omen-space-daemon
    git push fork main

Prefer merge on main so public history stays stable. Rebase feature/PR branches
instead if they are meant to be clean upstream patches.

## Current state (2026-11-27, upstream v2.6.1)

The fork is now one GUI commit plus docs. Both upstream contributions are merged.

| Work | Where |
| --- | --- |
| LampArray backend, calibration API | upstream (PR #379) |
| EN/DE keyboard layout selector | upstream (PR #378) |
| Lazy non-initial pages | upstream (issue #384, v2.4.0) |
| Per-key colour presets | upstream (PR #397, v2.6.0) |
| Power-profile failure reporting (issue #396) | upstream (v2.6.0) |
| Settings key / Copilot label / aligned top row | fork only (e178b7d) |
| 8D88 docs, install script, build-info script | fork only |

Fork base: `c43cabe` (upstream main, v2.6.1). Branch `fork/8d88-v261`.

The whole fork-only source diff is 30 lines in `keyboard.rs`.

Rebuilding on a new upstream:

    git fetch origin
    git switch -c fork/8d88 origin/main
    git cherry-pick <settings-key-commit>
    git checkout <old-fork> -- FORK-8D88.md INSTALL-8D88.md UPDATE-8D88.md \
        SYNC-UPSTREAM.md install-8d88.sh tools/update-build-info.sh tools/calibrate-lamps.py
    cargo build --release && cargo test --release
    sudo ./setup.sh install
    sudo ./tools/update-build-info.sh       # MANDATORY
    git push -f fork fork/8d88

## What to preserve on conflicts

Only three things, all in `src/omen-gui/src/keyboardrgb/keyboard.rs`:

1. Top row without the `("", 0.5)` spacers, `("Del", 2.0)` and Omen/Calc/""/Power.
2. `"Menu" -> "Copilot"` in the `display_name` chain.
3. The `Extra Settings key` block after the row loop: id 98,
   `x: 17.0 * unit_size`, and `zone: get_zone_for_key("Settings")`
   (upstream added the `zone` field to `KeyGeom` in v2.6.1).

Already upstream, do not re-add: presets, lazy pages, EN/DE layout,
calibration API, lightbar cache, slot-98 lamp mapping, power-profile error
reporting.

## Scenarios

1. Upstream accepts the generic parts: drop those duplicate commits from the
   fork, keep only 8D88-specific work, and follow upstream releases.
2. Upstream rejects or delays: keep the fork, merge upstream monthly, and keep
   the board-specific commits on top.
3. Invited as co-author: push feature branches to the upstream repository and
   keep the fork for hardware-specific experiments and docs.
4. Fork becomes unnecessary: archive it but keep INSTALL-8D88.md and the
   calibration report for the next 8D88 owner.

## PR branches from the fork

For each upstream PR, branch from origin/main and cherry-pick only the relevant
commits; do not send the whole fork history.

    git fetch origin
    git switch -c pr/lamparray origin/main
    git cherry-pick <commits>
    git push fork pr/lamparray
