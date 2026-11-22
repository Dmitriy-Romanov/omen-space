# Updating the 8D88 fork

This is the mandatory procedure for this fork. The update center compares
/etc/omen-space/build_info.json with upstream GitHub; if that file is stale the
UI reports an old build even when the binaries are current.

## Normal update from the fork

    cd /home/dima/omen-space
    git fetch fork
    git pull --ff-only fork main
    sudo ./setup.sh install --non-interactive

    # MANDATORY metadata refresh for this fork:
    git fetch origin
    sudo ./tools/update-build-info.sh /home/dima/omen-space

    sudo systemctl restart omen-space-daemon
    # close and reopen omen-gui

## Manual binary update (what we do during development)

    cd /home/dima/omen-space
    cargo build --release -p omen-space-daemon -p omen-gui
    sudo install -m 755 target/release/omen-space-daemon /usr/libexec/omen-space/omen-space-daemon
    sudo install -m 755 target/release/omen-gui /usr/bin/omen-gui

    # MANDATORY - otherwise the Updater tab lies:
    git fetch origin
    sudo ./tools/update-build-info.sh /home/dima/omen-space

    sudo systemctl restart omen-space-daemon
    # close and reopen omen-gui

## What the script writes

    /etc/omen-space/build_info.json
      version              from src/omen-gui/Cargo.toml
      commit_sha           origin/main (upstream base the UI compares against)
      commit_short         first 7 of upstream SHA
      fork_commit_sha      actual fork HEAD
      fork_commit_short    first 7 of fork HEAD
      updated_at           UTC timestamp
      repo_path            /home/dima/omen-space

The extra fork_commit fields are informational; the updater only reads
commit_sha/commit_short. That is why commit_sha must be the upstream base, not
the fork merge commit: otherwise the GitHub compare cannot resolve it and the
update state looks wrong.

## Upstream catch-up

    git fetch origin
    git switch main
    git merge origin/main
    cargo test -p omen-space-daemon
    cargo build --release -p omen-space-daemon -p omen-gui
    sudo install ...            # as above
    sudo ./tools/update-build-info.sh
    git push fork main
    git push fork --tags

Resolve conflicts by keeping the 8D88-specific overlay and re-applying it on
top of the upstream changes; see UPSTREAM-2026-11-16.md for the last merge.

## Rollback

    git tag -l 'checkpoint-*'
    git switch <tag>            # e.g. checkpoint-2026-11-16-pre-upstream
    # rebuild/install and rerun tools/update-build-info.sh
