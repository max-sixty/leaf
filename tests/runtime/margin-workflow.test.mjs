import assert from "node:assert/strict";
import test from "node:test";
import { syncContributionAgentWorkflow } from "../../skills/leaf/assets/runtime/contribution-controls.js";
import { servedWorkflow } from "../served.mjs";

const workflow = (stage, condition = null) =>
  servedWorkflow({
    id: `${stage}-workflow`,
    stage,
    condition,
    detail: "Preparing an update",
  });

test("margin workflow paint distinguishes live work from conditioned history", () => {
  const control = document.createElement("button");

  syncContributionAgentWorkflow(control, workflow("working"));
  assert.equal(control.getAttribute("data-lf-agent-workflow"), "working");

  syncContributionAgentWorkflow(
    control,
    workflow("working", { kind: "stale", operation: "work" }),
  );
  assert.equal(control.hasAttribute("data-lf-agent-workflow"), false);

  syncContributionAgentWorkflow(
    control,
    workflow("picked_up", { kind: "ended", operation: "work" }),
  );
  assert.equal(control.hasAttribute("data-lf-agent-workflow"), false);
});
