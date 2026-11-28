/* Which section of the contents each open thread, On Me item and change counts in
   (toc-marks.js), and the words a row's link previews them in. How the marks draw, and
   that the widget reads them again as the readings change, is the browser's to show
   (`tests/browser/widgets/test_contents_and_glosses.py`). */
import "/runtime/stage-integration.js";
import assert from "node:assert/strict";
import test from "node:test";
import { readOutline } from "../../packages/default/widgets/lf-toc.js";
import { marksWords, sectionMarks } from "../../packages/default/widgets/toc-marks.js";

// The contents of `markup` as lf-toc lists them, and each section's marks, by the words
// of the heading leading it ("" for an untitled start), from threads about the elements
// `threads` names (`{id, resolved}`), On Me items at the widgets `onMe` names, and
// changes over the blocks each of `changes` names, or a removal whose gap stands
// `before`, `after` or `in` the element `at` names.
/** @param {string} markup
 * @param {{threads?: {id: string, resolved?: boolean}[], onMe?: string[], changes?: {blocks?: string[], at?: string, gap?: "before" | "after" | "in"}[], toc?: string}} items */
function marked(markup, { threads = [], onMe = [], changes = [], toc = "" } = {}) {
  document.body.innerHTML = `<aside><lf-toc id="contents" ${toc}></lf-toc><p id="aside-note">Aside.</p></aside><main>${markup}</main>`;
  const host = /** @type {HTMLElement} */ (document.querySelector("lf-toc"));
  const { main, sections } = readOutline(
    host,
    (/** @type {Element} */ heading) => heading.textContent ?? "",
  );
  const byId = (/** @type {string} */ id) =>
    /** @type {Element} */ (document.getElementById(id));
  const marks = sectionMarks(/** @type {Element} */ (main), sections, {
    threads: threads.map(({ id, resolved }) => ({ resolved, anchor: { section: id } })),
    onMe: onMe.map((id) => ({ source: { id } })),
    changes: changes.map(({ blocks = [], at = blocks[0] ?? "", gap = null }) => ({
      blocks: blocks.map(byId),
      at: byId(at),
      gap,
    })),
  });
  return Object.fromEntries(
    [...marks].map(([heading, held]) => [heading?.textContent ?? "", held]),
  );
}

test("an item counts in the section of the heading over it, and before any in the start's", () => {
  assert.deepEqual(
    marked(
      `<h1>Runbook</h1><p id="lede">Why.</p>
      <h2>Prepare</h2><p id="prepare">Book it.</p>
      <h3>Check access</h3><p id="access">Ask.</p><lf-options id="access-question"></lf-options>
      <h2>Switch</h2><p id="switch">Restart.</p><p id="switch-more">Watch.</p>`,
      {
        threads: [
          { id: "lede" },
          { id: "prepare" },
          { id: "access" },
          { id: "access" },
          { id: "switch", resolved: true },
          { id: "aside-note" },
        ],
        onMe: ["access-question"],
        changes: [
          { blocks: ["access", "switch"] },
          { at: "switch-more", gap: "before" },
        ],
      },
    ),
    {
      Runbook: { threads: 1, onMe: 0, changes: 0 },
      Prepare: { threads: 1, onMe: 0, changes: 0 },
      "Check access": { threads: 2, onMe: 1, changes: 1 },
      Switch: { threads: 0, onMe: 0, changes: 2 },
    },
  );
});

test("a removal counts in the section it was taken from, a section's end included", () => {
  assert.deepEqual(
    marked(
      `<h2>Prepare</h2><p id="prepare">Book it.</p>
      <h2 id="switch-heading">Switch</h2><p id="switch">Restart.</p>
      <h3>Check</h3><div id="check-notes"></div>`,
      {
        changes: [
          // Prepare's last paragraph, taken out: its gap stands before Switch's heading.
          { at: "switch-heading", gap: "before" },
          { at: "prepare", gap: "after" },
          { at: "switch", gap: "before" },
          { at: "check-notes", gap: "in" },
        ],
      },
    ),
    {
      Prepare: { threads: 0, onMe: 0, changes: 2 },
      Switch: { threads: 0, onMe: 0, changes: 1 },
      Check: { threads: 0, onMe: 0, changes: 1 },
    },
  );
  // A gap before a section stands where the reading was before it, not under the
  // heading the section opens with.
  assert.deepEqual(
    marked(
      `<h2>Prepare</h2><p id="prepare">Book it.</p>
      <section id="switch"><h2>Switch</h2><p>Restart.</p></section>`,
      { changes: [{ at: "switch", gap: "before" }] },
    ),
    { Prepare: { threads: 0, onMe: 0, changes: 1 } },
  );
});

