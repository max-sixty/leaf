/* Placement against a fresh resolution, through seeded runs of the changes a page's
   scripts make: words written, taken out and put back, a second copy written, a fence
   made or taken away, ids swapped and renamed, text wrapped in a section of its own,
   moved to another or replaced by the same words, and a declared shadow stage replaced
   by another holding the same ids, filled in place or before it is put there. After
   each change, in the task that made it as well as after the watcher delivers it, on
   pages with threads and on pages holding only a draft, every thread's placement, the
   draft's and a saved draft's, stands
   where a resolution of its anchor read afresh puts it: no reader reads placement older
   than the page (annotations/anchor-placement.js, `settle`), a reading kept from it included. A fresh resolution names the quote
   with a space before it, which the page's index of quotes doesn't keep, so it reads
   the page by a pass of its own (readings/passages.js, `copiesOf`). */
// Stages watched as the page's are, which the reading watcher hears inside.
import "/runtime/stage-integration.js";
import assert from "node:assert/strict";
import test from "node:test";

import { createAnchorPlacement } from "/runtime/annotations/anchor-placement.js";
import { kept } from "/runtime/state/kept.js";
import {
  resolveAnchor,
  setAnchoringReady,
} from "/runtime/readings/anchor-resolution.js";
import { neighbourhood, pageText, spanIn } from "/runtime/readings/passages.js";
import { registry } from "/runtime/state/registry.js";
import { shadowStage } from "/runtime/dom/shadow-stage.js";

import { random } from "./seeded.mjs";

const STAGED = '<p id="s4">Mu nu shared phrase xi.</p>';
const PAGE =
  '<main id="all"><section id="s1"><p>First alpha beta gamma. <span>The shared ' +
  'phrase here.</span></p></section><section id="s2"><p>Second shared phrase. ' +
  'Delta <span>epsilon zeta</span> eta.</p></section><section id="s3"><p>Theta alpha ' +
  `beta iota.</p><p>Kappa shared phrase lambda.</p></section><lf-staged>${STAGED}` +
  "</lf-staged></main>";
