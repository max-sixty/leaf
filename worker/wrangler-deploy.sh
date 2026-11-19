#!/usr/bin/env bash
# Deploy the Worker: `wrangler deploy` with the given arguments, from this directory.
#
# Wrangler uploads the Worker version, then applies that version's image to the
# session class's container application, which reads back the version just uploaded.
# Cloudflare can answer that read 404 for a moment, and wrangler then fails with the
# Worker live and the image not applied, asking for the same command again. So that
# failure alone runs the command once more; any other failure ends the deploy.

set -euo pipefail

worker_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
wrangler="$worker_root/../node_modules/.bin/wrangler"
output=$(mktemp "${TMPDIR:-/tmp}/leaf-deploy.XXXXXX")
trap 'rm -f -- "$output"' EXIT

for attempt in 1 2; do
  if (cd "$worker_root" && "$wrangler" deploy "$@") 2>&1 | tee "$output"; then
    exit 0
  fi
  if ! grep -q "were not fully applied" "$output"; then
    exit 1
  fi
  echo "Retrying the deploy to apply the container application (attempt $attempt failed)" >&2
done
exit 1
