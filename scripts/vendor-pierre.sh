#!/usr/bin/env bash
# Rebuild the browser-native Pierre renderer used by lf-diff. Pierre and Shiki
# expose far more languages and themes than Leaf declares, so this bundle reads
# the language vocabulary from registry.json and carries only those grammars plus
# the two fixed token themes lf-diff maps onto Leaf's syntax roles.
set -euo pipefail

PIERRE_VERSION=1.3.6
SHIKI_VERSION=4.4.3
ESBUILD_VERSION=0.28.2
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="$ROOT/plugins/leaf/skills/leaf/assets"
OUT="$ROOT/plugins/leaf/skills/leaf/packages/default/vendor/pierre-diffs.esm.js"
NOTICES="$ROOT/plugins/leaf/skills/leaf/packages/default/vendor/pierre-diffs.LICENSES.txt"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

npm install --prefix "$work" --no-save --no-package-lock --silent \
  "@pierre/diffs@$PIERRE_VERSION" \
  "shiki@$SHIKI_VERSION" \
  "@shikijs/core@$SHIKI_VERSION" \
  "@shikijs/engine-javascript@$SHIKI_VERSION" \
  "@shikijs/langs@$SHIKI_VERSION" \
  "@shikijs/themes@$SHIKI_VERSION" \
  "esbuild@$ESBUILD_VERSION"

languages=$(python3 -c '
import json, sys
print(" ".join(json.load(open(sys.argv[1]))["$languages"]["names"]))
' "$ASSETS/registry.json")

{
  cat <<'EOF'
import {
  createBundledHighlighter,
  createCssVariablesTheme,
  createSingletonShorthands,
  getTokenStyleObject,
  stringifyTokenStyle,
} from "@shikijs/core";
import { createJavaScriptRegexEngine } from "@shikijs/engine-javascript";

export const bundledLanguages = {
EOF
  for language in $languages; do
    printf '  "%s": () => import("@shikijs/langs/%s"),\n' "$language" "$language"
  done
  cat <<'EOF'
};

export const createHighlighter = createBundledHighlighter({
  langs: bundledLanguages,
  themes: {},
  engine: createJavaScriptRegexEngine,
});
export const { codeToHtml } = createSingletonShorthands(createHighlighter);
export {
  createCssVariablesTheme,
  createJavaScriptRegexEngine,
  getTokenStyleObject,
  stringifyTokenStyle,
};
export const createOnigurumaEngine = () => {
  throw new Error("Leaf's Pierre bundle includes the JavaScript regex engine only");
};
EOF
} >"$work/shiki-leaf.mjs"

cat >"$work/themes-leaf.mjs" <<'EOF'
import { normalizeTheme } from "@shikijs/core";

const descriptors = new Map([
  ["github-light", {
    name: "github-light",
    load: () => import("@shikijs/themes/github-light"),
  }],
  ["github-dark", {
    name: "github-dark",
    load: () => import("@shikijs/themes/github-dark"),
  }],
]);

export const createTheme = ({ name, load, ...metadata }) => ({
  name,
  ...metadata,
  load: async () => {
    const loaded = await load();
    return normalizeTheme(loaded?.default ?? loaded);
  },
});
export const pierreThemes = { getThemes: () => [] };
export const shikiThemes = { getTheme: (name) => descriptors.get(name) };
EOF

cat >"$work/entry.mjs" <<'EOF'
export { parsePatchFiles } from "@pierre/diffs";
export { preloadDiffHTML } from "@pierre/diffs/ssr";
EOF

cat >"$work/build.mjs" <<'EOF'
import fs from "node:fs";
import path from "node:path";
import { build } from "esbuild";

const work = process.cwd();
const result = await build({
  entryPoints: [path.join(work, "entry.mjs")],
  outfile: process.argv[2],
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "chrome105",
  minify: true,
  legalComments: "inline",
  banner: {
    js: "/*! @pierre/diffs 1.3.6 — Apache-2.0 — licenses: pierre-diffs.LICENSES.txt */",
  },
  plugins: [{
    name: "leaf-pierre-bounds",
    setup(build) {
      build.onResolve({ filter: /^shiki$/ }, () => ({
        path: path.join(work, "shiki-leaf.mjs"),
      }));
      build.onResolve({ filter: /^@pierre\/theming\/themes$/ }, () => ({
        path: path.join(work, "themes-leaf.mjs"),
      }));
    },
  }],
  metafile: true,
});

const packageRoots = new Set();
for (const input of Object.keys(result.metafile.inputs)) {
  const relative = input.split("node_modules/").at(-1);
  if (relative === input) continue;
  const parts = relative.split("/");
  packageRoots.add(path.join(
    work,
    "node_modules",
    ...(parts[0].startsWith("@") ? parts.slice(0, 2) : parts.slice(0, 1)),
  ));
}
const notices = [...packageRoots].sort().map((root) => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "package.json")));
  const licenseFile = fs.readdirSync(root).find((name) =>
    /^(licen[cs]e|copying)(\.|$)/i.test(name)
  );
  if (licenseFile == null)
    throw new Error(`No license file shipped by ${manifest.name}`);
  return [
    `===== ${manifest.name} ${manifest.version} (${manifest.license}) =====`,
    fs.readFileSync(path.join(root, licenseFile), "utf8").trim(),
  ].join("\n");
});
fs.writeFileSync(
  process.argv[3],
  "Third-party licenses for pierre-diffs.esm.js\n\n" + notices.join("\n\n") + "\n",
);
EOF

mkdir -p "$(dirname "$OUT")"
(cd "$work" && node build.mjs "$OUT" "$NOTICES")
printf 'wrote %s (%s bytes) and %s\n' \
  "$OUT" "$(wc -c <"$OUT" | tr -d ' ')" "$NOTICES"
