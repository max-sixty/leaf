#!/usr/bin/env bash
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
