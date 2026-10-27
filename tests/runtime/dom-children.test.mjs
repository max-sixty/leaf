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
import { createRef, html, ref, render } from "/runtime/framework.js";

test("failure replacement releases directives and the next native draw replaces it", () => {
  const host = document.createElement("test-widget");
  const reference = createRef();
  render(html`<p ${ref(reference)}>Before failure</p>`, host);
  assert.equal(reference.value.textContent, "Before failure");
  failSoftUnreported(host, new Error("first failure"));
  assert.equal(reference.value, undefined);
  assert.equal(host.textContent, "<test-widget> failed: first failure");
  const native = document.createElement("p");
  native.textContent = "Recovered native reading";
  setChildren(host, [native]);
  assert.equal(host.textContent, "Recovered native reading");
});

test("a staged widget shows each failure in its stage and its next stage replaces it", () => {
  const host = document.createElement("test-widget");
  document.body.append(host);
  const view = document.createElement("p");
  view.textContent = "Good reading";
  shadowStage(host, [view]);
  const rendererSheet = new CSSStyleSheet();
  rendererSheet.replaceSync("p { color: red }");
  // An embedded renderer owns its sheet; restaging adds Leaf's apparatus without
  // losing the renderer's face or accumulating copies on later draws.
  host.shadowRoot.adoptedStyleSheets = [rendererSheet];
  for (const message of ["first failure", "second failure"]) {
    failSoftUnreported(host, new Error(message));
    const errors = host.shadowRoot.querySelectorAll(".lf-error");
    assert.deepEqual(
      [...errors].map((box) => box.textContent),
      [`<test-widget> failed: ${message}`],
    );
    assert.equal(view.isConnected, false);
    shadowStage(host, [view]);
    assert.equal(
      host.shadowRoot.adoptedStyleSheets.filter((sheet) => sheet === rendererSheet)
        .length,
      1,
    );
    assert.ok(host.shadowRoot.adoptedStyleSheets.length > 1);
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
    body: () => null,
    unchanged: (held, wanted) => held.isEqualNode(wanted),
    same: (held, wanted) => held.isEqualNode(wanted),
    sameValue: (_name, held, wanted) => held === wanted,
    touched: () => {},
    generated: () => false,
  };
  return {
    live,
    after,
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

// A moved element is laid out afresh, and Firefox then anchors its scrolling on
// whatever ends the viewport: once a revision that removed a section above a reader at
// the page's end had moved the two sections after it, everything they typed below
// lifted the page. The whitespace that stood after the section may move instead.
test("a revision removing a section moves none of the sections after it", () => {
  const { live, install } = patch(
    '<p id="a">A</p>\n\n<section id="gone">G</section>\n\n<section id="b">B</section>\n\n<section id="c">C</section>\n',
    '<p id="a">A</p>\n\n<section id="b">B</section>\n\n<section id="c">C</section>\n',
  );
  const nativeMove = Element.prototype.moveBefore;
  const moved = [];
  Element.prototype.moveBefore = function (node, before) {
    moved.push(node);
    return this.insertBefore(node, before);
  };
  try {
    install();
  } finally {
    Element.prototype.moveBefore = nativeMove;
  }
  assert.deepEqual(
    moved.filter((node) => node.nodeType === Node.ELEMENT_NODE),
    [],
  );
  assert.equal(
    live.innerHTML,
    '<p id="a">A</p>\n\n<section id="b">B</section>\n\n<section id="c">C</section>\n',
  );
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

test("a widget a revision keeps stands for the same live nodes inside it", () => {
  const { live, after, rules, install } = patch(
    '<test-owner id="o"><p>Kept words.</p></test-owner><p>Before</p>',
    '<test-owner id="o"><p>Kept words.</p></test-owner><p>After</p>',
  );
  const words = live.querySelector("test-owner p");
  // The controller moved its paragraph into a box of its own.
  const box = document.createElement("div");
  live.firstElementChild.append(box);
  box.append(words);
  install();
  const source = after.querySelector("test-owner p");
  assert.equal(rules.pairs.get(source), words);
  assert.equal(rules.pairs.get(source.firstChild), words.firstChild);
});

test("a revision reaching a widget writes inside the authored body its module built", () => {
  const { live, rules, install } = patch(
    '<test-owner id="o"><p>Before</p></test-owner>',
    '<test-owner id="o"><p>After</p><p>Added</p></test-owner>',
  );
  const owner = live.firstElementChild;
  const kept = owner.firstElementChild;
  const body = document.createElement("div");
  body.append(...owner.childNodes);
  const summary = document.createElement("span");
  owner.append(summary, body);
  rules.reaches = () => true;
  rules.body = (node) => (node === owner ? body : null);
  rules.arrive = (node) => node.cloneNode(true);
  install();
  assert.deepEqual([...owner.children], [summary, body]);
  assert.equal(body.innerHTML, "<p>After</p><p>Added</p>");
  assert.equal(body.firstElementChild, kept);
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

test("a reorder moves only the nodes that left the run in place", () => {
  const nativeMove = Element.prototype.moveBefore;
  const moved = [];
  Element.prototype.moveBefore = function (node, before) {
    moved.push(node);
    return this.insertBefore(node, before);
  };
  try {
    const parent = document.createElement("div");
    const [a, b, c, d] = ["a", "b", "c", "d"].map((id) => {
      const node = document.createElement("p");
      node.id = id;
      return node;
    });
    parent.append(a, b, c, d);
    document.body.replaceChildren(parent);
    setChildren(parent, [b, c, d, a]);
    assert.deepEqual([...parent.children], [b, c, d, a]);
    assert.deepEqual(moved, [a]);
  } finally {
    Element.prototype.moveBefore = nativeMove;
  }
});
