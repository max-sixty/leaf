#!/usr/bin/env bash
# Deploy the Worker: `wrangler deploy` with the given arguments, from this directory.
#
# Wrangler uploads the Worker version, then applies the container application's
# settings, which first reads back the version just uploaded. Wrangler gives that read
# 2.5 s, Cloudflare often takes longer, and wrangler then fails with the Worker live.
# Where the application already exists with those settings, as on every deploy after
# the first, the live version works anyway; where it doesn't, the session class has no
# container. Wrangler asks for the same command again, which uploads a new version and
# reads that one back, so that failure alone runs the command again, up to four times
# in all; any other failure ends the deploy.

set -euo pipefail

worker_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
wrangler="$worker_root/../node_modules/.bin/wrangler"
output=$(mktemp "${TMPDIR:-/tmp}/leaf-deploy.XXXXXX")
trap 'rm -f -- "$output"' EXIT

for attempt in 1 2 3 4; do
  if (cd "$worker_root" && "$wrangler" deploy "$@") 2>&1 | tee "$output"; then
    exit 0
  fi
  if ! grep -q "were not fully applied" "$output"; then
    exit 1
  fi
  echo "Retrying the deploy to apply the container application (attempt $attempt failed)" >&2
done
exit 1
