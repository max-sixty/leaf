/* Which section of the contents each open thread, On me item and change counts in
   (toc-marks.js), and the words a row's link previews them in. How the marks draw, and
   that the widget reads them again as the readings change, is the browser's to show
   (`tests/browser/widgets/test_contents_and_glosses.py`). */
import "/runtime/stage-integration.js";
import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/vendor/lit.js";
import { drawToc } from "../../packages/default/widgets/toc-view.js";
import { marksWords, sectionMarks } from "../../packages/default/widgets/toc-marks.js";

// The contents of `markup` as lf-toc lists them, and each section's marks, by the words
// of the heading leading it ("" for an untitled start), from threads about the elements
// `threads` names (`{id, resolved}`), On me items at the widgets `onMe` names, and
// changes over the blocks each of `changes` names, or a removal whose gap stands
// `before`, `after` or `in` the element `at` names.
/** @param {string} markup
 * @param {{threads?: {id: string, resolved?: boolean}[], onMe?: string[], changes?: {blocks?: string[], at?: string, gap?: "before" | "after" | "in"}[], toc?: string}} items */
function marked(markup, { threads = [], onMe = [], changes = [], toc = "" } = {}) {
  document.body.innerHTML = `<aside><lf-toc id="contents" ${toc}></lf-toc><p id="aside-note">Aside.</p></aside><main>${markup}</main>`;
  const host = /** @type {HTMLElement} */ (document.querySelector("lf-toc"));
  const reading = {
    label: (/** @type {Element} */ heading) => heading.textContent ?? "",
    chrome: () => false,
  };
  const drawing = drawToc(host, reading);
  render(drawing.render(reading), host, { host });
  const main = /** @type {Element} */ (document.querySelector("main"));
  const byId = (/** @type {string} */ id) =>
    /** @type {Element} */ (document.getElementById(id));
  const marks = sectionMarks(main, drawing.sections(), {
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
      Prepare: { threads: 2, onMe: 0, changes: 0 },
      "Check access": { threads: 1, onMe: 0, changes: 0 },
      Switch: { threads: 1, onMe: 0, changes: 0 },
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
