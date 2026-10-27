/** Names hand-written code spells out stay the ones the other runtime spells.
 *
 * Runtime modules read what they can from the kernel registry itself
 * (`runtime/kernel-facts.js`), but a stylesheet's selector, the inline prepaint, a
 * package's own module (`references/package-themes.md`), a render check's probe and
 * the markup Python writes can only spell a name out. Each test here holds those spellings to their other
 * side:
 *
 * - each `$marks` paint is still spelled somewhere, and no source spells another
 *   `data-lf-` name formed from a mark's key, which is what a renamed paint leaves
 *   behind;
 * - each `data-lf-` attribute Python writes into a page or reads off one is one the
 *   browser spells too, so renaming it on either side alone fails here. A name two
 *   browser sources read, such as the served script's `data-lf-layer`, still passes
 *   while one of them keeps it: the check knows names, not which reader needs one;
 * - each stylesheet selector on a page-wide allocation names a value `$authored`
 *   declares. The runtime's readers of those values are typed by the same table
 *   (`AuthoredAllocations`, build/browser/contract-types.mjs). */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = fileURLToPath(new URL("../", import.meta.url));
// The `data-lf-` names Python writes only for itself: the export's fallback style
// hides a page until its bootstrap replaces the document, and the inlined annotation
// sheet is named for the suite to find.
const PYTHON_ONLY = new Set(["data-lf-export-pending", "data-lf-annotation-theme"]);

const registry = JSON.parse(
  await readFile(new URL("browser/runtime/kernel-registry.json", `file://${root}`)),
);

const tracked = (...patterns) =>
  execFileSync("git", ["ls-files", ...patterns], { cwd: root, encoding: "utf8" })
    .split("\n")
    .filter(
      (file) => file && !file.startsWith("dist/kernel/") && !file.includes("/vendor/"),
    );
const python = tracked("src/*.py", "src/*.js");
const browser = tracked(
  "browser/*.css",
  "browser/*.js",
  "packages/*.css",
  "packages/*.js",
);

// Each `data-lf-` name the files spell, as markup or a selector writes it or as an
// element's `dataset` reads it, with the files that spell it.
async function spelledNames(files) {
  const spelled = new Map();
  const add = (name, file) => spelled.set(name, [...(spelled.get(name) ?? []), file]);
  for (const file of files) {
    const text = await readFile(`${root}${file}`, "utf8");
    for (const [name] of text.matchAll(/data-lf-[a-z0-9]+(?:-[a-z0-9]+)*/g))
      add(name, file);
    for (const [, key] of text.matchAll(/\bdataset\??\.(lf[A-Z][A-Za-z0-9]*)/g))
      add(
        `data-${key.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`,
        file,
      );
  }
  return spelled;
}

test("hand-written sources spell each mark as `$marks` paints it", async () => {
  const { description: _, ...marks } = registry.$marks;
  const spelled = await spelledNames([...python, ...browser]);
  for (const [key, { paint }] of Object.entries(marks)) {
    assert.ok(spelled.has(paint), `no stylesheet or module spells ${key}'s ${paint}`);
    const stale = `data-lf-${key.slice("x-".length)}`;
    if (stale !== paint)
      assert.ok(
        !spelled.has(stale),
        `${spelled.get(stale)} spell ${stale}, but $marks paints ${key} as ${paint}`,
      );
  }
});

test("the browser spells each `data-lf-` attribute Python spells", async () => {
  const browserNames = await spelledNames(browser);
  const unread = [...(await spelledNames(python))].filter(
    ([name]) => !browserNames.has(name) && !PYTHON_ONLY.has(name),
  );
  assert.deepEqual(
    unread.map(([name, files]) => `${name} (${[...new Set(files)].join(", ")})`),
    [],
    "no browser source spells these",
  );
  for (const name of PYTHON_ONLY)
    assert.ok(!browserNames.has(name), `the browser reads ${name}; drop it here`);
});

test("stylesheets select only the allocation values `$authored` declares", async () => {
  const { allocations } = registry.$authored;
  const sheets = browser.filter((file) => file.endsWith(".css"));
  const selected = [];
  for (const file of sheets) {
    const text = await readFile(`${root}${file}`, "utf8");
    for (const [attr, values] of Object.entries(allocations))
      for (const [, value] of text.matchAll(
        new RegExp(`\\[${attr}\\s*[~|^$*]?=\\s*"?([^"\\]]*)"?\\s*\\]`, "g"),
      )) {
        selected.push(attr);
        assert.ok(
          values.includes(value),
          `${file} selects ${attr}="${value}", which $authored doesn't declare`,
        );
      }
  }
  assert.ok(selected.length, "no stylesheet selects a page-wide allocation");
});
