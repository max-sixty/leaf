#!/usr/bin/env bash
#
# The cloud containers' way in. What they install is `wt configure-cloud`, declared in
# `.config/wt.toml` beside the gates it exists to make runnable; this file is the part
# that cannot be an alias, since `wt` has to exist before one can be invoked.
#
# Both hosts run it — Codex Cloud as its setup and maintenance command, Claude Code on
# the web from `.claude/hooks/session-start.sh` — because both containers arrive missing
# the same things. What differs is only how the file is reached, which is all either
# entry point says.
#
# It is not workstation setup: it installs system packages and approves this repo's
# Worktrunk commands without review. Both entry points are what keep it in a container,
# so neither reaches a machine that would mind.
set -euo pipefail

# Unpinned, and `command -v` rather than a version compare, so there is no number here to
# bump. `pipefail` is the point of the bash: a download that fails feeds `sh` nothing,
# which installs nothing and exits clean, and the setup would go on to report success
# having never got its tools. A cached container keeps the `wt` it was built with until the
# cache is reset, which is also what lets it start with no network at all.
if ! command -v wt >/dev/null 2>&1; then
  curl --proto '=https' --tlsv1.2 -LsSf \
    --retry 6 --retry-all-errors --retry-delay 2 \
    "https://github.com/max-sixty/worktrunk/releases/latest/download/worktrunk-installer.sh" |
    WORKTRUNK_UNMANAGED_INSTALL="$HOME/.local/bin" sh
fi
export PATH="$HOME/.local/bin:$PATH"

# The container runs this script from the same branch as `.config/wt.toml`, so its
# unattended Worktrunk commands can approve that branch's declarations — the alias below
# among them, which would otherwise stop for a prompt nobody is there to answer.
wt config approvals add --yes
wt configure-cloud
