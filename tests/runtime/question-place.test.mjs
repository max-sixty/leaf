import assert from "node:assert/strict";
import test from "node:test";
import { questionPlace } from "/runtime/questions/place.js";
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
