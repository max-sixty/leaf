/* Placement against a fresh resolution, through seeded runs of the changes a page's
   scripts make: words written, taken out and put back, a second copy written, a fence
   made or taken away, ids swapped and renamed, text wrapped in a section of its own,
   moved to another or replaced by the same words, and a declared shadow stage replaced
   by another holding the same ids, filled in place or before it is put there. After
   each change, in the task that made it as well as after the watcher delivers it, on
   pages with threads and on pages holding only a draft, every thread's placement, and
   the draft's, stands
   where a resolution of its anchor read afresh puts it: no reader reads placement older
   than the page (anchor-placement.js, `settle`). A fresh resolution names the quote
   with a space before it, which the page's index of quotes doesn't keep, so it reads
   the page by a pass of its own (passages.js, `copiesOf`). */
// Stages watched as the page's are, which the reading watcher hears inside.
import "/runtime/stage-integration.js";
import assert from "node:assert/strict";
import test from "node:test";

import { createAnchorPlacement } from "/runtime/anchor-placement.js";
import { resolveAnchor, setAnchoringReady } from "/runtime/anchor-resolution.js";
import { neighbourhood, pageText, spanIn } from "/runtime/passages.js";
import { registry } from "/runtime/registry.js";
import { shadowStage } from "/runtime/shadow-stage.js";

const STAGED = '<p id="s4">Mu nu shared phrase xi.</p>';
const PAGE =
  '<main id="all"><section id="s1"><p>First alpha beta gamma. <span>The shared ' +
  'phrase here.</span></p></section><section id="s2"><p>Second shared phrase. ' +
  'Delta <span>epsilon zeta</span> eta.</p></section><section id="s3"><p>Theta alpha ' +
  `beta iota.</p><p>Kappa shared phrase lambda.</p></section><lf-staged>${STAGED}` +
  "</lf-staged></main>";
const WORDS = ["alpha", "beta", "shared", "phrase", "zeta", "x", " ", "."];
const IDS = ["s1", "s2", "s3", "s4", "all", "x"];

// A seeded generator, so a failure names its run.
/** @param {number} seed */
function random(seed) {
  let s = seed >>> 0;
  return () => (s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 2 ** 32;
}

/** @param {{section: string, quote?: string, prefix?: string, suffix?: string}} anchor */
const fresh = (anchor) =>
  resolveAnchor(anchor.quote ? { ...anchor, quote: ` ${anchor.quote}` } : anchor);
/** @param {any} found */
const where = (found) =>
  found?.kind === "passage"
    ? found.segments.map(
        (
          /** @type {{node: Text, start: number, end: number}} */ { node, start, end },
        ) => [node, start, end],
      )
    : found?.kind === "element"
      ? found.element
      : null;
// The page, with its stage holding its words in a declared shadow tree.
const load = () => {
  document.body.innerHTML = PAGE;
  stage(/** @type {Element} */ (document.querySelector("lf-staged")));
};
/** @param {Element} host */
const stage = (host) => shadowStage(host, [...host.childNodes]);

test("placement stands where a fresh resolution does, after every change", async () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "placement-seeded" },
  });
  for (let seed = 1; seed <= 7; seed++) {
    const next = random(seed);
    /** @template T @param {readonly T[]} list @returns {T} */
    const pick = (list) => /** @type {T} */ (list[Math.floor(next() * list.length)]);
    load();
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
      { section: "s4", quote: "shared phrase" },
      { section: "s4" },
    ];
    // The draft a user opened on a passage, which no thread names yet.
    const drafted = { section: "s3", quote: "Theta alpha beta" };
    assert.ok(spanIn(reading, fresh(anchors[2]).segments)[0] > 0, "the second copy");
    // The last runs hold only the draft, as a page before its first thread does.
    const threads = (seed > 5 ? [] : anchors).map((anchor, at) => ({
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
      draft: { open: true, anchor: drafted, about: null, drawing: null },
      actionAnchor: null,
    });
    const texts = () => {
      const found = [];
      for (const root of [
        document.body,
        document.querySelector("lf-staged")?.shadowRoot,
      ])
        if (root) {
          const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
          for (let text = walker.nextNode(); text; text = walker.nextNode())
            found.push(text);
        }
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
        pick([...document.querySelectorAll("p")]).append(
          ` ${pick(anchors).quote ?? ""}`,
        );
      },
      restore() {
        if (next() < 0.5) load();
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
      restage() {
        const old = document.querySelector("lf-staged");
        const host = document.createElement("lf-staged");
        host.innerHTML = STAGED;
        // Filled before it is put in place, and read in between, or filled in place.
        const early = next() < 0.5;
        if (early) {
          stage(host);
          placement.pendingAt();
        }
        if (old) old.replaceWith(host);
        else document.querySelector("main")?.append(host);
        if (!early) stage(host);
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
      assert.deepEqual(
        where(placement.pendingAt()),
        where(fresh(drafted)),
        `seed ${seed}, step ${step} (${kind}), the draft`,
      );
    }
  }
  document.body.replaceChildren();
});
