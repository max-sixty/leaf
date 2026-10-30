/* Authored inputs are captured before widgets render; presentation may then move
   nodes without changing the document coordinates those inputs established. */
import assert from "node:assert/strict";
import test from "node:test";
import { render, generatedElement, holdAuthoredBody } from "/runtime/widget-api.js";
import { authoredBody } from "/runtime/widget-elements.js";
import { drawToc } from "../../packages/default/widgets/toc-view.js";
import { render as worktree } from "../../packages/diff/widgets/worktree-view.js";
import { render as worktrees } from "../../packages/diff/widgets/worktree-diffs-view.js";
import { adoptShadowStage } from "/runtime/shadow-stage.js";
import { adoptRegistry } from "/runtime/registry.js";
import {
  rememberAuthoredParents,
  stageAuthoredStates,
} from "/runtime/projection/authored.js";
import {
  stageWidgetDescriptors,
  commitWidgetDescriptors,
  widgetDescriptor,
} from "/runtime/widget-descriptors.js";

test("capture keeps authored values and parentage when rendering moves members", () => {
  document.body.innerHTML =
    '<main><lf-outer id="outer" status="idle"><lf-left id="left"><lf-inner id="inner">Authored</lf-inner></lf-left><lf-right id="right"></lf-right></lf-outer></main>';
  adoptRegistry({
    $layer: { generation: "capture-before-render" },
    "lf-outer": {
      "x-state": {
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
  const states = stageAuthoredStates(root, new Map());
  const descriptors = stageWidgetDescriptors(root, { kind: "page", revision: 1 });
  outer.setAttribute("status", "drawing");
  document.getElementById("right").append(inner);
  commitWidgetDescriptors(descriptors);
  assert.equal(states.get("outer").state.set.value, "idle");
  assert.deepEqual(widgetDescriptor(inner).parent, { id: "left", tag: "lf-left" });
  assert.equal(inner.parentElement.localName, "lf-right");
});

test("native idioms never become widget descriptors or authored widget ancestors", () => {
  document.body.innerHTML =
    '<main><table id="native"><tbody><tr><td><lf-nested id="nested">Value</lf-nested></td></tr></tbody></table></main>';
  adoptRegistry({
    "lf-nested": {},
    table: { description: "A table idiom.", "x-example": "<table></table>" },
    "lf-nested.selected": {
      description: "A selected widget idiom.",
      "x-example": '<lf-nested class="selected"></lf-nested>',
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
    "lf-quoted-parent": { "x-exhibit": true },
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
      "x-state": {
        move: { unit: "unit", record: { kind: "position", within: "lf-audit-zone" } },
      },
    },
    "lf-audit-zone": {
      "x-state": {
        choose: { unit: "widget", record: { kind: "attribute", attr: "selected" } },
      },
    },
    "lf-audit-card": {
      "x-state": {
        phase: { unit: "widget", record: { kind: "value", attr: "phase" } },
      },
    },
  };
  adoptRegistry(declarations);
  const states = stageAuthoredStates(root, new Map());
  assert.deepEqual(states.get("outer").state.move.value, { one: ["card"], two: [] });
  assert.deepEqual(states.get("one").state.choose.value, ["card"]);
  assert.deepEqual(states.get("inner-zone").state.choose.value, ["inner-card"]);
});

test("the contents drawing keeps its native state and keyed rows through revisions", () => {
  document.body.innerHTML =
    '<main><h1>Field guide</h1><lf-toc id="contents"></lf-toc>' +
    '<h2 id="first">Take inventory</h2><h3>Save a snapshot</h3></main>';
  const host = document.querySelector("lf-toc");
  const reading = {
    label: (heading) => heading.textContent,
    chrome: () => false,
    lends: true,
  };
  const live = drawToc(host, reading);
  render(live.render(reading), host, { host });
  const disclosure = host.querySelector("details");
  const summary = host.querySelector("summary");
  const links = [...host.querySelectorAll("a")];
  assert.deepEqual(
    links.map((link) => link.getAttribute("href")),
    ["#lf-contents-section-0", "#first", "#lf-contents-section-2"],
  );
  disclosure.open = true;
  links[1].focus();

  render(live.render(reading), host, { host });
  const sections = live.sections();
  assert.equal(host.querySelector("details"), disclosure);
  assert.equal(host.querySelector("summary"), summary);
  assert.equal(disclosure.open, true);
  assert.deepEqual(
    sections.map(({ link }) => link),
    links,
  );
  assert.equal(document.activeElement, links[1]);
  assert.equal(links[2].getAttribute("href"), "#lf-contents-section-2");

  const first = document.querySelector("h2");
  const next = document.querySelector("h3");
  first.before(next);
  first.textContent = "Read the inventory";
  render(live.render(reading), host, { host });
  const reordered = live.sections();
  assert.deepEqual(
    reordered.map(({ link }) => link),
    [links[0], links[2], links[1]],
  );
  assert.equal(links[1].textContent, "Read the inventory");
  assert.equal(disclosure.open, true);
  host.remove();
  assert.equal(live.scope(), null);
  document.querySelector("main").append(host);
  assert.equal(live.scope(), document.querySelector("main"));
  render(live.render(reading), host, { host });
  assert.equal(live.sections()[1].link, links[2]);
});

test("generated words declare whether they are said, echoed or apparatus", () => {
  const heading = generatedElement(document.createElement("h2"), { says: true });
  const name = generatedElement(document.createElement("span"), { says: "echo" });
  const declared = document.createElement("span");
  declared.dataset.lfSaid = "label";
  generatedElement(declared, { says: true });
  assert.throws(() => generatedElement(document.createElement("p"), {}), TypeError);
  const markers = (node) =>
    ["data-lf-gen", "data-lf-said", "data-lf-echo"].map((a) => node.getAttribute(a));
  assert.deepEqual(markers(heading), ["1", "", null]);
  assert.deepEqual(markers(name), ["1", null, ""]);
  assert.deepEqual(markers(declared), ["1", "label", null]);
  generatedElement(name, { says: false });
  assert.deepEqual(markers(name), ["1", null, null]);
});

test("an authored body retains every authored child for member patching", () => {
  const host = document.createElement("lf-bodied");
  host.innerHTML = "<p>One</p> <p>Two</p>";
  const written = [...host.childNodes];
  const body = holdAuthoredBody(host, document.createElement("div"));
  host.append(body);
  assert.deepEqual([...body.childNodes], written);
  assert.equal(authoredBody(host), body);
  assert.equal(authoredBody(document.createElement("lf-plain")), null);
});

test("worktree presentation keeps native disclosure and authored evidence while totals change", () => {
  document.body.innerHTML =
    '<main><lf-worktree-diffs id="set"><lf-worktree id="tree"><p id="evidence">Kept evidence</p></lf-worktree></lf-worktree-diffs></main>';
  const collection = document.getElementById("set");
  const host = document.getElementById("tree");
  const evidence = document.getElementById("evidence");
  const root = adoptShadowStage(host.attachShadow({ mode: "open" }));
  const overview = adoptShadowStage(collection.attachShadow({ mode: "open" }));
  const attributes = {
    label: "Changes",
    path: "/repo",
    status: "changed",
    files: "1",
    additions: "4",
    deletions: "2",
  };
  for (const [name, value] of Object.entries(attributes))
    host.setAttribute(name, value);
  const draw = () => {
    render(worktree(host), root);
    render(worktrees(collection), overview);
  };
  draw();
  const disclosure = root.querySelector("details");
  const summary = root.querySelector("summary");
  disclosure.open = true;
  summary.focus();
  host.setAttribute("files", "2");
  host.setAttribute("additions", "7");
  draw();
  adoptShadowStage(root);
  assert.equal(root.querySelector("details"), disclosure);
  assert.equal(disclosure.open, true);
  assert.equal(root.activeElement, summary);
  assert.equal(host.firstElementChild, evidence);
  assert.equal(root.querySelector("slot").assignedNodes()[0], evidence);
  assert.match(root.querySelector(".lf-worktree-stats").textContent, /2 files/);
  assert.match(overview.querySelector(".lf-worktree-stats").textContent, /\+7/);
  assert.equal(root.querySelectorAll("style").length, 1);
});
