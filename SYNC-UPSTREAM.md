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

## What to preserve on conflicts

- LAMP_SLOT_OVERRIDES_8D88 and the is_board_8d88 / n == 120 gate.
- Settings key slot 98, Copilot label, top-row column alignment.
- EN/DE label map and the keyboard_layout setting.
- lightbar_animation_loop and the last_lightbar_level cache.
- Our tags only; do not force-push over upstream tags.

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
