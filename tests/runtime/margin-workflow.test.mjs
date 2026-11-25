import assert from "node:assert/strict";
import test from "node:test";
import {
  contributionControl,
  contributionEntry,
  contributionHost,
  contributionReceipts,
  presentContributionEntry,
  presentContributionHost,
  presentContributionReceipts,
} from "../../browser/runtime/features/contribution-controls.js";
import { servedState, servedWorkflow } from "../served.mjs";

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

test("an entry draws the receipts it is given and keeps those a seat painted", () => {
  const control = document.createElement("button");
  const entry = { key: "apply", icon: "check", label: "Apply" };
  presentContributionEntry(control, entry, {
    receipt: workflow(RUNNING),
    awaitsUser: true,
  });
  assert.equal(control.getAttribute("data-lf-agent-workflow"), "working");
  assert.equal(control.getAttribute("data-lf-turn"), "user");
  // A seat that paints the receipts on every pass redraws the entry without them
  // (`materializeContributionControls`).
  presentContributionEntry(control, entry);
  assert.equal(control.getAttribute("data-lf-agent-workflow"), "working");
  assert.equal(control.getAttribute("data-lf-turn"), "user");
  presentContributionEntry(control, entry, { receipt: null });
  assert.equal(control.hasAttribute("data-lf-agent-workflow"), false);
  assert.equal(control.getAttribute("data-lf-turn"), "user");
  presentContributionEntry(control, entry, { awaitsUser: false });
  assert.equal(control.hasAttribute("data-lf-turn"), false);
});

test("template contribution hosts paint the retained-host contract and are found on their surface", async () => {
  const { html, render } = await import("/vendor/lit.js");
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
  const { applicationState } = await import("/runtime/state/semantic-state.js");
  const { createAnnotationInventory } =
    await import("/runtime/features/annotation-inventory.js");
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

// The Margin and Page Map draw a claim's carriers apart and join its one arrival: a
// carrier drawn partway through takes the pulse from there, and one drawn after it
// ends takes none. Once no published workflow holds the claim, a claim that comes back
// arrives anew, on the carrier that drew it before too.
test("a claim's carriers share one arrival while a published workflow holds it", async (t) => {
  const { applicationState } = await import("/runtime/state/semantic-state.js");
  document.documentElement.style.setProperty("--lf-motion-agent-arrival", "1000ms");
  let now = 0;
  t.mock.method(performance, "now", () => now);
  const claimed = servedWorkflow({
    id: "claimed-workflow",
    state: "running",
    seen: true,
  });
  let taken = 0;
  const publish = (workflows) =>
    assert.equal(
      applicationState.adopt(servedState({ taken: ++taken, workflows })),
      true,
    );
  // The delay a carrier's pulse starts at as it draws `receipt`, or null for none.
  const carry = (control, receipt = claimed) => {
    presentContributionReceipts(control, receipt, false);
    return control.hasAttribute("data-lf-agent-arrival")
      ? control.style.getPropertyValue("--lf-agent-arrival-delay")
      : null;
  };
  const carrier = () => document.createElement("button");
  const margin = carrier();
  applicationState.identify(1);
  publish([claimed]);
  assert.equal(carry(margin), "0ms");
  now = 400;
  assert.equal(carry(carrier()), "-400ms");
  now = 1400;
  assert.equal(carry(carrier()), null);

  // The update settles, and its carrier draws it without the claim.
  publish([]);
  assert.equal(carry(margin, null), null);
  now = 2000;
  publish([claimed]);
  assert.equal(carry(margin), "0ms");
});
