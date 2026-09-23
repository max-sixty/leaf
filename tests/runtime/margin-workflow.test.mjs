import assert from "node:assert/strict";
import test from "node:test";
import { syncMarginAgentWorkflow } from "../../skills/leaf/assets/runtime/margin-entries.js";

const workflow = (stage, condition = null) => ({
  id: `${stage}-workflow`,
  subject: { kind: "conversation", id: "thread-1" },
  stage,
  condition,
  detail: "Preparing an update",
});

test("margin workflow paint distinguishes live work from conditioned history", () => {
  const control = document.createElement("button");

  syncMarginAgentWorkflow(control, workflow("working"));
  assert.equal(control.getAttribute("data-lf-agent-workflow"), "working");

  syncMarginAgentWorkflow(
    control,
    workflow("working", { kind: "stale", operation: "work" }),
  );
  assert.equal(control.hasAttribute("data-lf-agent-workflow"), false);

  syncMarginAgentWorkflow(
    control,
    workflow("picked_up", { kind: "ended", operation: "work" }),
  );
  assert.equal(control.hasAttribute("data-lf-agent-workflow"), false);
});