const WORDS = ["alpha", "beta", "shared", "phrase", "zeta", "x", " ", "."];
const IDS = ["s1", "s2", "s3", "s4", "all", "x"];

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
    "lf-staged": {
      shadow: true,
    },
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
    // The draft a user opened on a passage, which no thread names yet, and a comment
    // they saved and haven't sent.
    const drafted = { section: "s3", quote: "Theta alpha beta" };
    const saved = { section: "s2", quote: "Second shared phrase" };
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
      saved: [{ context: "kept", anchor: saved }],
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
    const placedNow = () => ({
      threads: threads.map((thread) => where(placement.placedAt(thread.id))),
      draft: where(placement.pendingAt()),
      saved: where(placement.savedAt("kept")),
    });
    // A reading kept from placement (state/kept.js, `kept`), which no change leaves older
    // than placement, a saved draft's placement included.
    const keptPlaces = kept(placedNow);
    keptPlaces();
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
        where(placement.savedAt("kept")),
        where(fresh(saved)),
        `seed ${seed}, step ${step} (${kind}), the saved draft`,
      );
      assert.deepEqual(
        keptPlaces(),
        placedNow(),
        `seed ${seed}, step ${step} (${kind}), a reading kept from placement`,
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

test("placement keeps a range over a passage's words, a thread's and the draft's", () => {
  // The anchor paint marks a passage from its `ranges`, a thread's and the draft's
  // alike. A reading that moves nothing keeps the ranges it had, so the paint keeps
  // the highlights and the index it built of them. A browser also moves a live range
  // with words written ahead of it, which this document doesn't
  // (test_render_anchors.py holds that for a thread's mark).
  document.body.innerHTML =
    '<main><p id="a">The nightly export keeps one file per tenant.</p>' +
    '<p id="b">Both exports run side by side each morning.</p></main>';
  setAnchoringReady(true);
  const placement = createAnchorPlacement();
  const thread = {
    id: "t",
    key: "t",
    anchor: { section: "a", quote: "one file per tenant" },
    msgs: [],
    resolved: false,
    root: {},
  };
  const read = () =>
    placement.read({
      threads: [thread],
      draft: {
        open: true,
        anchor: { section: "b", quote: "side by side" },
        about: null,
        drawing: null,
      },
      actionAnchor: null,
      saved: [],
    });
  read();
  const [placed] = placement.placedAt("t").ranges;
  const [drafted] = placement.pendingAt().ranges;
  assert.equal(String(placed), "one file per tenant");
  assert.equal(String(drafted), "side by side");
  read();
  assert.equal(placement.placedAt("t").ranges[0], placed);
  assert.equal(placement.pendingAt().ranges[0], drafted);
  // Words taken out of the passage itself leave the draft on what held them.
  const words = /** @type {Text} */ (document.getElementById("b")?.firstChild);
  words.data = "Both exports run.";
  assert.equal(placement.pendingAt()?.status, "fallback");
  assert.equal(placement.pendingAt()?.place, document.getElementById("b"));
  document.body.replaceChildren();
});

// A saved draft on a part of a picture stands on the picture while the picture draws
// no element for the part, and on the part at the first read after it draws one, as a
// widget's draw is followed by a presentation's read, and a reading kept from placement,
// as the draft's margin entry is drawn from one, reads it again.
test("a saved draft on a part the picture draws later stands on the part at the next read", () => {
  registry["lf-plot"] = { visual: { prefixes: ["point:"] } };
  document.body.innerHTML =
    '<main><lf-plot id="plot"><svg><circle id="p"></circle></svg></lf-plot></main>';
  setAnchoringReady(true);
  const plot = /** @type {Element} */ (document.getElementById("plot"));
  const point = /** @type {Element} */ (document.getElementById("p"));
  let drawn = false;
  plot.lfParts = {
    read: () => [],
    find: (id) =>
      drawn && id === "point:p" ? { id, element: point, label: "x 1" } : null,
    label: (id) => (id === "point:p" ? "x 1" : null),
  };
  const placement = createAnchorPlacement();
  const read = () =>
    placement.read({
      threads: [],
      draft: { open: false, anchor: null, about: null, drawing: null },
      actionAnchor: null,
      saved: [{ context: "kept", anchor: { section: "plot", visual: "point:p" } }],
    });
  try {
    read();
    const savedPlace = kept(() => placement.savedAt("kept"));
    assert.equal(savedPlace()?.element, plot);
    assert.equal(savedPlace()?.label, "x 1");
    drawn = true;
    read();
    assert.equal(savedPlace()?.element, point);
  } finally {
    delete registry["lf-plot"];
    document.body.replaceChildren();
  }
});

// Those who hear which threads placement placed again hear only threads: a saved draft
// placed again, which a later read no longer holds by the time they are told, is none.
test("placement's hearers never hear a saved draft as a thread", async () => {
  document.body.innerHTML =
    '<main><p id="a">The nightly export keeps one file per tenant.</p></main>';
  setAnchoringReady(true);
  const placement = createAnchorPlacement();
  /** @type {string[]} */
  const heard = [];
  placement.hearPlaced((change) => heard.push(...change.threads));
  /** @param {{context: string, anchor: {section: string, quote: string}}[]} saved */
  const read = (saved) =>
    placement.read({
      threads: [],
      draft: { open: false, anchor: null, about: null, drawing: null },
      actionAnchor: null,
      saved,
    });
  try {
    read([{ context: "kept", anchor: { section: "a", quote: "one file per tenant" } }]);
    const words = /** @type {Text} */ (document.getElementById("a")?.firstChild);
    words.data = "The nightly export keeps nothing.";
    assert.equal(placement.savedAt("kept")?.status, "fallback");
    read([]);
    await new Promise((done) => setTimeout(done, 0));
    assert.deepEqual(heard, []);
  } finally {
    document.body.replaceChildren();
  }
});