test("a heading the contents leave out counts in the section listed above it", () => {
  assert.deepEqual(
    marked(
      `<h2>Prepare</h2><p id="prepare">Book it.</p>
      <h3>Check access</h3><p id="access">Ask.</p>
      <h2>Switch</h2><p id="switch">Restart.</p>`,
      {
        threads: [{ id: "prepare" }, { id: "access" }, { id: "switch" }],
        toc: 'max-level="2"',
      },
    ),
    {
      Prepare: { threads: 2, onMe: 0, changes: 0 },
      Switch: { threads: 1, onMe: 0, changes: 0 },
    },
  );
});

test("a thread about a whole section counts in it, and one in a nested section in that", () => {
  assert.deepEqual(
    marked(
      `<section id="prepare"><h2>Prepare</h2><p>Book it.</p>
        <section id="access"><h3>Check access</h3><p id="ask">Ask.</p></section>
        <p id="after">Then confirm.</p></section>
      <section id="switch"><h2>Switch</h2><p>Restart.</p></section>`,
      {
        threads: [{ id: "prepare" }, { id: "ask" }, { id: "after" }, { id: "switch" }],
      },
    ),
    {
      // What follows a nested section before the next heading is in its stretch, as
      // the map draws it.
      Prepare: { threads: 1, onMe: 0, changes: 0 },
      "Check access": { threads: 2, onMe: 0, changes: 0 },
      Switch: { threads: 1, onMe: 0, changes: 0 },
    },
  );
});

test("a thread about a whole question or card counts in the row of the heading titling it", () => {
  assert.deepEqual(
    marked(
      `<h1>Plan</h1><p id="lede">Why.</p>
      <section id="decision"><section id="ask">
        <hgroup id="ask-title"><p>Decision 1</p><h2>Which store?</h2></hgroup>
        <p id="ask-context">Two stores fit.</p>
      </section></section>
      <section id="bare-ask">
        <hgroup><p>Decision 2</p><h2>Which region?</h2></hgroup>
        <p>One region fits.</p>
      </section>
      <h2>Cards</h2>
      <article id="card"><h3>First card</h3><p>Its words.</p></article>`,
      {
        threads: [
          { id: "decision" },
          { id: "ask" },
          { id: "ask-title" },
          { id: "ask-context" },
          { id: "bare-ask" },
          { id: "card" },
        ],
      },
    ),
    {
      "Which store?": { threads: 4, onMe: 0, changes: 0 },
      "Which region?": { threads: 1, onMe: 0, changes: 0 },
      "First card": { threads: 1, onMe: 0, changes: 0 },
    },
  );
});

test("a section's marks read as its counts, and none read as nothing", () => {
  assert.equal(
    marksWords({ threads: 2, onMe: 1, changes: 1 }),
    "2 threads · 1 waiting on me · 1 change",
  );
  assert.equal(marksWords({ threads: 0, onMe: 2, changes: 0 }), "2 waiting on me");
  assert.equal(marksWords(undefined), "");
});

test("what follows a question before the next heading counts in the question's row", () => {
  // As the map draws the question's stretch, a note after it, a removal after it and a
  // heading after it inside the section around it agree.
  assert.deepEqual(
    marked(
      `<h1>Plan</h1><h2>Context</h2><p>Why.</p>
      <section id="ask"><hgroup><p>Decision 1</p><h2>Which store?</h2></hgroup>
        <p>Two fit.</p></section>
      <p id="after">A note after the question.</p>
      <section id="s"><section><h2>Which region?</h2></section>
        <h3>Notes</h3><p id="notes">Its words.</p></section>`,
      {
        threads: [{ id: "after" }, { id: "s" }, { id: "notes" }],
        changes: [{ at: "ask", gap: "after" }],
      },
    ),
    {
      "Which store?": { threads: 1, onMe: 0, changes: 1 },
      "Which region?": { threads: 1, onMe: 0, changes: 0 },
      Notes: { threads: 1, onMe: 0, changes: 0 },
    },
  );
});
