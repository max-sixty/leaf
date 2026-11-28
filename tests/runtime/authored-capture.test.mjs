import "/runtime/stage-integration.js";
/* Authored inputs are captured before widgets render; presentation may then move
   nodes without changing the document coordinates those inputs established. */
import assert from "node:assert/strict";
import test from "node:test";
import "../../packages/diff/widgets/lf-worktree.js";
import "../../packages/diff/widgets/lf-worktree-diffs.js";
import { adoptRegistry } from "/runtime/state/registry.js";
import {
  rememberAuthoredParents,
  stageAuthoredStates,
} from "/runtime/records/projection/authored.js";
import {
  stageWidgetDescriptors,
  bindWidgetDescriptors,
  widgetDescriptor,
} from "/runtime/records/widget-descriptors.js";

test("capture keeps authored values and parentage when rendering moves members", () => {
  document.body.innerHTML =
    '<main><lf-outer id="outer" status="idle"><lf-left id="left"><lf-inner id="inner">Authored</lf-inner></lf-left><lf-right id="right"></lf-right></lf-outer></main>';
  adoptRegistry({
    $layer: { generation: "capture-before-render" },
    "lf-outer": {
      verbs: {
        set: {
          unit: "widget",
          record: { kind: "value", attr: "status", value: "status" },
        },
      },
    },
    "lf-left": {},
    "lf-right": {},
    "lf-inner": {},
  });
  const root = document.querySelector("main");
  const outer = document.getElementById("outer");
  const inner = document.getElementById("inner");
  rememberAuthoredParents(root);
  const states = stageAuthoredStates(root);
  const descriptors = stageWidgetDescriptors(root, { kind: "page", revision: 1 });
  outer.setAttribute("status", "drawing");
  document.getElementById("right").append(inner);
  bindWidgetDescriptors(descriptors.bindings);
  assert.equal(states.get("outer").state.set.value, "idle");
  assert.deepEqual(widgetDescriptor(inner).parent, { id: "left", tag: "lf-left" });
  assert.equal(inner.parentElement.localName, "lf-right");
});

test("an attribute record counts only Leaf elements among its members", () => {
  document.body.innerHTML =
    '<main><lf-options id="size"><lf-option id="small" selected>Small <select id="unit"><option id="unit-m" selected>m</option></select></lf-option><lf-option id="large">Large</lf-option></lf-options></main>';
  adoptRegistry({
    $layer: { generation: "native-selected" },
    "lf-options": {
      verbs: {
        choose: { unit: "widget", record: { kind: "attribute", attr: "selected" } },
      },
    },
    "lf-option": {},
  });
  const root = document.querySelector("main");
  rememberAuthoredParents(root);
  const states = stageAuthoredStates(root, new Map());
  assert.deepEqual(states.get("size").state.choose.value, ["small"]);
});

test("native idioms never become widget descriptors or authored widget ancestors", () => {
  document.body.innerHTML =
    '<main><table id="native"><tbody><tr><td><lf-nested id="nested">Value</lf-nested></td></tr></tbody></table></main>';
  adoptRegistry({
    $layer: { generation: "native-idioms" },
    "lf-nested": {},
    table: {
      description: "A table idiom.",
      example: "<table></table>",
    },
    "lf-nested.selected": {
      description: "A selected widget idiom.",
      example: '<lf-nested class="selected"></lf-nested>',
    },
  });
  const staged = stageWidgetDescriptors(document.querySelector("main"), {
    kind: "page",
    revision: 2,
  });
  assert.deepEqual([...staged.descriptors.keys()], ["nested"]);
  assert.deepEqual(staged.descriptors.get("nested").ancestors, []);
});

