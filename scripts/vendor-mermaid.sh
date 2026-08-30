#!/usr/bin/env bash
# Rebuild skills/leaf/packages/default/vendor/mermaid.min.js.
#
# lf-diagram loads this through a `<script src>` tag and reads `globalThis.mermaid`,
# so the vendored file is `dist/mermaid.min.js`, the IIFE build that defines that
# global. The package's ESM entry defines no global, and the widget imports no
# modules.
#
# There is nothing to bundle: unlike Plot and highlight.js, mermaid publishes its
# dependencies already built into that one file. So this is a copy, and the result
# is byte-identical to what npm ships.
#
# Mermaid changes the ids it draws boxes under between minor versions, and
# lf-diagram finds a commentable box by its id. The widget answers both spellings
# it has seen, so a bump should not move an anchor; that is still the first thing
# to check. Run tests/test_render_aim.py against a new version.
set -euo pipefail

MERMAID_VERSION=11.17.2
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/skills/leaf/packages/default/vendor/mermaid.min.js"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work"

npm pack "mermaid@$MERMAID_VERSION" >/dev/null
tar xzf "mermaid-$MERMAID_VERSION.tgz"
cp package/dist/mermaid.min.js "$OUT"

printf 'wrote %s (%s bytes)\n' "$OUT" "$(wc -c <"$OUT" | tr -d ' ')"
