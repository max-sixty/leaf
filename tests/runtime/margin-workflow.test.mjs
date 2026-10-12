import assert from "node:assert/strict";
import test from "node:test";
import {
  contributionControl,
  contributionEntry,
  contributionHost,
  contributionReceipts,
  presentContributionHost,
  syncContributionAgentWorkflow,
  syncContributionTurn,
} from "../../skills/leaf/assets/runtime/contribution-controls.js";
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

test("template contribution hosts paint the retained-host contract and are found on their surface", async () => {
  const { html, render } = await import("/vendor/browser-runtime.js");
  const root = document.createElement("section");
  document.body.append(root);
  const imperative = document.createElement("button");
  const source = {};
  const paint = (record, options, receipt, awaitsUser) =>
    render(
      html`<button
        ${contributionHost(source, "map", record, options)}
        ${contributionReceipts(receipt, awaitsUser)}
      ></button>`,
      root,
    );
  for (const [record, receipt, awaitsUser] of [
    [
      contributionEntry({
        key: "apply",
        icon: "check",
        label: "Apply",
        behavior: "disclosure",
        relation: { kind: "entries", keys: ["detail"], expanded: true },
      }),
      workflow("picked_up"),
      true,
    ],
    [
      contributionEntry({
        key: "apply",
        icon: "check",
        label: "Applied",
        disabled: true,
      }),
      null,
      false,
    ],
  ]) {
    const options = {
      accessibleLabel: record.label,
      relatedControlIds: ["detail-host"],
    };
    paint(record, options, receipt, awaitsUser);
    presentContributionHost(imperative, record, options);
    syncContributionAgentWorkflow(imperative, receipt);
    syncContributionTurn(imperative, awaitsUser);
    const control = root.querySelector("button");
    assert.equal(control.outerHTML, imperative.outerHTML);
    assert.equal(contributionControl(source, "apply", "map"), control);
  }
  root.remove();
});
