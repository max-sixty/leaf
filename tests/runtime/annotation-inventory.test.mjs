import assert from "node:assert/strict";
import test from "node:test";
import { createAnnotationInventory } from "/runtime/annotation-inventory.js";
import { contributionEntry } from "/runtime/contribution-controls.js";
import { registerContribution } from "/runtime/contributions.js";

const obligation = (id) => ({
  id,
  thread: null,
  message: null,
  source: { kind: "widget", id: "asked" },
  prompt: { target: "asked" },
});

const inventoryOf = (user = []) =>
  createAnnotationInventory({
    readObligations: () => ({ user }),
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
