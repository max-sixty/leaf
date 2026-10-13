/* Note ownership and authored-detail restoration. Browser navigation tests retain
   the native ARIA relation and shadow-tree accessibility checks. happy-dom lacks
   ariaDetailsElements, so this rule test models that native setter's empty attribute. */
import assert from "node:assert/strict";
import test from "node:test";
import { shelve, unshelve } from "../../skills/leaf/assets/runtime/details-shelf.js";

test("the shelf keeps all notes after authored details and restores the latest source", () => {
  const root = document.createElement("section");
  root.innerHTML =
    '<p id="shelf-held" aria-details="shelf-own">Held.</p>' +
    '<p id="shelf-own">Own details.</p><p id="shelf-later">Later details.</p>';
  document.body.append(root);
  const held = root.querySelector("#shelf-held");
  let relation = [];
  let writes = 0;
  Object.defineProperty(held, "ariaDetailsElements", {
    get: () => relation,
    set: (value) => {
      relation = value;
      writes++;
      held.setAttribute("aria-details", "");
    },
  });
  const one = Object.assign(document.createElement("button"), { id: "shelf-one" });
  const two = Object.assign(document.createElement("div"), { id: "shelf-two" });
  const named = () => relation.map((node) => node.id);
  try {
    shelve(held, one);
    shelve(held, two);
    assert.deepEqual(named(), ["shelf-own", "shelf-one", "shelf-two"]);
    unshelve(held, one);
    assert.deepEqual(named(), ["shelf-own", "shelf-two"]);
    const before = writes;
    shelve(held, two);
    shelve(held, two);
    assert.equal(writes, before, "an unchanged relation writes nothing");
    held.setAttribute("aria-details", "shelf-later");
    shelve(held, two);
    assert.deepEqual(named(), ["shelf-later", "shelf-two"]);
    unshelve(held, two);
    assert.equal(held.getAttribute("aria-details"), "shelf-later");
  } finally {
    unshelve(held, one);
    unshelve(held, two);
    root.remove();
  }
});
