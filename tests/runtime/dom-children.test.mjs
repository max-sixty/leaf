import assert from "node:assert/strict";
import test from "node:test";
import { patchRetains, patchTree } from "/runtime/dom-children.js";
import { under } from "/runtime/shadow.js";

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
