import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import {
  stateDefinition,
  sameStateDefinition,
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
