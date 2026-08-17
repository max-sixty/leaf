#!/usr/bin/env bash
#
# What a cloud container needs before it can run the gates: the locked developer
# environment, the system Chrome the browser suite attaches to (`channel="chrome"`,
# so a preinstalled Chromium of some other build is no substitute), warm pre-commit
# hooks, and Worktrunk with this branch's commands approved.
#
# Both hosts run this one script — Codex Cloud as its setup and maintenance
# command, Claude Code on the web from `.claude/hooks/session-start.sh` — because
# they need the same things, and a second copy is a copy to forget. What differs
# between them is how the script is reached, which is all either entry point says.
#
# It is not workstation setup: it installs system packages and approves this repo's
# Worktrunk commands without review. Both entry points are what keep it in a
# container, so neither reaches a machine that would mind.
set -euo pipefail

WORKTRUNK_VERSION=0.74.0
PRE_COMMIT_VERSION=4.6.1

if ! command -v wt >/dev/null 2>&1 ||
  [[ "$(wt --version)" != "wt v${WORKTRUNK_VERSION}" ]]; then
  curl --proto '=https' --tlsv1.2 -LsSf \
    --retry 6 --retry-all-errors --retry-delay 2 \
    "https://github.com/max-sixty/worktrunk/releases/download/v${WORKTRUNK_VERSION}/worktrunk-installer.sh" |
    WORKTRUNK_UNMANAGED_INSTALL="$HOME/.local/bin" sh
fi

# The container runs this script from the same branch as `.config/wt.toml`, so
# its unattended Worktrunk commands can approve that branch's declarations.
wt config approvals add --yes

uv sync --frozen
uv run playwright install-deps chrome
if ! command -v google-chrome >/dev/null 2>&1; then
  uv run playwright install chrome
fi

uv tool install "pre-commit==${PRE_COMMIT_VERSION}"
pre-commit install-hooks
