#!/usr/bin/env node
/**
 * Build Leaf's committed browser framework from locked contributor dependencies.
 *
 * Run with --check to compare a fresh, typechecked build with committed bytes
 * without writing them. This module owns its source roots, outputs, and manifest;
 * Leaf installation, vendoring, activation, and export never invoke this tool.
 */
import { createHash } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { parse } from "acorn";

const root = fileURLToPath(new URL("../../", import.meta.url));
const outputRoot = "skills/leaf/assets/vendor";
const entry = "scripts/browser/index.ts";
const modulePath = `${outputRoot}/browser-runtime.js`;
const manifestPath = `${outputRoot}/browser-runtime.manifest.json`;
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
const relative = (file) => path.relative(root, file).split(path.sep).join("/");

export function checkModule(source) {
  const parsed = parse(source, { ecmaVersion: "latest", sourceType: "module" });
  function visit(node) {
    if (!node || typeof node !== "object") return;
    if (
      node.type === "ImportExpression" ||
      (["ImportDeclaration", "ExportNamedDeclaration", "ExportAllDeclaration"].includes(
        node.type,
      ) &&
        node.source) ||
      (["CallExpression", "NewExpression"].includes(node.type) &&
        node.callee.type === "Identifier" &&
        ["eval", "Function", "require"].includes(node.callee.name))
    ) {
      throw new Error(
        "Browser output must be self-contained ESM without runtime compilation",
      );
    }
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach(visit);
      else visit(value);
    }
  }
  visit(parsed);
}

export async function buildOutputs() {
  const packageJson = JSON.parse(
    await readFile(path.join(root, "package.json"), "utf8"),
  );
  const lockfile = await readFile(path.join(root, "package-lock.json"));
  const lock = JSON.parse(lockfile);
  for (const [name, version] of Object.entries(packageJson.devDependencies)) {
    const installed = JSON.parse(
      await readFile(path.join(root, "node_modules", name, "package.json"), "utf8"),
    );
    if (
      installed.version !== version ||
      lock.packages[`node_modules/${name}`].version !== version
    ) {
      throw new Error(`${name} does not match its exact dependency pin; run npm ci`);
    }
  }
  const typecheck = spawnSync(
    process.execPath,
    [
      path.join(root, "node_modules/typescript/bin/tsc"),
      "--project",
      "scripts/browser/tsconfig.json",
    ],
    { cwd: root, encoding: "utf8" },
  );
  if (typecheck.error) throw typecheck.error;
  if (typecheck.status !== 0) throw new Error(typecheck.stdout + typecheck.stderr);

  const result = await build({
    absWorkingDir: root,
    entryPoints: [entry],
    outfile: modulePath,
    tsconfig: "scripts/browser/tsconfig.json",
    platform: "browser",
    format: "esm",
    target: "es2022",
    bundle: true,
    minify: true,
    sourcemap: "linked",
    sourcesContent: true,
    legalComments: "eof",
    metafile: true,
    write: false,
    logLevel: "silent",
  });
  const module = result.metafile.outputs[modulePath];
  if (module.imports.length) throw new Error("Browser output has unbundled imports");
  const outputs = new Map(
    result.outputFiles.map((file) => [relative(file.path), Buffer.from(file.contents)]),
  );
  checkModule(outputs.get(modulePath).toString());

  const packagePaths = [
    ...new Set(
      Object.keys(result.metafile.inputs)
        .filter((name) => name.startsWith("node_modules/"))
        .map((name) => name.match(/^node_modules\/(?:@[^/]+\/)?[^/]+/)[0]),
    ),
  ].sort();
  const dependencies = {};
  const licenses = [];
  for (const packagePath of packagePaths) {
    const pkg = JSON.parse(
      await readFile(path.join(root, packagePath, "package.json"), "utf8"),
    );
    if (lock.packages[packagePath].version !== pkg.version) {
      throw new Error(`${pkg.name} does not match package-lock.json; run npm ci`);
    }
    dependencies[pkg.name] = pkg.version;
    licenses.push(
      `${pkg.name} ${pkg.version}\n\n${await readFile(path.join(root, packagePath, "LICENSE"), "utf8")}`,
    );
  }
  outputs.set(
    `${outputRoot}/browser-runtime.LICENSES.txt`,
    Buffer.from(licenses.join("\n\n")),
  );
  const manifest = {
    format: "leaf-browser-build-v1",
    sourceRoots: ["scripts/browser"],
    sourceInputs: Object.keys(result.metafile.inputs)
      .filter((name) => !name.startsWith("node_modules/"))
      .sort(),
    entryPoints: { [modulePath]: entry },
    outputRoot,
    lockfile: "package-lock.json",
    lockfileSha256: digest(lockfile),
    commands: {
      install: "npm ci",
      build: "npm run build:browser",
      check: "npm run check:browser",
      test: "npm run test:browser",
    },
    contributorDependencies: packageJson.devDependencies,
    bundledDependencies: dependencies,
    internalModule: "/vendor/browser-runtime.js",
    publicImport: "/runtime/widget-api.js",
    exports: module.exports,
    externalizedModules: module.imports,
    pageModules:
      "Browser-ready authored page modules are captured with their revision; they are not contributor-build inputs.",
    outputs: Object.fromEntries(
      [...outputs].map(([name, bytes]) => [
        name,
        { bytes: bytes.length, sha256: digest(bytes) },
      ]),
    ),
  };
  outputs.set(manifestPath, Buffer.from(JSON.stringify(manifest, null, 2) + "\n"));
  return outputs;
}

export async function checkOutputs(outputs, directory = root) {
  const stale = [];
  for (const [name, expected] of outputs) {
    let actual;
    try {
      actual = await readFile(path.join(directory, name));
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
    if (!actual?.equals(expected)) stale.push(name);
  }
  if (stale.length)
    throw new Error(
      `Stale browser output; run npm run build:browser:\n${stale.join("\n")}`,
    );
}

async function main(args) {
  if (args.length === 1 && args[0] === "--help") {
    console.log(
      "Usage: node scripts/browser/build.mjs [--check]\n\nBuild committed browser ESM, or check it without writing. Run npm ci first.",
    );
    return;
  }
  if (args.length > 1 || (args.length && args[0] !== "--check")) {
    throw new Error("Usage: node scripts/browser/build.mjs [--check]");
  }
  const outputs = await buildOutputs();
  if (args[0] === "--check") await checkOutputs(outputs);
  else {
    await mkdir(path.join(root, outputRoot), { recursive: true });
    for (const [name, bytes] of outputs) await writeFile(path.join(root, name), bytes);
  }
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main(process.argv.slice(2)).catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
