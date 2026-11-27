/* A custom element that is no `LeafElement` is given its state and data from outside
   (host/element-integration.js).

   These hold what the host and `widgetState` decide on their own: the `state` a
   reading becomes, when a plain element's bound data is set on it, what an element
   that asks as it connects is given, what the page waits for, and what becomes of a
   setter that throws. The elements here are no
   declared widgets, so each owns a region of its own; a widget's recorded state, its
   `lf-action` and its comment targets cross the page's reading, and are the browser
   suite's (tests/browser/test_plain_elements.py). */
import assert from "node:assert/strict";
import test from "node:test";
import { hostDeclaredElements } from "/runtime/host/element-integration.js";
import { widgetState } from "/runtime/host/widget-state.js";
import { failureOf, placesFailure } from "/runtime/lib/failure.js";
import { adoptRegistry } from "/runtime/state/registry.js";
import { acceptData, notifyDataSubscribers } from "/runtime/host/data.js";
import { readApplicationPresentation } from "/runtime/state/semantic-state.js";

let tags = 0;

// The arrival batch that meets an element, and the sets it brings.
const settled = () => new Promise((resolve) => setTimeout(resolve, 0));

// A page whose registry declares a tag bound to two sources, `value` to rows and
// `notes` to words, and a delivery of either.
function bound(declaration = {}) {
  const tag = `lf-plain-${++tags}`;
  adoptRegistry({
    [tag]: {
      inputs: {
        rows: { source: "source", contract: "rows", property: "value" },
        words: { source: "notes", contract: "rows", property: "notes" },
      },
      ...declaration,
    },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  hostDeclaredElements();
  const sources = {};
  const accept = async (version, revisions) => {
    for (const [source, revision] of Object.entries(revisions))
      sources[source] = {
        contract: "rows",
        revision,
        value: [{ key: "api", revision }],
      };
    acceptData({ version, sources: { ...sources } }, 1);
    await notifyDataSubscribers();
  };
  const element = (attributes = { source: "builds" }) => {
    const made = document.createElement(tag);
    for (const [name, value] of Object.entries(attributes))
      made.setAttribute(name, value);
    return made;
  };
  return { tag, accept, element };
}

const revision = (value) => value?.[0].revision ?? null;

// The failures a page would report while `work` runs, each as its element and message.
async function reported(work) {
  const failures = [];
  const report = (event) => failures.push(failureOf(event));
  window.addEventListener("error", report);
  try {
    await work();
  } finally {
    window.removeEventListener("error", report);
  }
  return failures.map(({ element, reason }) => [element, reason.message]);
}

test("a plain element is set nothing until the page has read its data, then each delivery", async () => {
  const { tag, accept, element: make } = bound();
  const sets = [];
  customElements.define(
    tag,
    class extends HTMLElement {
      set value(next) {
        sets.push(revision(next));
      }
    },
  );
  const element = make();
  document.body.append(element);
  await settled();
  assert.deepEqual(sets, [], "a source nobody has read is not set as empty");
  await accept("d1", { builds: "b1" });
  assert.deepEqual(sets, ["b1"]);
  await accept("d2", { builds: "b2" });
  assert.deepEqual(sets, ["b1", "b2"]);
  assert.equal(document.body.getAttribute("data-lf-data-version"), "d2");
  // Away, it is set nothing, and it is set what it missed as it returns.
  element.remove();
  await settled();
  await accept("d3", { builds: "b3" });
  assert.deepEqual(sets, ["b1", "b2"]);
  document.body.append(element);
  await settled();
  assert.deepEqual(sets, ["b1", "b2", "b3"]);
  element.remove();
});

test("a reading becomes a state saying what the user may do, why not, and what they may take back", () => {
  const picked = (candidate) => ({
    action: "pick",
    value: null,
    detail: { candidate, picked: true },
  });
  const reading = {
    state: {
      decide: { action: "decide", value: "ship", detail: { value: "ship" } },
      pick: { units: { ada: picked("ada"), grace: picked("grace") } },
      // A verb the agent writes is no action of the user's.
      status: { action: null, value: "planned", detail: {} },
    },
    actions: {
      decide: {
        available: true,
        unavailable: null,
        inForce: [{ unit: "verdict", event: { id: "e1" } }],
        undo: [{ id: "e1" }],
      },
      pick: {
        available: false,
        unavailable: "no agent or server is available",
        inForce: [
          { unit: "ada", event: { id: "e2" } },
          { unit: "grace", event: { id: "e3" } },
        ],
        undo: [{ id: "e3" }],
      },
    },
  };
  const state = widgetState(reading);
  assert.deepEqual(state, {
    decide: {
      ...reading.state.decide,
      undoable: true,
      available: true,
      unavailable: null,
    },
    pick: {
      units: {
        ada: { ...picked("ada"), undoable: false },
        grace: { ...picked("grace"), undoable: true },
      },
      available: false,
      unavailable: "no agent or server is available",
    },
    status: {
      ...reading.state.status,
      undoable: false,
      available: false,
      unavailable: null,
    },
  });
  assert.ok(Object.isFrozen(state.pick.units.ada), "the element can't write its state");
});

test("a plain data widget the markup binds to nothing is set its written <pre>", async () => {
  const { tag } = bound({ content: "data" });
  const sets = [];
  customElements.define(
    tag,
    class extends HTMLElement {
      set value(next) {
        sets.push(next);
      }
    },
  );
  const element = document.createElement(tag);
  element.innerHTML = "<pre>**Fixed** &lt;now&gt;\n</pre>";
  document.body.append(element);
  await settled();
  assert.deepEqual(sets, ["**Fixed** <now>\n"]);
  element.remove();
});

test("the page shows a delivery only once the drawing its setter announced is in", async () => {
  const { tag, accept, element: make } = bound();
  await accept("p1", { builds: "first" });
  const drawing = [];
  customElements.define(
    tag,
    class extends HTMLElement {
      set value(next) {
        const task = Promise.withResolvers();
        drawing.push(task);
        const complete = task.promise.then(() => {
          this.textContent = revision(next);
        });
        this.dispatchEvent(
          Object.assign(new Event("pending-task", { bubbles: true, composed: true }), {
            complete,
          }),
        );
      }
    },
  );
  const element = make();
  document.body.append(element);
  await settled();
  drawing.shift().resolve();
  const delivered = accept("p2", { builds: "second" });
  await settled();
  assert.equal(document.body.getAttribute("data-lf-data-version"), "p1");
  drawing.shift().resolve();
  await delivered;
  assert.equal(element.textContent, "second");
  assert.equal(document.body.getAttribute("data-lf-data-version"), "p2");
  element.remove();
});

test("a setter that throws is reported and owed again, and the other sets still land", async () => {
  const { tag, accept, element: make } = bound();
  await accept("f1", { builds: "good", words: "plain" });
  const notes = [];
  customElements.define(
    tag,
    class extends HTMLElement {
      set value(next) {
        if (this.failing) throw new Error(`cannot draw ${revision(next)}`);
        this.querySelector("output").value = revision(next);
      }
      set notes(next) {
        notes.push(revision(next));
      }
    },
  );
  const element = make({ source: "builds", notes: "words" });
  element.innerHTML = "<p>Authored words</p><output></output>";
  document.body.append(element);
  await settled();
  element.failing = true;
  const failures = await reported(async () => {
    await accept("f2", { builds: "bad", words: "plain" });
    await settled();
  });
  assert.deepEqual(failures, [[element, "cannot draw bad"]]);
  // The box stands after what the element holds, which is as it was drawn.
  assert.match(element.lastElementChild.textContent, /failed: cannot draw bad/);
  assert.equal(element.querySelector("p").textContent, "Authored words");
  assert.equal(element.querySelector("output").value, "good");
  // The input declared after the one that threw is still followed, and a pass that
  // sets it alone leaves the failure owed and shown.
  await reported(async () => {
    await accept("f3", { builds: "bad", words: "revised" });
    await settled();
  });
  assert.deepEqual(notes, ["plain", "revised"]);
  assert.ok(element.querySelector(".lf-error"));
  // The value that threw is set again by the next pass, changed or not.
  element.failing = false;
  await accept("f4", { builds: "bad", words: "final" });
  assert.equal(element.querySelector("output").value, "bad");
  assert.equal(element.querySelector(".lf-error"), null);
  element.remove();
});

test("the failure box stands in the tree that shows the element, or where the element puts it", async () => {
  const { tag, accept, element: make } = bound();
  await accept("s1", { builds: "bad" });
  customElements.define(
    tag,
    class extends HTMLElement {
      connectedCallback() {
        if (this.dataset.shadow === undefined) placesFailure(this, () => true);
        else if (!this.shadowRoot) this.attachShadow({ mode: "open" });
      }
      set value(next) {
        throw new Error(`cannot draw ${revision(next)}`);
      }
    },
  );
  const shadowed = make({ source: "builds", "data-shadow": "" });
  const placing = make();
  await reported(async () => {
    document.body.append(shadowed, placing);
    await settled();
  });
  assert.match(shadowed.shadowRoot.textContent, /failed: cannot draw bad/);
  assert.equal(shadowed.querySelector(".lf-error"), null);
  assert.equal(placing.querySelector(".lf-error"), null, "its own placer took the box");
  shadowed.remove();
  placing.remove();
});

test("an element that says lf-connect has its sets before the event returns", async () => {
  const { tag, accept, element: make } = bound();
  await accept("c1", { builds: "asked" });
  const seen = [];
  customElements.define(
    tag,
    class extends HTMLElement {
      connectedCallback() {
        const answered = !this.dispatchEvent(
          new Event("lf-connect", { bubbles: true, composed: true, cancelable: true }),
        );
        seen.push([answered, revision(this.value), this.state]);
      }
    },
  );
  const element = make();
  document.body.append(element);
  // It reads data only, so the `state` Leaf told it to wait for is an empty one.
  assert.deepEqual(seen, [[true, "asked", {}]]);
  element.remove();
});

test("a drawing an element announces by itself holds its region until it is in", async () => {
  const { tag, accept, element: make } = bound();
  await accept("d1", { builds: "drawn" });
  customElements.define(tag, class extends HTMLElement {});
  const element = make();
  document.body.append(element);
  await settled();
  const pending = () =>
    readApplicationPresentation().pending.filter((region) =>
      region.startsWith(`element:${tag}:`),
    );
  assert.deepEqual(pending(), []);
  const drawing = Promise.withResolvers();
  element.dispatchEvent(
    Object.assign(new Event("pending-task", { bubbles: true, composed: true }), {
      complete: drawing.promise,
    }),
  );
  assert.equal(pending().length, 1, "its own region, and no preparation beside it");
  // A second drawing claims the region again, and the claim keeps the first.
  const later = Promise.withResolvers();
  element.dispatchEvent(
    Object.assign(new Event("pending-task", { bubbles: true, composed: true }), {
      complete: later.promise,
    }),
  );
  later.resolve();
  await settled();
  assert.equal(pending().length, 1, "the earlier drawing is still waited for");
  drawing.resolve();
  await settled();
  assert.deepEqual(pending(), []);
  element.remove();
});

test("an element says its failure with `error`, and `lf-error` on the window tells the user", async () => {
  const { errorsReading, dismissErrors } = await import("/runtime/transport/errors.js");
  const host = document.body.appendChild(document.createElement("section"));
  const part = host
    .attachShadow({ mode: "open" })
    .appendChild(document.createElement("div"));
  const failures = [];
  const report = (event) => failures.push(failureOf(event));
  window.addEventListener("error", report);
  try {
    // The failure is the element's the event began at, and its reason the event's
    // error, or its message where it carries none.
    const reason = new Error("cannot draw this file");
    part.dispatchEvent(
      new ErrorEvent("error", { error: reason, bubbles: true, composed: true }),
    );
    host.dispatchEvent(
      new ErrorEvent("error", { message: "no rows", bubbles: true, composed: true }),
    );
    assert.deepEqual(failures, [
      { element: part, reason },
      { element: host, reason: "no rows" },
    ]);
    dismissErrors();
    window.dispatchEvent(
      new CustomEvent("lf-error", {
        detail: "Wait for the current edit to finish saving",
      }),
    );
    assert.deepEqual(
      errorsReading().map(({ message, subject }) => [message, subject]),
      [["Wait for the current edit to finish saving", null]],
    );
  } finally {
    window.removeEventListener("error", report);
    dismissErrors();
    host.remove();
  }
});
