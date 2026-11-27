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

## Current state (2026-11-26, upstream v2.5.4)

The fork is now a very thin layer over upstream — basically one GUI commit plus docs:

| Work | Where |
| --- | --- |
| LampArray backend, calibration API | upstream (PR #379) |
| EN/DE keyboard layout selector | upstream (PR #378) |
| Lazy non-initial pages (startup perf) | upstream (issue #384, v2.4.0) |
| LAMP_SLOT_OVERRIDES_OMEN_MAX incl. Settings slot 98 | upstream (`lamparray.rs`) |
| build_info.json written by setup.sh | upstream |
| Settings key / Copilot label / aligned top row in the **GUI canvas** | fork only (`c3ae7e3`) |
| 8D88 docs, install script, upstream-aware build-info script | fork only |

Fork base: `c188714` (upstream main, v2.5.4).

Note the daemon already maps lamp → slot 98 upstream; what the fork adds is only
the *drawing* of that key, the Copilot label and the 18-column top row.

The branch is `fork/8d88-v254`. Rebuilding on a new upstream is one cherry-pick:

    git fetch origin
    git switch -c fork/8d88 origin/main
    git cherry-pick <settings-key-commit>   # expect conflicts in keyboard.rs
    git checkout <old-fork> -- FORK-8D88.md INSTALL-8D88.md UPDATE-8D88.md \
        SYNC-UPSTREAM.md install-8d88.sh tools/update-build-info.sh tools/calibrate-lamps.py
    cargo build --release && cargo test --release
    sudo ./setup.sh install
    sudo ./tools/update-build-info.sh       # MANDATORY
    git push -f fork fork/8d88

## What to preserve on conflicts

- Settings key slot 98, Copilot label, top-row column alignment in
  `src/omen-gui/src/keyboardrgb/keyboard.rs`.

Upstream reformats that file with rustfmt and uses one-key-per-line rows, so the
old single-line `layout_def` will always conflict. Re-apply:
1. top row without the `("", 0.5)` spacers, `("Del", 2.0)` + Omen/Calc/""/Power;
2. `"Menu" -> "Copilot"` in the `display_name` chain (upstream adds `Enter_num -> "Ent"` there);
3. the `Extra Settings key` block after the row loop (`x: 17.0 * unit_size`, id 98).

Already upstream, do not re-add: EN/DE label map, keyboard_layout setting,
calibration methods, lightbar animation cache, lazy page builders, slot-98 lamp
mapping.

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
