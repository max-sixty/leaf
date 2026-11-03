/** Bundle the third-party stylesheets Leaf's own sheets import into ready files.
 *
 * Leaf's sheets need no build: layer composition and the serving runtime place each
 * `@import` of a file beside them inline (`leaf.layer.stylesheet`). A dependency's
 * sheet lives in `node_modules`, which an install doesn't have, so esbuild resolves its
 * imports here at contributor build time and the result is committed beside the sheet
 * that imports it. `build/browser/build.mjs` writes and checks these outputs with its
 * own.
 */
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** Source and output pairs, readable without build dependencies by the trusted
 * dependency publisher as well as the compiler. A third member takes one region of
 * the source instead of all of it (`region`).
 * @type {[source: string, output: string, part?: Region][]} */
export const styleEntries = [
  [
    "node_modules/@awesome.me/webawesome/dist/styles/themes/default.css",
    "browser/styles/vendor/webawesome-theme.css",
  ],
  [
    "node_modules/@awesome.me/webawesome/dist/styles/native.css",
    "browser/styles/vendor/webawesome-choice.css",
    { region: "Checkboxes + Radios", scope: ".choice" },
  ],
];

export async function styleOutputs() {
  const outputs = new Map();
  for (const [source, output, part] of styleEntries)
    outputs.set(
      output,
      Buffer.from(part ? await region(source, part) : await sheet(source)),
    );
  return outputs;
}

/** One `#region` of a dependency's sheet, scoped to the Leaf face that takes it. Web
 * Awesome ships its styles for native controls only in `native.css`, which restyles
 * the whole document, so Leaf takes the region for radios and checkboxes and scopes it
 * to its `.choice` face (controls.css). A region that moves or goes fails the build
 * rather than shipping an empty sheet.
 * @typedef {{ region: string, scope: string }} Region
 * @param {string} source
 * @param {Region} part */
async function region(source, { region: name, scope }) {
  const { readFile } = await import("node:fs/promises");
  const text = await readFile(resolve(root, source), "utf8");
  const start = text.indexOf(`/* #region ${name} `);
  const end = text.indexOf("/* #endregion */", start);
  if (start < 0 || end < 0) throw new Error(`No region "${name}" in ${source}`);
  const rules = text.slice(text.indexOf("\n", start) + 1, end).trimEnd();
  return (
    `/* @noformat Generated from ${source}, region "${name}", by build/styles.mjs. */\n` +
    `@scope (${scope}) {\n${rules}\n}\n`
  );
}

async function sheet(source) {
  const { build } = await import("./esbuild.mjs");
  const result = await build({
    absWorkingDir: root,
    entryPoints: [source],
    bundle: true,
    write: false,
    metafile: true,
    logLevel: "silent",
    charset: "utf8",
    legalComments: "inline",
    plugins: [
      {
        name: "runtime-assets",
        setup(builder) {
          builder.onResolve({ filter: /.*/ }, (args) =>
            args.kind === "url-token" ? { path: args.path, external: true } : undefined,
          );
        },
      },
    ],
    banner: { css: `/* @noformat Generated from ${source} by build/styles.mjs. */` },
  });
  if (result.warnings.length)
    throw new Error(
      `Stylesheet build warnings in ${source}:\n${result.warnings.map((w) => w.text).join("\n")}`,
    );
  const deferredImports = Object.values(result.metafile.outputs)
    .flatMap((output) => output.imports)
    .filter((item) => item.kind === "import-rule");
  if (deferredImports.length)
    throw new Error(`Stylesheets must be complete at distribution: ${source}`);
  return result.outputFiles[0].text;
}
