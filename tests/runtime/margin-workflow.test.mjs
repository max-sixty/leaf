import assert from "node:assert/strict";
import test from "node:test";
import {
  contributionControl,
  contributionEntry,
  trackContributionControl,
  presentContributionHost,
  presentContributionReceipts,
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

  presentContributionReceipts(control, workflow("working"), false);
  assert.equal(control.getAttribute("data-lf-agent-workflow"), "working");

  presentContributionReceipts(
    control,
    workflow("working", { kind: "stale", operation: "work" }),
    false,
  );
  assert.equal(control.hasAttribute("data-lf-agent-workflow"), false);

  presentContributionReceipts(
    control,
    workflow("picked_up", { kind: "ended", operation: "work" }),
    false,
  );
  assert.equal(control.hasAttribute("data-lf-agent-workflow"), false);
});

test("a reply streaming paints the working face under its own word", () => {
  // Threads says Replying for this receipt (`workflowLabel`); the margin and Page Map
  // control carrying it says the same, under the face it shares with work.
  const control = document.createElement("button");
  presentContributionReceipts(control, workflow("replying"), false);
  assert.equal(control.getAttribute("data-lf-agent-workflow"), "working");
  assert.equal(
    control.getAttribute("aria-description"),
    "Replying · Preparing an update",
  );
  presentContributionReceipts(control, workflow("picked_up"), false);
  assert.equal(control.getAttribute("data-lf-agent-workflow"), "picked_up");
  assert.equal(
    control.getAttribute("aria-description"),
    "Picked up · Preparing an update",
  );
});

test("template contribution hosts paint the retained-host contract and are found on their surface", async () => {
  const {
    html,
    createView,
    createEffect,
  } = await import("/vendor/browser-runtime.js");
  const root = document.createElement("section");
  document.body.append(root);
  const imperative = document.createElement("button");
  const source = {};
  const drawing = createView(
    root,
    (read) =>
      html`<button
        ref=${(control) =>
          createEffect(
            () => read().current,
            (current) => {
              if (!current) return;
              const { record, options, receipt, awaitsUser } = current;
              presentContributionHost(control, record, options);
              trackContributionControl(source, "map", record.key, control);
              presentContributionReceipts(control, receipt, awaitsUser);
            },
          )}
      ></button>`,
    { current: null },
  );
  const paint = (record, options, receipt, awaitsUser) =>
    drawing.update({ current: { record, options, receipt, awaitsUser } });
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
    presentContributionReceipts(imperative, receipt, awaitsUser);
    const control = root.querySelector("button");
    assert.equal(control.outerHTML, imperative.outerHTML);
    assert.equal(contributionControl(source, "apply", "map"), control);
  }
  drawing.dispose();
  root.remove();
});
