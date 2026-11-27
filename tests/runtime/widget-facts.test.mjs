/* A tab's word on the facts its widgets work out (`reportFacts`): after each server
   reading or document it adopts, it sends what differs from what the page keeps, once,
   and nothing for a widget its own gesture still speaks for. Each case adopts a whole
   reading the server folded (`tests/served_records.py`) and sets only the kept facts
   the case is about, so the comparison is the one a tab makes after a version or
   another tab's act reached it. */
import assert from "node:assert/strict";
import test from "node:test";
import { adoptRegistry } from "/runtime/state/registry.js";
import { stageAuthoredStates } from "/runtime/records/projection/authored.js";
import { stageWidgetDescriptors } from "/runtime/records/widget-descriptors.js";
import { applicationState, readApplication } from "/runtime/state/semantic-state.js";
import { reportFacts } from "/runtime/host/widget-facts.js";
import { servedReading } from "../served.mjs";

// A plain widget that asks, whose class works out from its markup whether it is
// answered and how many steps it counts.
adoptRegistry({
  $layer: { generation: "widget-facts" },
  "lf-test-tally": {
    attributes: {
      properties: { ready: { type: "boolean" }, count: { type: "string" } },
      required: ["id"],
    },
    content: "markup",
    verbs: { mark: { unit: "widget", detail: {} } },
    awaits: { value: "mark" },
    facts: { answered: { type: "boolean" }, count: { type: "integer" } },
  },
});
customElements.define(
  "lf-test-tally",
  class extends HTMLElement {
    /** @param {unknown} _state @param {Element} element */
    static answered(_state, element) {
      return element.hasAttribute("ready");
    }
    /** @param {unknown} _state @param {Element} element */
    static count(_state, element) {
      return Number(element.getAttribute("count") ?? 0);
    }
  },
);

const served = servedReading("queues on both sides");
const [view] = Object.values(served.browser.views);
// Each version a case shows gets the next revision, as a page's do.
let revisions = 0;

/** `markup` as a new version's document, captured as Leaf does before upgrade. */
function shown(/** @type {string} */ markup) {
  document.body.innerHTML = markup;
  const { descriptors } = stageWidgetDescriptors(document.body);
  return {
    ...readApplication().document,
    revision: ++revisions,
    authored: stageAuthoredStates(document.body),
    descriptors,
  };
}

/** Adopt the server's reading of `page`, the shown document, with `facts` as the
 * facts the page keeps, while the version `newest` is the page's newest. */
function reading(
  /** @type {Record<string, Record<string, unknown>>} */ facts,
  /** @type {ReturnType<typeof shown>} */ page = readApplication().document,
  newest = page.revision,
) {
  const state = structuredClone(served);
  const revision = /** @type {number} */ (page.revision);
  state.browser.views = {
    [revision]: { ...structuredClone(view), basis: { ...view.basis, revision }, facts },
  };
  state.active.revision = newest;
  assert.equal(applicationState.adopt(state, page), true);
}

/** @type {unknown[]} */
const sent = [];
// What the next send's answer says of it.
let delivered = /** @type {"accepted" | "refused" | "unreached"} */ ("accepted");
reportFacts((event) => {
  sent.push(event);
  return Promise.resolve(delivered);
});
const tally = (/** @type {Record<string, unknown>} */ facts) => ({
  kind: "facts",
  widget: "tally",
  revision: readApplication().document.revision,
  through: served.browser.basis.through_seq,
  facts,
});

test("a tab says the facts that differ from what the page keeps, once, and stops once they agree", () => {
  // The page kept the word of a state this markup no longer holds, as when a version
  // reached the widget: the tab sends each fact that differs.
  reading(
    { tally: { answered: false } },
    shown('<lf-test-tally id="tally" ready count="3"></lf-test-tally>'),
  );
  assert.deepEqual(sent.splice(0), [tally({ answered: true, count: 3 })]);
  // Another reading before the page has taken the word sends nothing again.
  reading({ tally: { answered: false } });
  assert.deepEqual(sent.splice(0), []);
  // Once the page keeps what the widget says, there is nothing to say, and another
  // tab's different word draws no second one: the two tabs say theirs once each.
  reading({ tally: { answered: true, count: 3 } });
  reading({ tally: { answered: false, count: 3 } });
  assert.deepEqual(sent.splice(0), []);
  // A version that changes the markup moves the facts again, and only the one that
  // differs goes.
  reading(
    { tally: { answered: true, count: 3 } },
    shown('<lf-test-tally id="tally" ready count="4"></lf-test-tally>'),
  );
  assert.deepEqual(sent.splice(0), [tally({ count: 4 })]);
});

test("a word that never reached the page is said again at the next reading", async () => {
  delivered = "unreached";
  reading({}, shown('<lf-test-tally id="tally" count="2"></lf-test-tally>'));
  assert.deepEqual(sent.splice(0), [tally({ count: 2 })]);
  delivered = "accepted";
  await Promise.resolve();
  // The next reading, which moves something else, has the tab say it again; once it
  // reached the page, a reading after says nothing.
  reading({ tally: {} });
  assert.deepEqual(sent.splice(0), [tally({ count: 2 })]);
  reading({});
  assert.deepEqual(sent.splice(0), []);
});

test("a refused word is said again once the widget moved, and only then", async () => {
  delivered = "refused";
  reading({}, shown('<lf-test-tally id="tally" count="5"></lf-test-tally>'));
  assert.deepEqual(sent.splice(0), [tally({ count: 5 })]);
  await Promise.resolve();
  // Refused for good, as for a fact the widget doesn't declare: readings that leave
  // the widget as it was draw no second word.
  reading({ other: { count: 1 } });
  reading({ other: { count: 2 } });
  assert.deepEqual(sent.splice(0), []);
  // Refused as stale: another tab's word on the widget landed, and the widget's word
  // still differs from it, so the tab says it again.
  delivered = "accepted";
  reading({ tally: { count: 4 } });
  assert.deepEqual(sent.splice(0), [tally({ count: 5 })]);
});

test("an unsaid word reads as the question asked, so a widget that asks says nothing until answered", () => {
  reading({ tally: { count: 0 } }, shown('<lf-test-tally id="tally"></lf-test-tally>'));
  assert.deepEqual(sent.splice(0), []);
});

test("a gesture still on its way speaks for its widget until it leaves the ledger, and an older version speaks for none", () => {
  const page = shown('<lf-test-tally id="tally" ready count="1"></lf-test-tally>');
  applicationState.enqueue(
    {
      kind: "action",
      widget: "tally",
      action: "mark",
      detail: {},
      revision: page.revision,
      attempt: "a1",
    },
    "now",
  );
  reading({ tally: { count: 1 } }, page);
  assert.deepEqual(sent.splice(0), []);
  // The gesture leaves the ledger with no reading after it, and the tab says the word
  // the page still lacks.
  applicationState.refuse("a1");
  assert.deepEqual(sent.splice(0), [tally({ answered: true })]);
  // A tab showing a version older than the newest speaks for none of its widgets.
  reading({ tally: { count: 2 } }, page, /** @type {number} */ (page.revision) + 1);
  assert.deepEqual(sent.splice(0), []);
});
