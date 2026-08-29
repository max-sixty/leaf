#!/usr/bin/env bash
# Rebuild skills/leaf/packages/default/vendor/plot.esm.js.
#
# Observable Plot draws lf-chart. Nothing published is loadable as it stands, and
# there are three things to try: `src/index.js` is browser-native ESM but imports
# d3 by bare specifier; `dist/plot.umd.min.js` leaves d3 external too, reading a
# `d3` global the page would have to have loaded first; and a CDN's prebuilt ESM
# (jsdelivr's `+esm`) is smaller than this bundle only because it imports d3 from
# a second URL, which `default-src 'self'` will not fetch. So the vendored file is
# one we produce, the same way highlight.js's is: Plot and the parts of d3 it
# reaches for, bundled to one browser-native ESM file with no specifier left in
# it. The alternative is vendoring d3 whole beside it, which is 100KB more and
# two files whose versions can drift apart.
#
# The whole of Plot goes in rather than the marks lf-chart happens to use today.
# Naming the marks here would put the module's mark list in a second place, where
# a chart kind added in the module renders as a TypeError instead; the list is
# worth about 100KB, against a payload whose mermaid bundle is 2.6MB.
set -euo pipefail

PLOT_VERSION=0.6.17
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/skills/leaf/packages/default/vendor/plot.esm.js"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work"

npm install --silent --no-audit --no-fund "@observablehq/plot@$PLOT_VERSION" >/dev/null
d3_version=$(node -p "require('./node_modules/d3/package.json').version")

echo 'export * from "@observablehq/plot";' >entry.mjs

npx --yes esbuild@0.25 entry.mjs \
  --bundle --format=esm --minify --legal-comments=inline \
  --banner:js="/*! @observablehq/plot $PLOT_VERSION — ISC — https://observablehq.com/plot
 *  bundled with d3 $d3_version — ISC — https://d3js.org */" \
  --outfile="$OUT"

# A page's CSP is `default-src 'self'`, which allows neither eval nor a lazy chunk, and
# both of those are one careless import away: d3 carries a `new Function` in d3-dsv's CSV
# parser, and Plot reaches for none of d3-dsv today. What keeps that true is this check
# rather than anyone remembering, because the failure it prevents is a chart that draws in
# a developer's page and refuses in a reader's.
for banned in 'new Function' 'eval(' 'import('; do
  if grep -qF "$banned" "$OUT"; then
    printf 'refused: the bundle contains %s, which the page CSP forbids\n' "$banned" >&2
    rm -f "$OUT"
    exit 1
  fi
done

printf 'wrote %s (%s bytes)\n' "$OUT" "$(wc -c <"$OUT" | tr -d ' ')"
