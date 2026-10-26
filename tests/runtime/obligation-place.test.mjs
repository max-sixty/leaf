import assert from "node:assert/strict";
import test from "node:test";
import { obligationsIn, obligationPlace } from "/runtime/obligations/place.js";
import { obligationHolding } from "/runtime/current-target.js";

test("shared context keeps placement and containment specific to each obligation", () => {
  document.body.innerHTML =
    '<section id="context"><div id="first"><button>One</button></div><div id="second"><button>Two</button></div></section>';
  const item = (id) => ({
    id: `widget:${id}`,
    thread: null,
    message: null,
    source: { kind: "widget", id },
    prompt: { target: "context" },
  });
  const first = item("first");
  const second = item("second");
  const items = [first, second];
  try {
    assert.equal(obligationPlace(first, [first]).node.id, "context");
    for (const record of items) {
      const place = obligationPlace(record, items);
      assert.equal(place.source.id, record.source.id);
      assert.equal(place.node, place.source);
      assert.equal(place.context.id, "context");
      assert.equal(obligationHolding(items, place.source.firstElementChild), record);
    }
    assert.equal(obligationHolding(items, document.getElementById("context")), null);
  } finally {
    document.body.replaceChildren();
  }
});

test("the innermost obligation holding a node is where the user stands", () => {
  // A question inside a proposal's new text: the proposal's source holds the question's
  // enclosing widget, where arrival puts the user on the question.
  document.body.innerHTML =
    '<div id="change"><p id="text">Walk outside.</p><section id="ask"><h4>Which route?</h4><div id="route"><button>Garden</button></div></section></div>';
  const item = (source, target) => ({
    id: `widget:${source}`,
    thread: null,
    message: null,
    source: { kind: "widget", id: source },
    prompt: { target },
  });
  const change = item("change", "change");
  const route = item("route", "ask");
  const at = (id) => document.getElementById(id);
  try {
    for (const items of [
      [change, route],
      [route, change],
    ]) {
      assert.equal(obligationHolding(items, at("ask")), route);
      assert.equal(obligationHolding(items, at("ask").firstElementChild), route);
      assert.equal(obligationHolding(items, at("route").firstElementChild), route);
      assert.equal(obligationHolding(items, at("text")), change);
    }
  } finally {
    document.body.replaceChildren();
  }
});

test("a region holds the live widget obligations whose source is it or stands under it", () => {
  document.body.innerHTML =
    '<section id="queue"><div id="item"><div id="first"></div><div id="gone"></div></div></section><div id="outside"></div>';
  const item = (id, status = "open", kind = "widget") => ({
    id: `${kind}:${id}`,
    thread: null,
    message: null,
    status,
    source: { kind, id },
    prompt: { target: id },
  });
  const items = [
    item("first"),
    item("gone", "withdrawn"),
    item("outside", "answered"),
    item("missing"),
    item("item", "answered"),
    item("first", "open", "reply"),
  ];
  const ids = (region) =>
    obligationsIn(document.getElementById(region), items).map((held) => held.id);
  try {
    assert.deepEqual(ids("queue"), ["widget:first", "widget:item"]);
    assert.deepEqual(ids("item"), ["widget:first", "widget:item"]);
    assert.deepEqual(ids("first"), ["widget:first"]);
    assert.deepEqual(ids("outside"), ["widget:outside"]);
  } finally {
    document.body.replaceChildren();
  }
});

test("a to-do on the user stands at its subject, holding it but no region", () => {
  document.body.innerHTML =
    '<main><section id="notes"><h2>Notes</h2><div id="pick"><button>Beta</button></div></section></main>';
  const todo = (id, subject) => ({
    id,
    thread: null,
    message: null,
    status: "open",
    source: { kind: "todo", id, subject },
    prompt: { text: id, target: subject.id ?? null },
  });
  const pick = {
    id: "widget:pick",
    thread: null,
    message: null,
    status: "open",
    source: { kind: "widget", id: "pick" },
    prompt: { target: "pick" },
  };
  const notes = todo("t-notes", { kind: "element", id: "notes" });
  const onPick = todo("t-pick", { kind: "widget", id: "pick" });
  const whole = todo("t-page", { kind: "page" });
  const onThread = todo("t-thread", { kind: "thread", id: "th-1" });
  // As the inventory lists them: widgets' obligations, then the user's tasks.
  const items = [pick, notes, onPick, whole, onThread];
  const at = (id) => document.getElementById(id);
  try {
    assert.equal(obligationPlace(notes, items).node, at("notes"));
    assert.equal(obligationPlace(notes, items).source, null);
    assert.equal(obligationPlace(onThread, items).node, null);
    // With no top-level heading, the page's head is its first heading.
    assert.equal(obligationPlace(whole, items).node, document.querySelector("h2"));
    assert.equal(obligationHolding(items, at("notes")), notes);
    // On a widget a to-do is on, the widget's own question holds the user.
    assert.equal(obligationHolding(items, at("pick").firstElementChild), pick);
    assert.equal(obligationHolding([onPick], at("pick")), onPick);
    // The section's heading is the page's head, inside the notes' to-do.
    assert.equal(obligationHolding(items, document.querySelector("h2")), whole);
    // A region counts what its widgets ask, which a to-do is not.
    assert.deepEqual(
      obligationsIn(at("notes"), items).map((held) => held.id),
      ["widget:pick"],
    );
    document.querySelector("main").insertAdjacentHTML("afterbegin", "<h1>Release</h1>");
    assert.equal(obligationPlace(whole, items).node, document.querySelector("h1"));
    document.querySelector("main").innerHTML = '<p id="lead">Plain words.</p>';
    assert.equal(obligationPlace(whole, items).node, at("lead"));
  } finally {
    document.body.replaceChildren();
  }
});
