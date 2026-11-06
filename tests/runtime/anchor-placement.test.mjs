/* Placement against a fresh resolution, through seeded runs of the changes a page's
   scripts make: words written, taken out and put back, a second copy written, a fence
   made or taken away, ids swapped and renamed, text wrapped in a section of its own,
   moved to another or replaced by the same words. After each change, in the task that
   made it as well as after the watcher delivers it, every thread's placement stands
   where a resolution of its anchor read afresh puts it: no reader reads placement older
   than the page (anchor-placement.js, `settle`). A fresh resolution names the quote
   with a space before it, which the page's index of quotes doesn't keep, so it reads
   the page by a pass of its own (passages.js, `copiesOf`). */
import assert from "node:assert/strict";
import test from "node:test";

import { createAnchorPlacement } from "/runtime/anchor-placement.js";
import { resolveAnchor, setAnchoringReady } from "/runtime/anchor-resolution.js";
import { neighbourhood, pageText, spanIn } from "/runtime/passages.js";

const PAGE =
  '<main id="all"><section id="s1"><p>First alpha beta gamma. <span>The shared ' +
  'phrase here.</span></p></section><section id="s2"><p>Second shared phrase. ' +
  'Delta <span>epsilon zeta</span> eta.</p></section><section id="s3"><p>Theta alpha ' +
  "beta iota.</p><p>Kappa shared phrase lambda.</p></section></main>";
const WORDS = ["alpha", "beta", "shared", "phrase", "zeta", "x", " ", "."];
const IDS = ["s1", "s2", "s3", "all", "x"];

// A seeded generator, so a failure names its run.
/** @param {number} seed */
function random(seed) {
  let s = seed >>> 0;
  return () => (s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 2 ** 32;
}

/** @param {{section: string, quote: string, prefix?: string, suffix?: string}} anchor */
const fresh = (anchor) => resolveAnchor({ ...anchor, quote: ` ${anchor.quote}` });
/** @param {any} found */
const where = (found) =>
  found?.kind === "passage"
    ? found.segments.map(
        (
          /** @type {{node: Text, start: number, end: number}} */ { node, start, end },
        ) => [node, start, end],
      )
    : (found?.kind ?? null);

test("placement stands where a fresh resolution does, after every change", async () => {
  for (let seed = 1; seed <= 5; seed++) {
    const next = random(seed);
    /** @template T @param {readonly T[]} list @returns {T} */
    const pick = (list) => /** @type {T} */ (list[Math.floor(next() * list.length)]);
    document.body.innerHTML = PAGE;
    setAnchoringReady(true);
    // One anchor told from its other copy by its context, as a capture writes it.
    const reading = pageText();
    const second = [...reading.raw.matchAll(/alpha beta/g)][1]?.index ?? 0;
    const anchors = [
      { section: "s1", quote: "alpha beta" },
      { section: "s2", quote: "shared phrase" },
      {
        section: "all",
        quote: "alpha beta",
        prefix: neighbourhood(reading, second, 12, true),
        suffix: neighbourhood(reading, second + "alpha beta".length, 12, false),
      },
      { section: "s2", quote: "Delta epsilon zeta eta" },
      { section: "s3", quote: "shared phrase lambda" },
      { section: "all", quote: "gamma. The shared" },
    ];
    assert.ok(spanIn(reading, fresh(anchors[2]).segments)[0] > 0, "the second copy");
    const threads = anchors.map((anchor, at) => ({
      id: `t${at}`,
      key: `t${at}`,
      anchor,
      msgs: [],
      resolved: false,
      root: {},
    }));
    const placement = createAnchorPlacement();
    placement.read({
      threads,
      draft: { open: false, anchor: null, about: null, drawing: null },
      actionAnchor: null,
    });
    const texts = () => {
      const found = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let text = walker.nextNode(); text; text = walker.nextNode())
        found.push(text);
      return /** @type {Text[]} */ (found);
    };
    const elements = () => [...document.querySelectorAll("main, section, p, span")];
    const changes = {
      write() {
        const text = pick(texts());
        text.insertData(Math.floor(next() * (text.data.length + 1)), pick(WORDS));
      },
      cut() {
        const text = pick(texts());
        const at = Math.floor(next() * text.data.length);
        text.deleteData(at, 1 + Math.floor(next() * 6));
      },
      again() {
        pick([...document.querySelectorAll("p")]).append(` ${pick(anchors).quote}`);
      },
      restore() {
        if (next() < 0.5) document.body.innerHTML = PAGE;
        else {
          const text = pick(texts());
          text.data = text.data.replace(/x/g, "");
        }
      },
      fence() {
        const span = document.querySelector("span");
        if (span?.isContentEditable) span.removeAttribute("contenteditable");
        else span?.setAttribute("contenteditable", "true");
      },
      swap() {
        const [a, b] = [pick(elements()), pick(elements())];
        const id = a.id;
        a.id = b.id;
        b.id = id;
      },
      rename() {
        pick(elements()).id = pick(IDS);
      },
      wrap() {
        const text = pick(texts());
        const span = Object.assign(document.createElement("span"), { id: pick(IDS) });
        text.replaceWith(span);
        span.append(text);
      },
      move() {
        pick([...document.querySelectorAll("p")]).append(pick(texts()));
      },
      replace() {
        const text = pick(texts());
        text.replaceWith(document.createTextNode(text.data));
      },
    };
    const kinds = Object.keys(changes);
    for (let step = 0; step < 400; step++) {
      const kind = /** @type {keyof typeof changes} */ (pick(kinds));
      changes[kind]();
      // Read in the task that made the change, or after the watcher delivered it.
      if (next() < 0.5) await new Promise((done) => setTimeout(done, 0));
      for (const [at, thread] of threads.entries())
        assert.deepEqual(
          where(placement.placedAt(thread.id)),
          where(fresh(anchors[at] ?? thread.anchor)),
          `seed ${seed}, step ${step} (${kind}), thread ${at}`,
        );
    }
  }
  document.body.replaceChildren();
});
