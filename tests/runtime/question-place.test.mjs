import assert from "node:assert/strict";
import test from "node:test";
import { asksIn, questionPlace } from "/runtime/questions/place.js";
import { questionHolding } from "/runtime/standing-target.js";

test("shared context keeps placement and containment specific to each Question", () => {
  document.body.innerHTML =
    '<section id="context"><div id="first"><button>One</button></div><div id="second"><button>Two</button></div></section>';
  const question = (id) => ({
    id: `widget:${id}`,
    thread: null,
    message: null,
    source: { kind: "widget", id },
    prompt: { target: "context" },
  });
  const first = question("first");
  const second = question("second");
  const questions = [first, second];
  try {
    assert.equal(questionPlace(first, [first]).node.id, "context");
    for (const record of questions) {
      const place = questionPlace(record, questions);
      assert.equal(place.source.id, record.source.id);
      assert.equal(place.node, place.source);
      assert.equal(place.context.id, "context");
      assert.equal(questionHolding(questions, place.source.firstElementChild), record);
    }
    assert.equal(questionHolding(questions, document.getElementById("context")), null);
  } finally {
    document.body.replaceChildren();
  }
});

test("a region holds the live widget asks whose source is it or stands under it", () => {
  document.body.innerHTML =
    '<section id="queue"><div id="item"><div id="first"></div><div id="gone"></div></div></section><div id="outside"></div>';
  const ask = (id, status = "open", kind = "widget") => ({
    id: `${kind}:${id}`,
    thread: null,
    message: null,
    status,
    source: { kind, id },
    prompt: { target: id },
  });
  const asks = [
    ask("first"),
    ask("gone", "withdrawn"),
    ask("outside", "answered"),
    ask("missing"),
    ask("item", "answered"),
    ask("first", "open", "reply"),
  ];
  const ids = (region) =>
    asksIn(document.getElementById(region), asks).map((held) => held.id);
  try {
    assert.deepEqual(ids("queue"), ["widget:first", "widget:item"]);
    assert.deepEqual(ids("item"), ["widget:first", "widget:item"]);
    assert.deepEqual(ids("first"), ["widget:first"]);
    assert.deepEqual(ids("outside"), ["widget:outside"]);
  } finally {
    document.body.replaceChildren();
  }
});
