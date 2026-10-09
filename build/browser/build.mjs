#!/usr/bin/env node
/**
 * Build Leaf's committed browser framework from locked contributor dependencies.
 *
 * Run with --check to compare a fresh, typechecked build with committed bytes
 * without writing them. This module owns its source root, outputs, and their layer
 * paths; Leaf installation, vendoring, activation, and export never invoke this tool.
 *
 * Each TypeScript module compiles to one JavaScript module, its types blanked to
 * whitespace, so every line keeps its source line number and two branches conflict
 * in the output exactly where they conflict in the source. `index.ts` becomes the
 * facade `vendor/browser-runtime.js`; the modules it reaches sit in
 * `vendor/browser-runtime/`. Their imports are rewritten to the layer paths a page
 * serves: runtime modules stay native, so a page holds one instance of each, and
 * packages bind to the vendored builds below. Delivery compiles the whole framework
 * into the kernel (`build/runtime-bundle.mjs`), so its file count costs a
 * development checkout requests and nothing else.
 *
 * The framework's third-party packages are minified builds, which change only when
 * the lock does. `vendor/lit.js` is the page's one copy of Lit: every public Lit
 * module in one namespace, shaped like Lit's own `lit-all` bundle, where the
 * static-html tags are renamed `staticHtml`, `staticSvg`, and `staticMathml` so they
 * do not shadow the ordinary ones. The framework imports Lit from it, and so does
 * the Web Awesome bundle (`build/webawesome/build.mjs`), so a page registers one
 * LitElement, one template cache, and one version. Signals are the framework's own
 * and sit inside its directory. `shipped.mjs` decides whether each output's imports
 * resolve on every page and writes the notices for the packages that reached them,
 * as it does for every bundle `build/vendor.py` makes.
 */
