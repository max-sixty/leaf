import assert from "node:assert/strict";
import test from "node:test";
import { createAnnotationInventory } from "/runtime/annotation-inventory.js";
import { contributionEntry } from "/runtime/contribution-controls.js";
import { registerContribution } from "/runtime/contributions.js";
import { resolvedPassage } from "/runtime/resolved-target.js";
import { applicationState } from "/runtime/semantic-state.js";
import { servedState, servedThread } from "../served.mjs";

const obligation = (id) => ({
  id,
  thread: null,
  message: null,
  source: { kind: "widget", id: "asked" },
  prompt: { target: "asked" },
});

const inventoryOf = (user = []) =>
  createAnnotationInventory({
    readObligations: () => ({ all: user, user }),
    placedAt: () => null,
    openThread() {},
    goToObligation() {},
    scrollToElement() {},
  });

const entryFor = (entries, id) => entries.find((entry) => entry.targetId === id);

test("an entry stays one object until what it is made from changes", () => {
  document.body.innerHTML =
    '<main><p id="asked">A question</p><p id="other">Other</p></main>';
  const asks = [obligation("first")];
  const inventory = inventoryOf(asks);
  const registration = registerContribution({
    key: "probe",
    target: document.getElementById("other"),
    read: () => ({
      entries: [contributionEntry({ key: "go", label: "Go", icon: "check" })],
    }),
    activate() {},
  });
  try {
    const first = inventory.collect();
    const second = inventory.collect();
    assert.notEqual(second, first, "each collection is a reading of its own");
    assert.equal(entryFor(second, "asked"), entryFor(first, "asked"));
    assert.equal(entryFor(second, "other"), entryFor(first, "other"));

    // A producer's publication is a change, whatever it says, since it can carry a
    // command the record's values don't show (contribution-controls.js).
    registration.update();
    const published = inventory.collect();
    assert.notEqual(entryFor(published, "other"), entryFor(second, "other"));
    assert.equal(entryFor(published, "asked"), entryFor(second, "asked"));

    // A word the entry says, read off the page.
    document.getElementById("asked").setAttribute("aria-label", "Another question");
    const named = inventory.collect();
    assert.notEqual(entryFor(named, "asked"), entryFor(published, "asked"));
    assert.equal(entryFor(named, "other"), entryFor(published, "other"));

    asks.push(obligation("second"));
    const grown = inventory.collect();
    assert.notEqual(entryFor(grown, "asked"), entryFor(named, "asked"));
    assert.equal(entryFor(grown, "asked").items.length, 2);
  } finally {
    registration.unregister();
    document.body.replaceChildren();
  }
});

test("a kept item acts through the capabilities of the latest reading", () => {
  document.body.innerHTML = '<main><p id="asked">A question</p></main>';
  const inventory = inventoryOf([obligation("first")]);
  try {
    const [entry] = inventory.collect();
    const [item] = entry.items;
    const held = inventory.sourceItem(item);
    const [kept] = inventory.collect();
    assert.equal(kept, entry);
    assert.notEqual(inventory.sourceItem(item), held);
  } finally {
    document.body.replaceChildren();
  }
});

// A passage's row is keyed from a reading of its target's words, which a change to
// another part of the page leaves as they were, as a closed tab's document drawing does:
// the collection that follows reads none of the target's elements.
test("a quoted passage is keyed once while its target's words are unchanged", () => {
  applicationState.identify(1);
  document.body.innerHTML =
    '<main><p id="other">Other words</p><div id="doc" data-lf-projection="w" ' +
    'data-lf-datum="doc"><p>Alpha <b>beta</b> gamma <b>beta</b></p></div></main>';
  const doc = document.getElementById("doc");
  const second = doc.querySelectorAll("b")[1].firstChild;
  const comment = {
    id: "c1",
    seq: 1,
    ts: "2026-09-19T12:00:00+00:00",
    author: "user",
    revision: 1,
    kind: "comment",
    text: "Which beta?",
    attention: true,
    content_version: "c1",
  };
  const thread = servedThread([comment], {
    anchor: { section: "doc", datum: "doc", quote: "beta" },
  });
  applicationState.adopt(
    servedState({ browser: { views: { 1: { thread: { threads: [thread] } } } } }),
  );
  const placement = {
    ...resolvedPassage({ place: doc, segments: [{ node: second, start: 0, end: 4 }] }),
    point: null,
  };
  const inventory = createAnnotationInventory({
    readObligations: () => ({ all: [], user: [] }),
    placedAt: () => placement,
    openThread() {},
    goToObligation() {},
    scrollToElement() {},
  });
  const { matches } = Element.prototype;
  let asked = 0;
  Element.prototype.matches = function (selector) {
    if (doc.contains(this) && this !== doc) asked += 1;
    return matches.call(this, selector);
  };
  const collected = () => {
    asked = 0;
    const entry = inventory.collect().find((each) => each.targetId === "doc");
    return { asked, key: entry.key };
  };
  try {
    const first = collected();
    assert.match(first.key, /\["beta",1\]$/, "the second copy of its words");
    document.getElementById("other").firstChild.data = "Other words edited";
    assert.deepEqual(collected(), { asked: 0, key: first.key });
    // A change to the words it stands in reads them again.
    doc.querySelector("b").firstChild.data = "delta";
    const moved = collected();
    assert.ok(moved.asked > 0);
    assert.match(moved.key, /\["beta",0\]$/, "now the first copy of its words");
  } finally {
    Element.prototype.matches = matches;
    document.body.replaceChildren();
  }
});
