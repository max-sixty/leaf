import assert from "node:assert/strict";
import test from "node:test";
import {
  sameStateDefinition,
  sameStateOperation,
  stampedState,
} from "../../skills/leaf/assets/runtime/registry-contract.js";
import { servedStateDefinitions } from "../served.mjs";

for (const entry of servedStateDefinitions())
  test(`state definition: ${entry.id}`, () => {
    assert.equal(sameStateDefinition(...entry.definitions), entry.same);
  });

const current = {
  origin: "lf-options",
  unit: "widget",
  record: { kind: "attribute", attr: "chosen" },
  creates: null,
  detail: { type: "object" },
};

test("an operation an earlier Leaf recorded with another field still matches", () => {
  // Before #2329 the recorded definition carried `update`, since renamed `report`
  // and then dropped as a restatement of `detail`.
  assert.ok(sameStateOperation({ ...current, update: false }, current));
  const { creates: _creates, ...missing } = current;
  assert.ok(!sameStateOperation(missing, current));
  assert.ok(!sameStateOperation({ ...current, unit: "option" }, current));
});

test("a verb's stamped state answers only the event its writer sends", () => {
  const registry = {
    $states: { "lf-options": { choose: { writer: "user", definition: current } } },
  };
  const event = { widget: "options", action: "choose" };
  assert.equal(
    stampedState(registry, "lf-options", { ...event, kind: "action" })?.definition,
    current,
  );
  assert.equal(
    stampedState(registry, "lf-options", { ...event, kind: "report" }),
    null,
  );
  assert.equal(stampedState(registry, "lf-other", { ...event, kind: "action" }), null);
});
