import assert from "node:assert/strict";
import test from "node:test";
import {
  patchRetains,
  patchTree,
  setChildLists,
  setChildren,
} from "/runtime/dom-children.js";
import { under } from "/runtime/shadow.js";
import { shadowStage } from "/runtime/shadow-stage.js";
import { failSoftUnreported } from "/runtime/widget-upgrade.js";
import { createRef, html, ref, render } from "/vendor/browser-runtime.js";

test("failure replacement releases directives and supports native and template recovery", () => {
  const host = document.createElement("test-widget");
  const reference = createRef();
  const paint = (text) => render(html`<p ${ref(reference)}>${text}</p>`, host);
  paint("Before failure");
  assert.equal(reference.value.textContent, "Before failure");
  failSoftUnreported(host, new Error("first failure"));
  assert.equal(reference.value, undefined);
  paint("Recovered template");
  assert.equal(host.textContent, "Recovered template");
  failSoftUnreported(host, new Error("second failure"));
  const native = document.createElement("p");
  native.textContent = "Recovered native reading";
  setChildren(host, [native]);
  assert.equal(host.textContent, "Recovered native reading");
  failSoftUnreported(host, new Error("third failure"));
  paint("Final template");
  assert.equal(host.textContent, "Final template");
});

test("a staged widget shows each failure in its stage and its next stage replaces it", () => {
  const host = document.createElement("test-widget");
  document.body.append(host);
  const view = document.createElement("p");
  view.textContent = "Good reading";
  shadowStage(host, [view]);
  for (const message of ["first failure", "second failure"]) {
    failSoftUnreported(host, new Error(message));
    const errors = host.shadowRoot.querySelectorAll(".lf-error");
    assert.deepEqual(
      [...errors].map((box) => box.textContent),
      [`<test-widget> failed: ${message}`],
    );
    assert.equal(view.isConnected, false);
    shadowStage(host, [view]);
    assert.equal(host.shadowRoot.querySelector(".lf-error"), null);
    assert.equal(view.isConnected, true);
  }
  host.remove();
});

function patch(beforeMarkup, afterMarkup = beforeMarkup) {
  const main = (markup) => {
    const node = document.createElement("main");
    node.innerHTML = markup;
    return node;
  };
  const before = main(beforeMarkup);
  const after = main(afterMarkup);
  const live = before.cloneNode(true);
  document.body.replaceChildren(live);
  const pairs = new Map();
  const pair = (source, node) => {
    pairs.set(source, node);
    [...source.childNodes].forEach((child, i) => pair(child, node.childNodes[i]));
  };
  pair(before, live);
  const rules = {
    pairs,
    contains: under,
    declared: (node) => node.localName === "test-owner",
    reaches: () => false,
    unchanged: (held, wanted) => held.isEqualNode(wanted),
    same: (held, wanted) => held.isEqualNode(wanted),
    sameValue: (_name, held, wanted) => held === wanted,
    touched: () => {},
    generated: () => false,
  };
  return {
    live,
    rules,
    retains: (node) => patchRetains(before, after, node, rules),
    install: () => patchTree(before, after, rules),
  };
}

test("runtime chrome outside the authored patch survives; detached fields do not", () => {
  const { retains } = patch("<p>Before</p>", "<p>After</p>");
  const editor = document.createElement("textarea");
  assert.equal(retains(editor), false);
  document.body.append(editor);
  assert.equal(retains(editor), true);
});

test("an authored editor moved outside main still belongs to the patch", () => {
  const { live, retains, install } = patch('<textarea id="note"></textarea>', "");
  const editor = live.querySelector("textarea");
  document.body.append(editor);
  assert.equal(retains(editor), false);
  install();
  assert.equal(editor.isConnected, false);
});

test("an unchanged authored editor moved outside main follows unrelated revisions", () => {
  const { live, retains, install } = patch(
    '<textarea id="note"></textarea><p>Before</p>',
    '<textarea id="note"></textarea><p>After</p>',
  );
  const editor = live.querySelector("textarea");
  document.body.append(editor);
  assert.equal(retains(editor), true);
  install();
  assert.equal(editor.isConnected, true);
  assert.equal(live.querySelector("p").textContent, "After");
});

