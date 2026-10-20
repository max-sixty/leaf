/** The paint names hand-written code spells out stay the ones `$marks` declares.
 *
 * Runtime modules import the paint names from the generated `runtime/marks.js`, but a
 * stylesheet's attribute selector, the inline prepaint and a package's own module
 * (`references/package-themes.md`) can only spell a name out. So each mark's paint
 * must still be spelled somewhere, and no source may spell another `data-lf-` name
 * formed from a mark's key, which is what a renamed paint leaves behind. */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const root = fileURLToPath(new URL("../", import.meta.url));
const GENERATED = "skills/leaf/assets/runtime/marks.js";

test("hand-written sources spell each mark as `$marks` paints it", async () => {
  const registry = JSON.parse(
    await readFile(new URL("skills/leaf/assets/registry.json", `file://${root}`)),
  );
  const { description: _, ...marks } = registry.$marks;
  const sources = execFileSync(
    "git",
    ["ls-files", "skills/leaf/*.css", "skills/leaf/*.js", "skills/leaf/*.mjs"],
    { cwd: root, encoding: "utf8" },
  )
    .split("\n")
    .filter(
      (file) =>
        file &&
        file !== GENERATED &&
        !file.startsWith("skills/leaf/kernel/") &&
        !file.includes("/vendor/"),
    );
  const spelled = new Map();
  for (const file of sources) {
    const text = await readFile(`${root}${file}`, "utf8");
    for (const [name] of text.matchAll(/data-lf-[a-z]+(?:-[a-z]+)*/g))
      spelled.set(name, [...(spelled.get(name) ?? []), file]);
  }
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
