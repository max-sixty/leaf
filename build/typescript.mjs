#!/usr/bin/env node
/**
 * Compile Leaf's TypeScript modules to the JavaScript a page loads.
 *
 * A module of the runtime or of a bundled package may be written as `name.ts`. The
 * layer serves `name.js` beside it, which this module writes and the tree commits, so
 * a page, an install from git, the tests and the kernel compiler read JavaScript as
 * before and nothing on a user's machine compiles. A `.js` whose first line names its
 * source is this module's output; every other `.js` is written by hand. Package authors
 * still write plain JavaScript, which Leaf serves as written.
 *
 * Compiling strips the types (`stripTypeScriptTypes`), so a source holds only syntax
 * that erases (`erasableSyntaxOnly`), and formats the result with the repository's
 * formatter and settings (`.oxfmtrc.jsonc`), which closes the gaps the types leave.
 * The output keeps every comment, and the formatter's hook and the other tools that
 * read the tree's JavaScript take it as it stands. A line in the output stands near,
 * not at, its line in the source: find a stack trace's or a lint report's line in the
 * `.ts` by its code.
 *
 * Run `node build/typescript.mjs` to write every output after an edit, as the
 * pre-commit hook does; `pnpm run build:browser` writes them too, and
 * `pnpm run check:browser` refuses a stale one, or one whose source is gone.
 */
import { readdir, readFile, rm, writeFile } from "node:fs/promises";
import { stripTypeScriptTypes } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));

/** The directories that may hold TypeScript modules: the layer and each package. */
const sourceRoots = async (directory) => [
  "browser",
  ...(await readdir(path.join(directory, "packages"), { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map(({ name }) => `packages/${name}`),
];

/** Every module file with `suffix` under the layer and the packages, by its path from
 * `directory`, sorted. The vendored bundles' and declarations' directories hold none. */
async function modulesEndingWith(suffix, directory) {
  const modules = [];
  for (const base of await sourceRoots(directory))
    for (const entry of await readdir(path.join(directory, base), {
      recursive: true,
    })) {
      const name = entry.split(path.sep).join("/");
      if (name.endsWith(suffix) && !/(^|\/)(vendor|types|node_modules)\//.test(name))
        modules.push(`${base}/${name}`);
    }
  return modules.sort();
}

/** Every TypeScript module, by its path from `directory`, sorted. */
export const typescriptModules = async (directory = root) =>
  (await modulesEndingWith(".ts", directory)).filter((name) => !name.endsWith(".d.ts"));

const banner = (source) =>
  `// Compiled from ${path.posix.basename(source)} by build/typescript.mjs; edit that file.\n`;

/** Strip `source`'s types without Node's notice that the API is experimental: its
 * output is fixed by the source alone, blanking each type where it stands. */
function strip(source) {
  const { emitWarning } = process;
  process.emitWarning = () => {};
  try {
    return stripTypeScriptTypes(source, { mode: "strip" });
  } finally {
    process.emitWarning = emitWarning;
  }
}

/** The formatter's settings, read from `.oxfmtrc.jsonc` with its comments taken out. */
async function formatSettings() {
  const { ignorePatterns, ...settings } = JSON.parse(
    (await readFile(path.join(root, ".oxfmtrc.jsonc"), "utf8"))
      .replace(/^\s*\/\/.*$/gm, "")
      .replace(/,(\s*[}\]])/g, "$1"),
  );
  return settings;
}

/** The JavaScript a page loads for the TypeScript module at `name`. */
export async function compile(source, name) {
  // Imported here, so a tool that only lists the modules needs no formatter.
  const { format } = await import("oxfmt");
  const { code, errors } = await format(
    name.replace(/\.ts$/, ".js"),
    banner(name) + strip(source),
    await formatSettings(),
  );
  if (errors.length) throw new Error(`${name}: ${errors[0].message}`);
  return code;
}

/** Each compiled module's path and bytes. */
export async function typescriptOutputs(directory = root) {
  const outputs = new Map();
  for (const name of await typescriptModules(directory))
    outputs.set(
      name.replace(/\.ts$/, ".js"),
      Buffer.from(
        await compile(await readFile(path.join(directory, name), "utf8"), name),
      ),
    );
  return outputs;
}

/** Every compiled module in `directory`: each `.js` whose first line names the
 * TypeScript it was compiled from, whether or not that source still stands. */
export async function compiledModules(directory = root) {
  const compiled = [];
  for (const name of await modulesEndingWith(".js", directory))
    if (
      (await readFile(path.join(directory, name), "utf8")).startsWith(
        banner(name.replace(/\.js$/, ".ts")),
      )
    )
      compiled.push(name);
  return compiled;
}

/** Write every output, and remove each whose source is gone. */
async function main() {
  const outputs = await typescriptOutputs();
  for (const name of await compiledModules())
    if (!outputs.has(name)) await rm(path.join(root, name));
  for (const [name, bytes] of outputs) await writeFile(path.join(root, name), bytes);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
