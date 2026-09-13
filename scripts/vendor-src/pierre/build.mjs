/*
 * Resolve Shiki and Pierre's theme registry onto Leaf's shims, then derive the
 * accompanying license notices from every package that reached the bundle.
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
    js: `/*! @pierre/diffs ${process.argv[4]} — Apache-2.0 — licenses: pierre-diffs.LICENSES.txt */`,
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

const packageRoots = new Set();
for (const input of Object.keys(result.metafile.inputs)) {
  const relative = input.split("node_modules/").at(-1);
  if (relative === input) continue;
  const parts = relative.split("/");
  packageRoots.add(
    path.join(
      work,
      "node_modules",
      ...(parts[0].startsWith("@") ? parts.slice(0, 2) : parts.slice(0, 1)),
    ),
  );
}
const notices = [...packageRoots].sort().map((root) => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "package.json")));
  const licenseFile = fs
    .readdirSync(root)
    .find((name) => /^(licen[cs]e|copying)(\.|$)/i.test(name));
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
