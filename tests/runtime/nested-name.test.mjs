/* What a playground refuses in a name it draws inside a control (`nestedIn`,
   playground-view.js), held to what page check refuses in a view's header
   (`validation/instances.py`, `nested_in`) by the cases both answer. */

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { NESTED, nestedIn } from "../../packages/playground/widgets/playground-view.js";

const { cases } = JSON.parse(
  readFileSync(new URL("../nested_name_cases.json", import.meta.url), "utf8"),
);

for (const { id, markup, nests } of cases)
  test(`nested: ${id}`, () => {
    document.body.innerHTML = `<main>${markup}</main>`;
    assert.deepEqual(
      nestedIn(/** @type {Element} */ (document.getElementById("it"))),
      nests,
    );
  });

test("the playground's list is the tags the cases name", () => {
  const named = new Set(cases.flatMap(({ nests }) => nests));
  assert.deepEqual(
    new Set(NESTED),
    new Set([...named].filter((tag) => !tag.startsWith("lf-"))),
  );
});
