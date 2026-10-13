import assert from "node:assert/strict";
import test from "node:test";
import {
  sameStateDefinition,
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

test("a verb's stamped state answers only the event its writer sends", () => {
  const states = { choose: { writer: "user", definition: current } };
  const event = { widget: "options", action: "choose" };
  assert.equal(stampedState(states, { ...event, kind: "action" })?.definition, current);
  assert.equal(stampedState(states, { ...event, kind: "report" }), null);
  assert.equal(stampedState({}, { ...event, kind: "action" }), null);
});
