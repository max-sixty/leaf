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
 * dependency publisher as well as the compiler. */
export const styleEntries = [
  [
    "node_modules/@awesome.me/webawesome/dist/styles/themes/default.css",
    "browser/styles/vendor/webawesome-theme.css",
  ],
];

export async function styleOutputs() {
  const outputs = new Map();
  for (const [source, output] of styleEntries)
    outputs.set(output, Buffer.from(await sheet(source)));
  return outputs;
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
