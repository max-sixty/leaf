/* The browser compares the state definitions the server serves as
   `registry.contract.same_state_definition` does, over the same cases
   (`tests/state_definition_cases.json`). */
import assert from "node:assert/strict";
import test from "node:test";
import { sameStateDefinition } from "../../skills/leaf/assets/runtime/registry-contract.js";
import { servedStateDefinitionCases } from "../served.mjs";

for (const { id, definitions, same } of servedStateDefinitionCases())
  test(`state definition: ${id}`, () => {
    assert.equal(sameStateDefinition(...definitions), same);
  });
