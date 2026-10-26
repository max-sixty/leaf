import assert from "node:assert/strict";
import test from "node:test";
import {
  sameStateDefinition,
  stampedState,
} from "../../browser/runtime/registry-contract.js";
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
  decides: false,
  detail: { type: "object" },
};

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
