#!/usr/bin/env node
/**
 * Build Leaf's committed browser framework from locked contributor dependencies.
 * Invoke through pnpm run build:browser or check:browser; pnpm verifies that the
 * installed dependencies match the manifest and lock before either script runs.
 *
 * Run with --check to compare a fresh, typechecked build with committed bytes
 * without writing them. This module owns its source root, outputs, and their layer
 * paths, and writes and checks every other committed Node-built output beside them:
 * the initial renderers (`build/initial.mjs`), the stylesheets (`build/styles.mjs`),
 * the modules generated from the registry (`build/registry.mjs`), the kernel
 * event contract and the protocol baseline `protocol.test.ts` holds it to
 * (`event-types.mjs`), and the third-party bundles (`build/vendor.mjs`). The layer's `vendor/` and each package's
 * hold nothing else, so a file there that no build writes is stale. Leaf
 * installation, vendoring, activation, and export never invoke this tool.
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
 * The framework's third-party packages are minified builds from the lock and the
 * adaptations below. `vendor/lit.js` is the page's one copy of Lit (`build/lit.mjs`);
 * the framework imports Lit from it, as Web Awesome's bundle does. Signals are the
 * framework's own and sit inside its directory. `shipped.mjs` decides whether each
 * output's imports resolve on every page and writes the notices for the packages
 * that reached them, as it does for every vendored bundle.
 */
import { readFile, readdir, mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { parse } from "acorn";
import { transformSync } from "amaro";
import { build } from "esbuild";
import { eventTypes } from "./event-types.mjs";
import { initialOutputs } from "../initial.mjs";
import { litNamespace, litPath } from "../lit.mjs";
import { registryOutputs } from "../registry.mjs";
import { styleOutputs } from "../styles.mjs";
import { adapt, seam, vendorOutputs } from "../vendor.mjs";
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
  lit: litPath,
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
  const trailer = `// Generated from ${source} by build/browser/build.mjs.\n`;
  return {
    code: code.endsWith("\n") ? code + trailer : `${code}\n${trailer}`,
    imports,
  };
}

/**
 * Build `lit.js` (`build/lit.mjs`), adapting the locked published modules in memory.
 *
 * Backport lit/lit#5218 while 3.3.0 avoids the repeat marker leak (#5298). Route
 * keyed and child-part insertions through `runtime/dom-move.js`, which keeps the
 * user's place and native state across the move.
 */
async function litModule() {
  const contents = await litNamespace();
  const move = 'import {move as leafMove} from "/runtime/dom-move.js";\n';
  return [
    {
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
    },
    adapt([
      {
        file: /[/\\]lit-html[/\\]directives[/\\]ref\.js$/,
        edit: (source) =>
          seam(
            seam(
              source,
              "e&&void 0!==this.G&&this.rt(void 0)",
              "e&&this.rt(void 0)",
              "Lit ref",
            ),
            "rt(t){if(this.isConnected",
            "rt(t){if(void 0===this.G)return;if(this.isConnected",
            "Lit ref",
          ),
      },
      {
        file: /[/\\]lit-html[/\\]lit-html\.js$/,
        edit: (source) =>
          move +
          seam(
            source,
            "this._$AA.parentNode.insertBefore(t,this._$AB)",
            "leafMove(this._$AA.parentNode,t,this._$AB)",
            "Lit move",
          ),
      },
      {
        file: /[/\\]lit-html[/\\]directive-helpers\.js$/,
        edit: (source) =>
          move + seam(source, "e.insertBefore(o,l)", "leafMove(e,o,l)", "Lit move"),
      },
    ]),
  ];
}

// The event contract as it last stood at the current page protocol, which
// `protocol.test.ts` holds every later contract at that protocol to taking. A build
// whose typecheck passes moves it forward to the contract it built; a new protocol
// starts it again (`layer-registry.md`, "Page protocol").
const protocolContractPath = path.join(root, sourceRoot, "protocol-contract.d.ts");

async function protocolContract(contract) {
  const registry = JSON.parse(
    await readFile(path.join(root, assets, "registry.json"), "utf8"),
  );
  const protocol = registry.$events.protocol;
  const header = `// The event contract pages vendored at protocol ${protocol} speak, as it last stood (protocol.test.ts).`;
  return { header, text: `${header}\n${contract.slice(contract.indexOf("\n") + 1)}` };
}

