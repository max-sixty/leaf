#!/usr/bin/env bash
# Deploy the Worker: `wrangler deploy` with the given arguments, from this directory.
#
# Cloudflare's Worker Versions API sometimes can't find a version just uploaded
# (`100146`, "The requested Worker version could not be found"), for seconds or, in
# an outage, for over 15 minutes, and a later deploy of the same tree succeeds. Wrangler
# then fails in one of two places: reading the version back as it uploads it, which
# names the code, or applying the container application's settings afterwards, which
# reads the version back for only 2.5 s and fails with the Worker live. Where the
# application already exists with those settings, as on every deploy after the first,
# that live version works anyway; where it doesn't, the session class has no container
# until a deploy gets through. Either failure deploys again, 30 s after the first and
# then every 5 minutes until 30 minutes after it; any other failure ends the deploy.

set -euo pipefail

worker_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
wrangler="$worker_root/../node_modules/.bin/wrangler"
output=$(mktemp "${TMPDIR:-/tmp}/leaf-deploy.XXXXXX")
trap 'rm -f -- "$output"' EXIT

first_failure=
pause=30
attempt=1
while true; do
  if (cd "$worker_root" && "$wrangler" deploy "$@") 2>&1 | tee "$output"; then
    exit 0
  fi
  grep --quiet --fixed-strings \
    -e '[code: 100146]' -e 'were not fully applied' "$output" || exit 1
  first_failure=${first_failure:-$SECONDS}
  if ((SECONDS + pause > first_failure + 1800)); then
    exit 1
  fi
  echo "Cloudflare could not find the uploaded Worker version (attempt $attempt); deploying again in ${pause}s" >&2
  sleep "$pause"
  pause=300
  attempt=$((attempt + 1))
done
