/** Build component-owned CSS into ready distribution sheets.
 *
 * Source entrypoints use native CSS imports; esbuild resolves them at contributor
 * build time. Runtime delivery, installation and packages consume the committed
 * complete sheets, so introducing an owner never adds a startup request or compiler.
 * Existing layer/scope wrappers remain with composition and their source owners.
 * `build/browser/build.mjs` writes and checks these outputs with its own.
 */
import { readdir } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const assets = "skills/leaf/assets";
const packages = "skills/leaf/packages";

/** Source and output pairs, readable without build dependencies by the trusted
 * dependency publisher as well as the compiler. */
export async function styleEntries() {
  const entries = [
    [`${assets}/styles/theme.css`, `${assets}/theme.css`],
    [`${assets}/styles/shadow.css`, `${assets}/shadow.css`],
    [`${assets}/styles/chrome.css`, `${assets}/runtime/chrome.css`],
  ];
  for (const entry of await readdir(resolve(root, packages), { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const packageName = entry.name;
    const source = `${packages}/${packageName}/styles`;
    let files;
    try {
      files = await readdir(resolve(root, source));
    } catch (error) {
      if (error.code === "ENOENT") continue;
      throw error;
    }
    for (const file of files.filter((file) => /^(theme|shadow)\.css$/.test(file)))
      entries.push([`${source}/${file}`, `${packages}/${packageName}/${file}`]);
  }
  return entries;
}

export async function styleOutputs() {
  const outputs = new Map();
  for (const [source, output] of await styleEntries())
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
