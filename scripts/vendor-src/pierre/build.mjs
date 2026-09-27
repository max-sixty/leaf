/*
 * Resolve Shiki and Pierre's theme registry onto Leaf's shims, recording in
 * `meta.json` what reached the bundle so `scripts/browser/shipped.mjs` can write
 * its license notices.
 */
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
    js: `/*! @pierre/diffs ${process.argv[3]} — Apache-2.0 — licenses: pierre-diffs.LICENSES.txt */`,
  },
  plugins: [
    {
      name: "leaf-pierre-bounds",
      setup(build) {
        build.onResolve({ filter: /^shiki$/ }, () => ({
          path: path.join(work, "shiki-leaf.mjs"),
        }));
        build.onResolve({ filter: /^@pierre\/theming\/themes$/ }, () => ({
          path: path.join(work, "themes-leaf.mjs"),
        }));
      },
    },
  ],
  metafile: true,
});
fs.writeFileSync("meta.json", JSON.stringify(result.metafile));
