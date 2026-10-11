import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import {
  stateDefinition,
  sameStateDefinition,
  sameStateOperation,
} from "../../skills/leaf/assets/runtime/registry-contract.js";

const cases = JSON.parse(
  readFileSync(new URL("../state_definition_cases.json", import.meta.url)),
);
for (const entry of cases)
  test(`state definition: ${entry.id}`, () => {
    const definitions = [entry.before, entry.after].map((detail) =>
      stateDefinition("lf-local", {}, { unit: "widget", detail }),
    );
    assert.equal(sameStateDefinition(...definitions), entry.same);
  });

test("an operation an earlier Leaf recorded with another field still matches", () => {
  const spec = { unit: "widget", record: { kind: "attribute", attr: "chosen" } };
  const current = stateDefinition("lf-options", {}, spec);
  // Before #2329 the recorded definition carried `update`, since renamed `report`
  // and then dropped as a restatement of `detail`.
  assert.ok(sameStateOperation({ ...current, update: false }, current));
  const { creates: _creates, ...missing } = current;
  assert.ok(!sameStateOperation(missing, current));
  assert.ok(!sameStateOperation({ ...current, unit: "option" }, current));
});