import { readFile, readdir, mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { parse } from "acorn";
import { transformSync } from "amaro";
import { build } from "esbuild";
import { initialOutputs } from "../initial.mjs";
import { bundledPackages, checkModule, licenseNotices } from "./shipped.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const assets = "skills/leaf/assets";
const sourceRoot = "build/browser";
const facade = "vendor/browser-runtime.js";
const frameworkDirectory = "vendor/browser-runtime";
/** The framework's layer paths: its facade and the directory of its modules. */
export const frameworkPaths = [facade, frameworkDirectory];
/** Whether a layer path belongs to the framework, which delivery compiles away. */
export const inFramework = (layerPath) =>
  layerPath === facade || layerPath.startsWith(`${frameworkDirectory}/`);
/** The layer path each package the framework imports is vendored at. */
const packages = {
  lit: "vendor/lit.js",
  "@preact/signals-core": `${frameworkDirectory}/signals-core.js`,
};

/** Each source module's layer path. */
const layerPathOf = (source) => {
  const name = path.posix.basename(source, ".ts");
  return name === "index" ? facade : `${frameworkDirectory}/${name}.js`;
};

/** The layer path an import in a framework source module names, and its source. */
function importTarget(specifier, source) {
  if (!/^\.{1,2}\//.test(specifier)) {
    // Its tags go by their lit-all names, which a bare rebinding would not reach.
    if (specifier === "lit/static-html.js")
      throw new Error(`${source}: import staticHtml and its kin from lit`);
    const name = specifier.startsWith("lit/") ? "lit" : specifier;
    if (!Object.hasOwn(packages, name))
      throw new Error(`${source}: ${specifier} is not a package the framework vendors`);
    return { target: packages[name] };
  }
  const resolved = path.posix.join(path.posix.dirname(source), specifier);
  if (path.posix.dirname(resolved) === sourceRoot) {
    const imported = resolved.replace(/\.js$/, ".ts");
    return { target: layerPathOf(imported), imported };
  }
  if (resolved.startsWith(`${assets}/`))
    return { target: resolved.slice(assets.length + 1) };
  throw new Error(`${source}: ${specifier} is outside the layer`);
}

/**
 * One source module as browser JavaScript, and the framework sources it imports.
 *
 * Types become whitespace; a line whose code ended in a type drops the spaces left
 * behind, and every other byte stays where the source has it.
 */
function compileModule(text, source) {
  const lines = text.split("\n");
  let code = transformSync(text, { mode: "strip-only" })
    .code.split("\n")
    .map((line, index) => (/\s$/.test(lines[index]) ? line : line.trimEnd()))
    .join("\n");
  const from = path.posix.dirname(layerPathOf(source));
  const imports = [];
  const sources = parse(code, { ecmaVersion: "latest", sourceType: "module" })
    .body.filter((node) => node.source)
    .map((node) => node.source);
  for (const node of sources.reverse()) {
    const { target, imported } = importTarget(node.value, source);
    if (imported) imports.push(imported);
    let edge = path.posix.relative(from, target);
    if (!edge.startsWith(".")) edge = `./${edge}`;
    code = code.slice(0, node.start) + JSON.stringify(edge) + code.slice(node.end);
  }
  const trailer = `// Generated from ${source} by npm run build:browser.\n`;
  return {
    code: code.endsWith("\n") ? code + trailer : `${code}\n${trailer}`,
    imports,
  };
}

/**
 * Build `lit.js` from Lit's published exports.
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
    },
  };
}

export async function buildOutputs() {
  const packageJson = JSON.parse(
    await readFile(path.join(root, "package.json"), "utf8"),
  );
  const lock = JSON.parse(await readFile(path.join(root, "package-lock.json")));
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
      `${sourceRoot}/tsconfig.json`,
    ],
    { cwd: root, encoding: "utf8" },
  );
  if (typecheck.error) throw typecheck.error;
  if (typecheck.status !== 0) throw new Error(typecheck.stdout + typecheck.stderr);

  const outputs = new Map();
  const pending = [`${sourceRoot}/index.ts`];
  while (pending.length) {
    const source = pending.pop();
    const name = `${assets}/${layerPathOf(source)}`;
    if (outputs.has(name)) continue;
    const { code, imports } = compileModule(
      await readFile(path.join(root, source), "utf8"),
      source,
    );
    checkModule(code, name);
    outputs.set(name, Buffer.from(code));
    pending.push(...imports);
  }

  const lit = JSON.parse(
    await readFile(path.join(root, "node_modules/lit/package.json"), "utf8"),
  );
  const result = await build({
    absWorkingDir: root,
    entryPoints: Object.fromEntries(
      Object.entries(packages).map(([name, layerPath]) => [
        layerPath.slice("vendor/".length, -".js".length),
        name === "lit" ? "leaf:lit" : name,
      ]),
    ),
    outdir: `${assets}/vendor`,
    plugins: [litModule(lit)],
    platform: "browser",
    format: "esm",
    target: "es2022",
    bundle: true,
    minify: true,
    legalComments: "eof",
    metafile: true,
    write: false,
    logLevel: "silent",
  });
  for (const file of result.outputFiles) {
    const name = path.relative(root, file.path).split(path.sep).join("/");
    if (result.metafile.outputs[name].imports.length)
      throw new Error(`${name} imports another module`);
    checkModule(file.text, name);
    outputs.set(name, Buffer.from(file.contents));
  }
  const packageRoots = bundledPackages(result.metafile, root);
  for (const packageRoot of packageRoots) {
    const pkg = JSON.parse(
      await readFile(path.join(packageRoot, "package.json"), "utf8"),
    );
    if (lock.packages[path.relative(root, packageRoot)].version !== pkg.version) {
      throw new Error(`${pkg.name} does not match package-lock.json; run npm ci`);
    }
  }
  outputs.set(
    `${assets}/vendor/browser-runtime.LICENSES.txt`,
    Buffer.from(licenseNotices("browser-runtime", packageRoots)),
  );
  for (const [name, bytes] of await initialOutputs()) outputs.set(name, bytes);
  return outputs;
}

export async function checkOutputs(outputs, directory = root) {
  // The framework's directory holds only what this build writes.
  const stale = (
    await readdir(path.join(directory, assets, frameworkDirectory), {
      recursive: true,
    }).catch((error) => {
      if (error.code !== "ENOENT") throw error;
      return [];
    })
  )
    .map((file) => `${assets}/${frameworkDirectory}/${file.split(path.sep).join("/")}`)
    .filter((name) => !outputs.has(name));
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
      "Usage: node build/browser/build.mjs [--check]\n\nBuild committed browser ESM, or check it without writing. Run npm ci first.",
    );
    return;
  }
  if (args.length > 1 || (args.length && args[0] !== "--check")) {
    throw new Error("Usage: node build/browser/build.mjs [--check]");
  }
  const outputs = await buildOutputs();
  if (args[0] === "--check") await checkOutputs(outputs);
  else {
    await rm(path.join(root, assets, frameworkDirectory), {
      force: true,
      recursive: true,
    });
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
