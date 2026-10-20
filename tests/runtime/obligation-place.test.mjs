import assert from "node:assert/strict";
import test from "node:test";
import { obligationsIn, obligationPlace } from "/runtime/obligations/place.js";
import { obligationHolding } from "/runtime/standing-target.js";

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