test("both the logical and current physical source owners must retain a moved editor", () => {
  for (const removed of [null, "logical", "physical"]) {
    const field = '<textarea id="note"></textarea>';
    const outlet = '<div id="outlet"></div>';
    const { live, retains, install } = patch(
      `${outlet}${field}<p>Before</p>`,
      `${removed === "physical" ? "" : outlet}${removed === "logical" ? "" : field}<p>After</p>`,
    );
    const editor = live.querySelector("textarea");
    live.firstElementChild.append(editor);
    assert.equal(retains(editor), removed === null);
    install();
    assert.equal(editor.isConnected, removed === null);
  }
});

test("a generated editor in an unchanged authored container survives unrelated changes", () => {
  const { live, retains, install } = patch(
    '<div id="outlet"></div><p>Before</p>',
    '<div id="outlet"></div><p>After</p>',
  );
  const editor = document.createElement("textarea");
  editor.setAttribute("data-lf-runtime", "");
  editor.value = "Unsent reply";
  live.firstElementChild.append(editor);
  assert.equal(retains(editor), true);
  install();
  assert.equal(editor.isConnected, true);
  assert.equal(editor.value, "Unsent reply");
  assert.equal(live.querySelector("p").textContent, "After");
});

test("a generated editor directly under the patch root survives source sibling changes", () => {
  const { live, retains, install } = patch("<p>Before</p>", "<p>After</p>");
  const editor = document.createElement("textarea");
  live.append(editor);
  assert.equal(retains(editor), true);
  install();
  assert.equal(editor.isConnected, true);
  assert.equal(live.querySelector("p").textContent, "After");
});

test("a native shadow editor follows its containing owner's authored retention", () => {
  for (const changed of [false, true]) {
    const { live, retains } = patch(
      '<test-owner id="owner">Before</test-owner>',
      `<test-owner id="owner">${changed ? "After" : "Before"}</test-owner>`,
    );
    const root = live.firstElementChild.attachShadow({ mode: "open" });
    const editor = document.createElement("textarea");
    root.append(editor);
    assert.equal(retains(editor), !changed);
  }
});

test("child reordering works without moveBefore and accepts new nodes", () => {
  const nativeMove = Element.prototype.moveBefore;
  Element.prototype.moveBefore = undefined;
  try {
    const parent = document.createElement("div");
    const a = document.createElement("input");
    const b = document.createElement("input");
    parent.append(a, b);
    setChildren(parent, [b, a]);
    assert.deepEqual([...parent.children], [b, a]);
    const c = document.createElement("input");
    setChildren(parent, [c, a, b]);
    assert.deepEqual([...parent.children], [c, a, b]);
  } finally {
    Element.prototype.moveBefore = nativeMove;
  }
});

// happy-dom has no moveBefore, the browser's move that keeps a node's native state, so
// this one records each node it moves. A node removed first, by a list it left before
// the list it joins placed it, arrives from a detached tree and cannot take it.
test("a node changing lists moves straight across, keeping its native state", () => {
  const nativeMove = Element.prototype.moveBefore;
  const kept = [];
  Element.prototype.moveBefore = function (node, before) {
    kept.push(node);
    return this.insertBefore(node, before);
  };
  try {
    const row = document.createElement("div");
    const menu = document.createElement("div");
    // The field's old group leaves the lists as the field moves to the menu.
    const group = document.createElement("section");
    const field = document.createElement("input");
    const other = document.createElement("input");
    group.append(field);
    row.append(group, other);
    document.body.replaceChildren(row, menu);
    setChildLists([
      [row, [other]],
      [menu, [field]],
    ]);
    assert.deepEqual([...row.childNodes], [other]);
    assert.deepEqual([...menu.childNodes], [field]);
    assert.deepEqual(kept, [field]);
    setChildLists([
      [row, [field, other]],
      [menu, []],
    ]);
    assert.deepEqual([...row.childNodes], [field, other]);
    assert.deepEqual(kept, [field, field]);
  } finally {
    Element.prototype.moveBefore = nativeMove;
  }
});
