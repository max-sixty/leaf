/**
 * What every third-party bundle Leaf commits must be, and what it must carry.
 *
 * Every bundle passes through this module: `build.mjs`'s browser framework and Lit,
 * and each of `build/vendor.mjs`'s, including the files it copies as published. So
 * one parser decides whether an output loads in an export, and one writer states the
 * licenses of the packages that reached it.
 *
 * An export loads only the modules it embeds, and a module it cannot embed is one
 * careless import away: a bundler splits a chunk out behind every `import()`, and a
 * CommonJS dependency left unbundled reaches for `require`. A bundle that does either
 * draws in a developer's served page, which serves every module, and fails in a user's
 * export. So the check reads the parsed module rather than its text: a grammar that
 * carries `import(` as data, as Pierre's TextMate grammars do, is ordinary.
 *
 * A static import may name only a local path. Whether its target exists is a fact of
 * the served layout rather than of the bundle, and capturing a revision refuses a
 * missing one (`revision_artifact.captured_imports`).
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { parse } from "acorn";

const LOCAL = /^(?:\/(?!\/)|\.{1,2}\/)/;

/** Refuse a module that loads another at run time or imports what no page serves. */
export function checkModule(source, name = "<module>") {
  const parsed = parse(source, {
    ecmaVersion: "latest",
    sourceType: "module",
    locations: true,
  });
  const refuse = (node, reason) => {
    throw new Error(
      `${name}:${node.loc.start.line}: ${reason}, which an export cannot load`,
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
    if (
      node.type === "CallExpression" &&
      node.callee.type === "Identifier" &&
      node.callee.name === "require"
    )
      refuse(node, "require() loads a module at run time");
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
 * Package sections sort by name and version, independent of installation paths.
 * Further documents follow under their path: a second license file, an Apache NOTICE,
 * and a renderer's own `THIRD_PARTY_NOTICES` with the texts it keeps in `LICENSES/`.
 */
export function licenseNotices(title, packageRoots) {
  const sections = packageRoots
    .map((root) => {
      const manifest = JSON.parse(
        readFileSync(path.join(root, "package.json"), "utf8"),
      );
      const files = readdirSync(root)
        .filter((file) => statSync(path.join(root, file)).isFile())
        .sort();
      const [license, ...licenses] = files.filter((file) => LICENSE.test(file));
      // The published scoped-registry package omits its upstream BSD license file.
      // Keep that dependency's source license as an explicit build input.
      const sourceLicense =
        manifest.name === "@webcomponents/scoped-custom-element-registry"
          ? new URL("../licenses/scoped-registry.LICENSE", import.meta.url)
          : null;
      if (license === undefined && sourceLicense === null)
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
      const text = (file) =>
        readFileSync(path.join(root, file), "utf8").replaceAll("\r\n", "\n").trim();
      return [
        `===== ${manifest.name} ${manifest.version} (${manifest.license}) =====\n${license === undefined ? readFileSync(sourceLicense, "utf8").trim() : text(license)}`,
        ...documents.map(
          (file) => `===== ${manifest.name}: ${file} =====\n${text(file)}`,
        ),
      ].join("\n\n");
    })
    .sort();
  return `Third-party licenses for ${title}\n\n${sections.join("\n\n")}\n`;
}
