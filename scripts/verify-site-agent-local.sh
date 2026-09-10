#!/usr/bin/env bash
# Run the hosted-agent journey against the website adapter and this host's Codex login.

set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/leaf-site-agent.XXXXXX")
site_root="$run_root/site"
log="$repo_root/.tmp/website-agent-local.log"
server=

cleanup() {
  if [[ -n "$server" ]]; then
    kill "$server" 2>/dev/null || true
    wait "$server" 2>/dev/null || true
  fi
  rm -rf -- "$run_root"
}
trap cleanup EXIT

uv run --project "$repo_root" "$repo_root/scripts/site.py"
cp -R "$repo_root/.tmp/site" "$site_root"
release=$(jq --raw-output .release "$site_root/_leaf/site.json")

LEAF_SITE_ROOT="$site_root" LEAF_AGENT_EPHEMERAL=1 uv run --project "$repo_root" \
  python "$repo_root/worker/server.py" >"$log" 2>&1 &
server=$!

deadline=$((SECONDS + 30))
until curl --fail --silent --output /dev/null http://127.0.0.1:8080/health; do
  if ! kill -0 "$server" 2>/dev/null || ((SECONDS >= deadline)); then
    cat "$log"
    exit 1
  fi
  sleep 1
done

if ! LEAF_SITE_ORIGIN=http://127.0.0.1:8080 \
  LEAF_VERIFY_AGENT=1 \
  LEAF_VERIFY_DIRECT_AGENT=1 \
  uv run --project "$repo_root" "$repo_root/scripts/verify-site.py" "$release"; then
  cat "$log"
  exit 1
fi

grep --fixed-strings '"component":"leaf-agent"' "$log"