test("an arriving source root keeps its declared parent and exhibit fence", () => {
  adoptRegistry({
    $layer: { generation: "initial-arrival" },
    "lf-quoted-parent": {
      exhibit: true,
    },
    "lf-arrival": {},
  });
  document.body.innerHTML =
    '<main><lf-quoted-parent id="quote"></lf-quoted-parent></main>';
  const parent = document.querySelector("lf-quoted-parent");
  const arriving = document.createElement("lf-arrival");
  arriving.id = "arrival";
  arriving.innerHTML = "<p>Source</p>";
  rememberAuthoredParents(arriving, parent);
  const before = stageWidgetDescriptors(arriving, { kind: "page", revision: 2 });
  assert.deepEqual(before.descriptors.get("arrival").parent, {
    id: "quote",
    tag: "lf-quoted-parent",
  });
  assert.equal(before.descriptors.get("arrival").quoted, true);
  arriving.append(document.createElement("button"));
  const after = stageWidgetDescriptors(arriving, { kind: "page", revision: 2 });
  assert.deepEqual(after.descriptors.get("arrival").parent, {
    id: "quote",
    tag: "lf-quoted-parent",
  });
  assert.equal(after.descriptors.get("arrival").quoted, true);
});

test("member state owns each physical slot independently across a hierarchy", () => {
  const root = document.createElement("main");
  root.innerHTML = `<lf-audit-board id="outer">
    <lf-audit-zone id="one"><lf-audit-card id="card" selected phase="idle">
      <lf-audit-board id="inner"><lf-audit-zone id="inner-zone">
        <lf-audit-card id="inner-card" selected phase="idle">Inner</lf-audit-card>
      </lf-audit-zone></lf-audit-board>
    </lf-audit-card></lf-audit-zone><lf-audit-zone id="two"></lf-audit-zone>
  </lf-audit-board>`;
  const declarations = {
    $layer: { generation: "independent-member-records" },
    "lf-audit-board": {
      verbs: {
        move: { unit: "unit", record: { kind: "position", within: "lf-audit-zone" } },
      },
    },
    "lf-audit-zone": {
      verbs: {
        choose: { unit: "widget", record: { kind: "attribute", attr: "selected" } },
      },
    },
    "lf-audit-card": {
      verbs: {
        phase: { unit: "widget", record: { kind: "value", attr: "phase" } },
      },
    },
  };
  adoptRegistry(declarations);
  const states = stageAuthoredStates(root);
  assert.deepEqual(states.get("outer").state.move.value, { one: ["card"], two: [] });
  assert.deepEqual(states.get("one").state.choose.value, ["card"]);
  assert.deepEqual(states.get("inner-zone").state.choose.value, ["inner-card"]);
});

test("worktree presentation keeps native disclosure and authored evidence while totals change", async () => {
  document.body.innerHTML = "<main></main>";
  const collection = document.createElement("lf-worktree-diffs");
  const host = document.createElement("lf-worktree");
  const evidence = document.createElement("p");
  evidence.textContent = "Kept evidence";
  const attributes = {
    id: "tree",
    label: "Changes",
    path: "/repo",
    status: "changed",
    files: "1",
    additions: "4",
    deletions: "2",
  };
  for (const [name, value] of Object.entries(attributes))
    host.setAttribute(name, value);
  host.append(evidence);
  collection.append(host);
  document.querySelector("main").append(collection);
  const root = /** @type {ShadowRoot} */ (host.shadowRoot);
  const overview = /** @type {ShadowRoot} */ (collection.shadowRoot);
  const disclosure = root.querySelector("details");
  const summary = root.querySelector("summary");
  disclosure.open = true;
  summary.focus();
  /** @type {PromiseLike<unknown>[]} */
  const pending = [];
  document.addEventListener("pending-task", (event) =>
    pending.push(/** @type {any} */ (event).complete),
  );
  host.setAttribute("files", "2");
  host.setAttribute("additions", "7");
  // A descendant connecting is what redraws a kept widget in place.
  evidence.dispatchEvent(new Event("lf-connect", { bubbles: true, composed: true }));
  await Promise.all(pending);
  assert.equal(root.querySelector("details"), disclosure);
  assert.equal(disclosure.open, true);
  assert.equal(root.activeElement, summary);
  assert.equal(host.firstElementChild, evidence);
  assert.equal(root.querySelector("slot").assignedNodes()[0], evidence);
  assert.match(root.querySelector(".lf-worktree-stats").textContent, /2 files/);
  assert.match(overview.querySelector(".lf-worktree-stats").textContent, /\+7/);
});
