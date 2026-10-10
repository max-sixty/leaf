#!/usr/bin/env node
/** Build component-owned CSS into ready distribution sheets.
 *
 * Source entrypoints use native CSS imports; esbuild resolves them at contributor
 * build time. Runtime delivery, installation and packages consume the committed
 * complete sheets, so introducing an owner never adds a startup request or compiler.
 * Existing layer/scope wrappers remain with composition and their source owners.
 */
import { build } from "esbuild";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const assets = "skills/leaf/assets";
const packages = "skills/leaf/packages";
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
const check = process.argv.includes("--check");
const stale = [];
for (const [source, output] of entries) {
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
    banner: { css: `/* Generated from ${source} by npm run build:styles. */` },
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
  const css = result.outputFiles[0].text;
  if (check) {
    if ((await readFile(resolve(root, output), "utf8")) !== css) stale.push(output);
  } else await writeFile(resolve(root, output), css);
}
if (stale.length)
  throw new Error(`Stale stylesheets; run npm run build:styles:\n${stale.join("\n")}`);
