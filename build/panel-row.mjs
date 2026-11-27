/** The floating panel's row as a served document stands it from its first paint,
 * before the runtime's modules have loaded (`runtime/panel-row.html`, which the
 * bootstrap stands after `body` and the panel takes over as it mounts).
 *
 * The row is the panel's own first drawing (`panelTemplate`, `initial`, in
 * panel/floating-panel.js), drawn here by the panel's module in the document the runtime's
 * Node tests run in (`tests/runtime/dom.mjs`), so the panel has one drawing of its row
 * and the served copy is its projection. An edit to the row, or to the faces and
 * symbols its controls wear, takes `pnpm run build:browser` to reach the first paint,
 * and `pnpm run check:browser` fails until it has. The copy keeps the drawing's
 * classes, attributes and words, and drops Lit's markers, which name nothing outside
 * the render that made them, and the template's indentation. Its root is a `div` rather than the panel's element,
 * which the runtime defines and would otherwise upgrade before the panel takes the row
 * over. `build/browser/build.mjs` writes and checks it with its other outputs. */
import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const self = fileURLToPath(import.meta.url);

export async function panelRowOutputs() {
  const drawn = execFileSync(
    process.execPath,
    ["--import", "./tests/runtime/dom.mjs", self, "--draw"],
    { cwd: root },
  );
  return new Map([["browser/runtime/panel-row.html", drawn]]);
}

// Run under the tests' document: the panel's first drawing, before it mounts.
if (process.argv[1] === self && process.argv[2] === "--draw") {
  // The document the tests' world registers on the global object.
  const { document, NodeFilter } = globalThis;
  const { createFloatingPanel } = await import(
    new URL("../browser/runtime/panel/floating-panel.js", import.meta.url).href
  );
  const unused = () => {
    throw new Error("The panel's first drawing reads none of its owners");
  };
  const { host } = createFloatingPanel(
    /** @type {any} */ (
      new Proxy(
        {},
        {
          get: () => unused,
        },
      )
    ),
  );
  /** @param {number} show */
  const nodesOf = (show) => {
    const walker = document.createTreeWalker(host, show);
    const found = [];
    while (walker.nextNode()) found.push(walker.currentNode);
    return found;
  };
  for (const comment of nodesOf(NodeFilter.SHOW_COMMENT)) comment.remove();
  host.normalize();
  // The template's indentation, which the row draws as one space or none wherever it
  // stands, so a reformatted panel/floating-panel.js draws the same row.
  for (const text of nodesOf(NodeFilter.SHOW_TEXT))
    if (/^\s*\n\s*$/.test(text.data)) text.data = "\n";
  const row = document.createElement("div");
  for (const { name, value } of host.attributes) row.setAttribute(name, value);
  row.append(...host.childNodes);
  process.stdout.write(`${row.outerHTML}\n`);
}
