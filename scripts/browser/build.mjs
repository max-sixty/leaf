#!/usr/bin/env node
/**
 * Build Leaf's committed browser framework from locked contributor dependencies.
 *
 * Run with --check to compare a fresh, typechecked build with committed bytes
 * without writing them. This module owns its source roots, outputs, and manifest;
 * Leaf installation, vendoring, activation, and export never invoke this tool.
 *
 * The page's one copy of Lit is built here, as `vendor/lit.js`: every public Lit
 * module in one namespace, shaped like Lit's own `lit-all` bundle, where the
 * static-html tags are renamed `staticHtml`, `staticSvg`, and `staticMathml` so
 * they do not shadow the ordinary ones. The framework imports Lit from it, and so
 * does the Web Awesome bundle (`scripts/vendor-src/webawesome/build.mjs`), so a page
 * registers one LitElement, one template cache, and one version. Outputs import
 * only one another, statically; nothing else crosses the bundle.
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
const diagnosticsRoot = "scripts/browser/generated";
const entry = "scripts/browser/index.ts";
const modulePath = `${outputRoot}/browser-runtime.js`;
const litPath = `${outputRoot}/lit.js`;
const manifestPath = `${diagnosticsRoot}/browser-runtime.manifest.json`;
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
const relative = (file) => path.relative(root, file).split(path.sep).join("/");

/** Refuse runtime compilation and every import but a static one of a sibling output. */
export function checkModule(source, name = modulePath, siblings = new Set()) {
  const parsed = parse(source, { ecmaVersion: "latest", sourceType: "module" });
  const sibling = (specifier) =>
    /^\.{1,2}\//.test(specifier) &&
    siblings.has(path.posix.join(path.posix.dirname(name), specifier));
  function visit(node) {
    if (!node || typeof node !== "object") return;
    if (
      node.type === "ImportExpression" ||
      (["ImportDeclaration", "ExportNamedDeclaration", "ExportAllDeclaration"].includes(
        node.type,
      ) &&
        node.source &&
        !sibling(node.source.value)) ||
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

/**
 * Build `lit.js` from Lit's published exports, and bind every other Lit import to it.
 *
 * Star exports would make static-html's tags ambiguous with the ordinary ones and
 * drop both, so that module is exported by name instead; the polyfill module patches
 * browsers older than any Leaf supports.
 */
function litModule(lit) {
  const stars = Object.keys(lit.exports)
    .filter(
      (subpath) => !["./static-html.js", "./polyfill-support.js"].includes(subpath),
    )
    .map((subpath) => `export * from "lit${subpath.slice(1)}";`);
  const contents = [
    ...stars,
    'export { html as staticHtml, svg as staticSvg, mathml as staticMathml, literal, unsafeStatic, withStatic } from "lit/static-html.js";',
  ].join("\n");
  return {
    name: "leaf-lit",
    setup(build) {
      build.onResolve({ filter: /^leaf:lit$/ }, () => ({
        path: "lit",
        namespace: "leaf-lit",
      }));
      build.onLoad({ filter: /.*/, namespace: "leaf-lit" }, () => ({
        contents,
        resolveDir: root,
      }));
      build.onResolve({ filter: /^lit(\/|$)/ }, ({ path: specifier, namespace }) => {
        if (namespace === "leaf-lit") return undefined;
        // Its tags go by their lit-all names, which a bare rebinding would not reach.
        if (specifier === "lit/static-html.js")
          return { errors: [{ text: "import staticHtml and its kin from lit" }] };
        return { path: "./lit.js", external: true };
      });
    },
  };
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

  const lit = JSON.parse(
    await readFile(path.join(root, "node_modules/lit/package.json"), "utf8"),
  );
  const entryPoints = { "browser-runtime": entry, lit: "leaf:lit" };
  const result = await build({
    absWorkingDir: root,
    entryPoints,
    outdir: outputRoot,
    plugins: [litModule(lit)],
    tsconfig: "scripts/browser/tsconfig.json",
    platform: "browser",
    format: "esm",
    target: "es2022",
    bundle: true,
    minify: true,
    sourcemap: "external",
    sourcesContent: true,
    legalComments: "eof",
    metafile: true,
    write: false,
    logLevel: "silent",
  });
  const module = result.metafile.outputs[modulePath];
  const built = new Map(
    result.outputFiles.map((file) => [relative(file.path), Buffer.from(file.contents)]),
  );
  const modules = new Set([...built.keys()].filter((name) => name.endsWith(".js")));
  const outputs = new Map();
  for (const name of [...modules].sort()) {
    const edges = result.metafile.outputs[name].imports.map((edge) =>
      edge.external ? path.posix.join(path.posix.dirname(name), edge.path) : edge.path,
    );
    if (edges.some((edge) => !modules.has(edge)))
      throw new Error(`${name} has unbundled imports`);
    checkModule(built.get(name).toString(), name, modules);
    outputs.set(name, built.get(name));
    // Each output's map sits at its own path under the diagnostics root.
    const mapPath = `${diagnosticsRoot}/${path.posix.relative(outputRoot, name)}.map`;
    const sourceMap = JSON.parse(built.get(`${name}.map`));
    sourceMap.sources = sourceMap.sources.map((source) =>
      path
        .relative(
          path.join(root, path.dirname(mapPath)),
          path.resolve(root, path.dirname(name), source),
        )
        .split(path.sep)
        .join("/"),
    );
    outputs.set(mapPath, Buffer.from(JSON.stringify(sourceMap)));
  }

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
      .filter(
        (name) => !name.startsWith("node_modules/") && !name.startsWith("leaf-lit:"),
      )
      .sort(),
    entryPoints: Object.fromEntries(
      Object.entries(entryPoints).map(([name, input]) => [
        `${outputRoot}/${name}.js`,
        input,
      ]),
    ),
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
    litModule: "/vendor/lit.js",
    litExports: result.metafile.outputs[litPath].exports,
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
    for (const [name, bytes] of outputs) {
      const destination = path.join(root, name);
      await mkdir(path.dirname(destination), { recursive: true });
      await writeFile(destination, bytes);
    }
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
