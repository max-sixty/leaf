#!/usr/bin/env bash
# Verify the built public site through the local Worker and its page container.

set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
log="$repo_root/.tmp/wrangler-dev.log"
release=${LEAF_SITE_RELEASE:-$(jq --raw-output .release "$repo_root/.tmp/site/_leaf/site.json")}

(cd "$repo_root/worker" && npx wrangler dev --port 8787) > "$log" 2>&1 &
server=$!
cleanup() {
  kill "$server" 2>/dev/null || true
  wait "$server" || true
}
trap cleanup EXIT

deadline=$((SECONDS + 180))
until curl --fail --silent --output /dev/null http://127.0.0.1:8787/; do
  if ! kill -0 "$server" 2>/dev/null || ((SECONDS >= deadline)); then
    cat "$log"
    exit 1
  fi
  sleep 2
done

# The Worker's own log is the other half of a failure the browser can only report as a
# timeout, and this is the only place it is kept.
if ! LEAF_SITE_ORIGIN=http://127.0.0.1:8787 \
  uv run "$repo_root/scripts/verify-site.py" "$release"; then
  cat "$log"
  exit 1
fi
