import assert from "node:assert/strict";
import test from "node:test";
import {
  contributionControl,
  contributionEntry,
  contributionHost,
  contributionReceipts,
  presentContributionHost,
  presentContributionReceipts,
} from "../../browser/runtime/contribution-controls.js";
import { servedWorkflow } from "../served.mjs";

// Where a workflow stands (`standing.py`), with the line the agent last wrote on it.
const RUNNING = { state: "running" };
const REPLYING = { state: "running", reason: "replying" };
const DELIVERED = { state: "waiting", seen: true };
const workflow = (standing) =>
  servedWorkflow({
    id: `${standing.state}-${standing.reason}-${standing.seen}-workflow`,
    ...standing,
    detail: "Preparing an update",
  });

test("margin workflow paint distinguishes live work from blocked work", () => {
  const control = document.createElement("button");

  presentContributionReceipts(control, workflow(RUNNING), false);
  assert.equal(control.getAttribute("data-lf-agent-workflow"), "working");

  presentContributionReceipts(
    control,
    workflow({ state: "blocked", reason: "quiet", seen: true }),
    false,
  );
  assert.equal(control.hasAttribute("data-lf-agent-workflow"), false);

  presentContributionReceipts(
    control,
    workflow({ state: "blocked", reason: "stopped", seen: true }),
    false,
  );
  assert.equal(control.hasAttribute("data-lf-agent-workflow"), false);
});

test("a reply streaming paints the working face under its own word", () => {
  // Threads says Replying for this receipt (`workflowWord`); the margin and Page Map
  // control carrying it says the same, under the face it shares with work.
  const control = document.createElement("button");
  presentContributionReceipts(control, workflow(REPLYING), false);
  assert.equal(control.getAttribute("data-lf-agent-workflow"), "working");
  assert.equal(
    control.getAttribute("aria-description"),
    "Replying · Preparing an update",
  );
  presentContributionReceipts(control, workflow(DELIVERED), false);
  assert.equal(control.getAttribute("data-lf-agent-workflow"), "delivered");
  assert.equal(
    control.getAttribute("aria-description"),
    "Delivered · Preparing an update",
  );
});

test("template contribution hosts paint the retained-host contract and are found on their surface", async () => {
  const { html, render } = await import("/runtime/framework.js");
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
      workflow(DELIVERED),
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
    presentContributionReceipts(imperative, receipt, awaitsUser);
    const control = root.querySelector("button");
    assert.equal(control.outerHTML, imperative.outerHTML);
    assert.equal(contributionControl(source, "apply", "map"), control);
  }
  root.remove();
});

test("a refused widget move without a projection coordinate does not break the annotation inventory", async () => {
  const { applicationState } = await import("/runtime/semantic-state.js");
  const { createAnnotationInventory } =
    await import("/runtime/annotation-inventory.js");
  applicationState.identify(1);
  const attempt = "margin-unprojected-move";
  applicationState.enqueue(
    {
      kind: "action",
      attempt,
      revision: 1,
      widget: "unprojected-widget",
      unit: "unprojected-widget",
      action: "move",
      detail: {},
    },
    "2026-10-31T12:00:00Z",
  );
  applicationState.refuse(attempt);
  const pending = applicationState
    .read()
    .effective.workflows.find((item) => item.id === `rejected:${attempt}`);
  assert.equal(pending.coordinate, null);
  const inventory = createAnnotationInventory({
    readObligations: () => ({ all: [], user: [] }),
    placedAt: () => undefined,
    openThread: () => {},
    goToObligation: () => {},
    scrollToElement: () => {},
  });
  try {
    assert.doesNotThrow(() => inventory.collect());
  } finally {
    applicationState.release(new Set([attempt]));
  }
});
