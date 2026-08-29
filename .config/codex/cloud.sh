#!/usr/bin/env bash
set -euo pipefail

mkdir -p ~/.local/bin
curl -fsSL https://github.com/max-sixty/worktrunk/releases/latest/download/worktrunk-x86_64-unknown-linux-musl.tar.xz \
  | tar -xJ -C ~/.local/bin --strip-components=1 worktrunk-x86_64-unknown-linux-musl/wt
exec ~/.local/bin/wt -y cloud "$@"