async function protocolHeader() {
  try {
    const text = await readFile(protocolContractPath, "utf8");
    return text.slice(0, text.indexOf("\n"));
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    return null;
  }
}

export async function buildOutputs() {
  const contractPath = path.join(root, sourceRoot, "event-contract.d.ts");
  const contract = await eventTypes(new URL("../../", import.meta.url));
  if ((await readFile(contractPath, "utf8")) !== contract)
    throw new Error("Stale kernel event types; run pnpm run build:browser");
  if ((await protocolHeader()) !== (await protocolContract(contract)).header)
    throw new Error("Stale protocol contract; run pnpm run build:browser");
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

  const result = await build({
    absWorkingDir: root,
    entryPoints: Object.fromEntries(
      Object.entries(packages).map(([name, layerPath]) => [
        layerPath.slice("vendor/".length, -".js".length),
        name === "lit" ? "leaf:lit" : name,
      ]),
    ),
    outdir: `${assets}/vendor`,
    plugins: await litModule(),
    external: ["/runtime/dom-move.js"],
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
    if (
      result.metafile.outputs[name].imports.some(
        ({ path }) => path !== "/runtime/dom-move.js",
      )
    )
      throw new Error(`${name} imports another module`);
    checkModule(file.text, name);
    outputs.set(name, Buffer.from(file.contents));
  }
  const packageRoots = bundledPackages(result.metafile, root);
  outputs.set(
    `${assets}/vendor/browser-runtime.LICENSES.txt`,
    Buffer.from(licenseNotices("browser-runtime", packageRoots)),
  );
  for (const producer of [initialOutputs, styleOutputs, registryOutputs, vendorOutputs])
    for (const [name, bytes] of await producer()) outputs.set(name, bytes);
  return outputs;
}

const missing = (error) => {
  if (error.code !== "ENOENT") throw error;
  return [];
};

/**
 * The directories this build owns whole: the layer's `vendor/` and each package's.
 * Every file in them is an output, so one the build no longer writes is stale.
 */
async function vendorDirectories(directory) {
  const packages = "skills/leaf/packages";
  return [
    `${assets}/vendor`,
    ...(
      await readdir(path.join(directory, packages), { withFileTypes: true }).catch(
        missing,
      )
    )
      .filter((entry) => entry.isDirectory())
      .map(({ name }) => `${packages}/${name}/vendor`),
  ];
}

export async function checkOutputs(outputs, directory = root) {
  const stale = [];
  for (const owned of await vendorDirectories(directory))
    for (const file of await readdir(path.join(directory, owned), {
      recursive: true,
      withFileTypes: true,
    }).catch(missing))
      if (file.isFile()) {
        const name = path
          .relative(directory, path.join(file.parentPath, file.name))
          .split(path.sep)
          .join("/");
        if (!outputs.has(name)) stale.push(name);
      }
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
      `Stale browser output; run pnpm run build:browser:\n${stale.join("\n")}`,
    );
}

async function main(args) {
  if (args.length === 1 && args[0] === "--help") {
    console.log(
      "Usage: node build/browser/build.mjs [--check]\n\nBuild committed browser ESM, or check it without writing. Run pnpm install --frozen-lockfile first.",
    );
    return;
  }
  if (args.length > 1 || (args.length && args[0] !== "--check")) {
    throw new Error("Usage: node build/browser/build.mjs [--check]");
  }
  const contract = await eventTypes(new URL("../../", import.meta.url));
  const protocol = await protocolContract(contract);
  if (args[0] !== "--check") {
    await writeFile(path.join(root, sourceRoot, "event-contract.d.ts"), contract);
    if ((await protocolHeader()) !== protocol.header)
      await writeFile(protocolContractPath, protocol.text);
  }
  const outputs = await buildOutputs();
  if (args[0] !== "--check") await writeFile(protocolContractPath, protocol.text);
  if (args[0] === "--check") await checkOutputs(outputs);
  else {
    for (const owned of await vendorDirectories(root))
      await rm(path.join(root, owned), { force: true, recursive: true });
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
