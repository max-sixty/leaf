#!/usr/bin/env node
/**
 * What every third-party bundle Leaf commits must be, and what it must carry.
 *
 * Both builders consume this module: `build.mjs` for the browser framework and Lit,
 * `scripts/vendor.py` for every other bundle, including the files it copies as
 * published. So one parser decides whether an output runs under the page CSP, and one
 * writer states the licenses of the packages that reached it.
 *
 * The interactive export's CSP admits neither runtime compilation nor a module it did
 * not embed, and both are one careless import away: d3 carries a `new Function` in
 * d3-dsv's CSV parser, and a bundler splits a chunk out behind every `import()`. A
 * bundle that breaks either rule draws in a developer's served page, whose policy
 * allows eval for the test drivers, and refuses in a user's export. So the check reads
 * the parsed module rather than its text: a grammar that carries `import(` as data,
 * as Pierre's TextMate grammars do, is ordinary.
 *
 * A static import may name only a local path. Whether its target exists is a fact of
 * the served layout rather than of the bundle, and capturing a revision refuses a
 * missing one (`revision_artifact.captured_imports`).
 *
 * Run as `node scripts/browser/shipped.mjs METAFILE NOTICES [MODULE...]` from the
 * build's working directory: it refuses the first module the page CSP forbids, then
 * writes NOTICES from the packages METAFILE (esbuild's) says reached the bundle.
 */
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "acorn";

const COMPILERS = new Set(["eval", "Function", "require"]);
// A timer given a string compiles it, as eval does; given a function, it does not.
const TIMERS = new Set(["setTimeout", "setInterval"]);
const GLOBALS = new Set(["globalThis", "window", "self"]);
const LOCAL = /^(?:\/(?!\/)|\.{1,2}\/)/;

/** Whether an expression is a string the source states: literal, template, or sum. */
function isString(node) {
  if (!node) return false;
  if (node.type === "Literal") return typeof node.value === "string";
  if (node.type === "TemplateLiteral") return true;
  return (
    node.type === "BinaryExpression" &&
    node.operator === "+" &&
    (isString(node.left) || isString(node.right))
  );
}

/** The function a call reaches by name, through `(0, eval)` or `globalThis.eval`. */
function calleeName(node) {
  if (node.type === "SequenceExpression") return calleeName(node.expressions.at(-1));
  if (node.type === "Identifier") return node.name;
  if (
    node.type === "MemberExpression" &&
    node.object.type === "Identifier" &&
    GLOBALS.has(node.object.name)
  )
    return node.computed ? node.property.value : node.property.name;
  return undefined;
}

/** Refuse a module that compiles code at run time or imports what no page serves. */
export function checkModule(source, name = "<module>") {
  const parsed = parse(source, {
    ecmaVersion: "latest",
    sourceType: "module",
    locations: true,
  });
  const refuse = (node, reason) => {
    throw new Error(
      `${name}:${node.loc.start.line}: ${reason}, which the page CSP forbids`,
    );
  };
  function visit(node) {
    if (!node || typeof node !== "object") return;
    if (node.type === "ImportExpression")
      refuse(node, "import() loads a module at run time");
    if (
      ["ImportDeclaration", "ExportNamedDeclaration", "ExportAllDeclaration"].includes(
        node.type,
      ) &&
      node.source &&
      !LOCAL.test(node.source.value)
    )
      refuse(node, `it imports ${JSON.stringify(node.source.value)}, not a local path`);
    if (["CallExpression", "NewExpression"].includes(node.type)) {
      const callee = calleeName(node.callee);
      if (COMPILERS.has(callee)) refuse(node, `it calls ${callee}`);
      if (TIMERS.has(callee) && isString(node.arguments[0]))
        refuse(node, `it passes ${callee} a string to compile`);
    }
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach(visit);
      else visit(value);
    }
  }
  visit(parsed);
}

/**
 * Each package directory whose code an esbuild metafile says reached an output.
 *
 * The metafile's top-level `inputs` also lists every file the bundler read and then
 * shook out entirely, such as the HTML, CSS, and JavaScript grammars CodeMirror's
 * Markdown package imports; an output's own `inputs` with bytes in it does not.
 */
export function bundledPackages(metafile, cwd) {
  const roots = new Set();
  const reached = Object.values(metafile.outputs).flatMap((output) =>
    Object.entries(output.inputs)
      .filter(([, input]) => input.bytesInOutput > 0)
      .map(([name]) => name),
  );
  for (const input of reached) {
    const at = input.lastIndexOf("node_modules/");
    if (at === -1) continue;
    const parts = input.slice(at).split("/");
    const name = parts.slice(0, parts[1].startsWith("@") ? 3 : 2);
    roots.add(path.resolve(cwd, input.slice(0, at), ...name));
  }
  return [...roots].sort();
}

const LICENSE = /^(?:licen[cs]e|copying)(?:[.-]|$)/i;
const NOTICE = /^(?:notice|third[-_]party[-_]notices)(?:\.|$)/i;

/**
 * The license text of each package, and every other notice it ships to be passed on.
 *
 * A package's license file comes first under its name, version, and declared license.
 * Further documents follow under their path: a second license file, an Apache NOTICE,
 * and a renderer's own `THIRD_PARTY_NOTICES` with the texts it keeps in `LICENSES/`.
 */
export function licenseNotices(title, packageRoots) {
  const sections = packageRoots.map((root) => {
    const manifest = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));
    const files = readdirSync(root)
      .filter((file) => statSync(path.join(root, file)).isFile())
      .sort();
    const [license, ...licenses] = files.filter((file) => LICENSE.test(file));
    if (license === undefined)
      throw new Error(`no license file shipped by ${manifest.name}`);
    const bundled = path.join(root, "LICENSES");
    const documents = [
      ...licenses,
      ...files.filter((file) => NOTICE.test(file)),
      ...(statSync(bundled, { throwIfNoEntry: false })?.isDirectory()
        ? readdirSync(bundled)
            .sort()
            .map((file) => `LICENSES/${file}`)
        : []),
    ];
    const text = (file) => readFileSync(path.join(root, file), "utf8").trim();
    return [
      `===== ${manifest.name} ${manifest.version} (${manifest.license}) =====\n${text(license)}`,
      ...documents.map(
        (file) => `===== ${manifest.name}: ${file} =====\n${text(file)}`,
      ),
    ].join("\n\n");
  });
  return `Third-party licenses for ${title}\n\n${sections.join("\n\n")}\n`;
}

function main([metafilePath, notices, ...modules]) {
  if (!metafilePath || !notices)
    throw new Error(
      "Usage: node scripts/browser/shipped.mjs METAFILE NOTICES [MODULE...]",
    );
  for (const module of modules) checkModule(readFileSync(module, "utf8"), module);
  const metafile = JSON.parse(readFileSync(metafilePath, "utf8"));
  writeFileSync(
    notices,
    licenseNotices(
      path.basename(notices, ".LICENSES.txt"),
      bundledPackages(metafile, process.cwd()),
    ),
  );
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
