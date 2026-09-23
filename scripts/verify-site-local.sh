#!/usr/bin/env bash
# Verify the built public site through the local Worker and its page container.

set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
log="$repo_root/.tmp/wrangler-dev.log"
release=${LEAF_SITE_RELEASE:-$(jq --raw-output .release "$repo_root/.tmp/site/_leaf/site.json")}

# Chrome and Docker share this host, which is only ever true here: a reader's container
# runs on Cloudflare, so nothing in production starts one on the machine drawing the
# page. Chromium answers a host IP-address change by flushing its socket pools with
# ERR_NETWORK_CHANGED, loopback included, and starting a container adds a host interface.
# Prewarm puts that start in the background of the document response, so it lands inside
# the module loads this pass measures and can abort a page's entry module before it
# arrives. Without it the only thing that starts a container is the activation read this
# script's verifier makes and waits on, with no page loading beside it, so the host's
# interfaces are settled for every load the browser is measured on. Production keeps
# prewarm, and the pass over the deployed release exercises it there.
(cd "$repo_root/worker" && npx wrangler dev --port 8787 --var AGENT_PREWARM:false) > "$log" 2>&1 &
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
if ! uv run "$repo_root/scripts/verify_site.py" http://127.0.0.1:8787 \
  --release "$release" "$@"; then
  cat "$log"
  exit 1
fi
