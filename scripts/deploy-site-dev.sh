#!/usr/bin/env bash
# Deploy and verify the one standing Cloudflare development environment.

set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
worker_root="$repo_root/worker"
origin=https://leaf-website-dev.maxsixty.workers.dev
wrangler="$worker_root/node_modules/.bin/wrangler"
secret_file=

cleanup() {
  if [[ -n "$secret_file" ]]; then
    rm -f -- "$secret_file"
  fi
}
trap cleanup EXIT

if [[ -z ${CLOUDFLARE_API_TOKEN:-} ]]; then
  echo "CLOUDFLARE_API_TOKEN is required" >&2
  exit 2
fi
if [[ ! -x "$wrangler" ]]; then
  echo "website dependencies are missing; run npm ci --prefix $worker_root" >&2
  exit 2
fi

deploy_arguments=(deploy --env dev --containers-rollout=immediate)
if ! "$wrangler" secret list --env dev 2>/dev/null \
  | jq -e '.[] | select(.name == "OPENAI_API_KEY")' >/dev/null; then
  if [[ -z ${OPENAI_API_KEY:-} ]]; then
    echo "OPENAI_API_KEY is required for the dev Worker's first deployment" >&2
    exit 2
  fi
  secret_file=$(mktemp "${TMPDIR:-/tmp}/leaf-dev-secrets.XXXXXX")
  chmod 600 "$secret_file"
  printf 'OPENAI_API_KEY=%s\n' "$OPENAI_API_KEY" >"$secret_file"
  deploy_arguments+=(--secrets-file "$secret_file")
fi
unset OPENAI_API_KEY

uv run --project "$repo_root" "$repo_root/scripts/site.py"
release=$(jq --raw-output .release "$repo_root/.tmp/site/_leaf/site.json")

(
  cd "$worker_root"
  "$wrangler" "${deploy_arguments[@]}"
)

deadline=$((SECONDS + 900))
until LEAF_SITE_ORIGIN="$origin" uv run --project "$repo_root" \
  "$repo_root/scripts/verify-site.py" "$release"; do
  ((SECONDS < deadline)) || exit 1
  sleep 10
done
uv run --project "$repo_root" "$repo_root/scripts/benchmark-site.py" "$origin"
