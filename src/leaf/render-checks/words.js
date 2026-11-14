import { canvas2D, pageScroller, scrollLimit } from "/runtime/widget-api.js";
import { says } from "/runtime/widget-api.js";
import {
  colourableAs,
  colouredAs,
  coverBoxes,
  inPage,
  quoteFrom,
  textNodesUnder,
  upFrom,
  userScrollport,
  verbatimBoundaryIdentity,
  verbatimOwnerIdentity,
} from "/runtime/check-api.js";
import { at, place, unique } from "./locate.js";
import { drawnPage, openRoots } from "./open-roots.js";

/** @param {Element} owner @param {readonly string[]} modules the tags a module upgrades */
const compositionalWords = (owner, modules) => {
  /** @type {{at: number, child: Element}[]} */
  const boundaries = [];
  const segments = textNodesUnder(owner, undefined, (child, at) => {
    if (!modules.includes(child.localName)) return false;
    boundaries.push({ at, child });
    return true;
  });
  const reading = [];
  let start = 0;
  const flush = (/** @type {number} */ end) => {
    const text = quoteFrom(segments.slice(start, end));
    if (text) reading.push({ text });
    start = end;
  };
  for (const { at, child } of boundaries) {
    flush(at);
    const identity = verbatimBoundaryIdentity.get(child);
    reading.push({
      boundary: [
        identity?.owner ?? null,
        identity?.index ?? null,
        child.localName,
        child.id || null,
      ],
    });
  }
  flush(segments.length);
  return reading;
};

/** @param {Readonly<Record<string, import("../../../browser/types/contract.js").WidgetDeclaration>>} declarations
 * @param {readonly string[]} modules the tags a module upgrades */
export const shownVerbatim = (declarations, modules) =>
  Object.entries(declarations)
    .filter(([, entry]) => entry["x-verbatim"])
    .flatMap(([tag]) =>
      [...document.querySelectorAll(tag)].map((el) => ({
        tag,
        id: el.id,
        provenance: verbatimOwnerIdentity.get(el) ?? null,
        says: says(el),
        compositional: compositionalWords(el, modules),
      })),
    );

// Words the page draws in the same place as other words. A copy went out with a settled
// group's cards laid across the heading above them — the cards kept the collapsed
// padding, which is the room the group is laid out in — and the user saw it in the
// first second while every assertion passed: the words were all present, all shown, and
// all of a usable size. They were in the same place, and nothing was asking about place.
//
// Boxes rather than a hit test, which is the other way to ask: a press landing on the
// wrong element is a different fault with its own test, and the medium this has to hold
// up in is the copy, where there is nothing left to press. Text against text, because
// text over a background, a border, or a picture is how a page is built.
//
// What floats over the document on purpose is answered for, and that is one exemption
// rather than two. It reads as the runtime's, because for a long time the runtime owned
// every float there was; the sentence is about the float and not about the owner. A
// sidenote hangs out of the flow level with the block it annotates, pinned by what it
// belongs to, and a page's own absolutely placed furniture does the same; covering a
// word there is the page's composition, not a fault. A control in the flow covering a
// word is a fault this still reports. Leaf's margin rows stand in its own layer over the
// page, which the chrome skip below takes whole.
//
// A pair where one element contains the other is skipped: a paragraph and the <em>
// inside it are one run of words that the flow lays out together, and their boxes
// overlap by construction. Two pixels of slack, since a line box carries its leading and
// adjacent blocks can round into each other by a hair. The runtime's layer is skipped
// too: it floats over the document on purpose, and where that costs the user a press
// it is the hit test that says so.
//
// The same fact one element over: an SVG <text> lays out its own lines, a tspan each,
// every one of them a sibling of the last. Where a chart's date axis names the month a
// week begins — the tick reading 1 over Dec — the two lines are offset by the dy the
// drawing asked for and each reports a line box carrying the font's own leading, which
// is a couple of pixels taller than that step. So the pair overlapped by construction on
// a drawing where no glyph comes near another. A wrapped paragraph is the identical
// shape and never reported, because its lines are boxes of one text node and the
// same-element skip takes them; two lines of one label are two nodes only because SVG
// spells a line break as an element. The <text> is the label, so a pair inside one of
// them is one word of the page's, and this asks about two.
//
// The layer is in two places and the float rule reaches both, which is why only one of
// them is named. Beside the chrome, a widget hangs some of its own controls out of flow
// over the page, clipped or transparent at rest. checkVisibility answers for display,
// visibility and opacity and knows nothing of clip-path, so such a control reads as
// drawn, and its text lays out past the box holding it. A control the runtime hangs
// absolutely is the whole of what `floating` asks, so no float needs a name here: two
// skips over one element is a guarantee kept twice, and the weaker of them is the one
// that has to be remembered when the next float is written.
//
// checkVisibility knows nothing of content-visibility either, which is what a collapse
// wears: an inactive tab's panel and a settled group's cards are hidden="until-found" so
// that find-in-page still reaches inside, and the text in one reports the boxes it last
// laid out in — every sibling's at the same place. So a page with a collapsed group on it
// failed about half the runs and passed the rest, which is the worst way for a gate to be
// wrong: the page that goes out is whichever one the coin was kind to. A collapse is asked
// for, and words nobody can see are not drawn over anything, so [hidden] is held out here
// the way the size check holds it out. The coin comes down the same side every time on a
// group that has been opened and closed, which is where the test pins it.
//
// Leaf's own interface can cover words too. The floating panel's row stands over the
// window's foot, and the theme pads the end of the page by the row's room
// (`--lf-foot-room`, base.css), so the page's last words scroll clear of it. A page can
// lose that room without any rule saying so: a reset that zeroes body's padding, a body
// held to the window's height that its content runs past, or a scroller of its own
// with nothing at its end. No rule of Leaf's keeps the room against every page, since
// the page's CSS can end its content past any box Leaf pads. So this reading places
// each word where it stands once every scroller holding it is at its end, as far up
// the window as the user can bring it, and compares it with the boxes Leaf's chrome
// covers (`coverBoxes`, geometry.js), which the gate reads at rest, before it opens a
// thread. A word still under one of them is out of the user's reach (`under-panel`).
// Words the page hides from assistive technology and draws at under half opacity.
/** @param {Element} el */
const decoration = (el) => {
  if (!el.closest("[aria-hidden=true]")) return false;
  let opacity = 1;
  /** @type {Element | null} */
  let at = el;
  for (; at; at = at.parentElement) opacity *= Number(getComputedStyle(at).opacity);
  return opacity < 0.5;
};

export function coveredWords({
  holdFloating = true,
  holdHidden = true,
  holdLabelLines = true,
} = {}) {
  const runs = paintedRuns(document.body, { holdFloating, holdHidden });
  /** @type {Record<string, unknown>[]} */
  const found = [];
  const chrome = coverBoxes();
  for (const { el, end, text } of runs)
    if (end && !decoration(el) && chrome.some((box) => overlaps(end, box)))
      found.push({ code: "under-panel", at: at(el), place: place(el), words: text });
  const shown = runs
    .flatMap(({ box, ...run }) => (box ? [{ ...run, box }] : []))
    .map((run, order) => ({ ...run, order }));
  // Two runs can cover each other only if their boxes overlap by more than the 2px of
  // slack in height. So the runs are taken from the top of the page down, and each is
  // compared only with the earlier ones whose boxes reach more than 2px below its top:
  // on a page of text, the other runs on its line. Comparing every pair cost the square
  // of the page's words, at every width of the gate's sweep.
  /** @type {typeof shown} */
  let open = [];
  /** @type {[typeof shown[number], typeof shown[number]][]} */
  const pairs = [];
  for (const run of [...shown].sort((a, b) => a.box.top - b.box.top)) {
    open = open.filter((other) => other.box.bottom - run.box.top > 2);
    for (const other of open)
      pairs.push(other.order < run.order ? [other, run] : [run, other]);
    open.push(run);
  }
  // Each pair in the page's order, so a finding names first what the page says first.
  pairs.sort(([a, b], [c, d]) => a.order - c.order || b.order - d.order);
  for (const [a, b] of pairs) {
    if (a.el === b.el || a.el.contains(b.el) || b.el.contains(a.el)) continue;
    if (holdLabelLines && a.label && a.label === b.label) continue;
    // A faint numeral the page declares decorative, set behind a label, is drawn
    // there on purpose and leaves the label legible; an opaque one still covers it.
    if (decoration(a.el) || decoration(b.el)) continue;
    // SVG renderers can draw a stroked copy directly behind a filled label
    // to make its letters legible. They are one painted word, not two words
    // covering each other; keep comparing either copy with every other run.
    if (
      a.label &&
      b.label &&
      a.label !== b.label &&
      a.label.parentElement === b.label.parentElement &&
      a.label.textContent === b.label.textContent &&
      (getComputedStyle(a.label).fill === "none" ||
        getComputedStyle(b.label).fill === "none") &&
      Math.abs(a.box.left - b.box.left) < 1 &&
      Math.abs(a.box.top - b.box.top) < 1 &&
      Math.abs(a.box.width - b.box.width) < 1 &&
      Math.abs(a.box.height - b.box.height) < 1
    )
      continue;
    if (!overlaps(a.box, b.box)) continue;
    found.push({
      code: "covered-words",
      at: at(a.el),
      // Both elements' places (locate.js), so the gate's sweep meets the same pair
      // again at another width and tells it from another pair sharing a name.
      place: [place(a.el), place(b.el)],
      words: a.text,
      under: at(b.el),
      covered: b.text,
    });
  }
  return unique(found);
}

// Two boxes share more than the two pixels a line's leading or a rounding can account
// for, across and down (`coveredWords`'s header).
/** @param {import("/runtime/rect.js").Box} a @param {import("/runtime/rect.js").Box} b */
const overlaps = (a, b) =>
  Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 &&
  Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2;

// Where the words under the element `selector` names are painted, one box per run:
// the reading `coveredWords` compares, for a suite test asking what a box hides. It
// sees what the user is shown, so a word said only to a screen reader (`.lf-quiet`),
// whose text still lays out a line box past the pixel clipping it, hides nothing.
/** @param {string} selector */
export const paintedWords = (selector) =>
  paintedRuns(document.querySelector(selector)).flatMap(({ box, text }) =>
    box
      ? [{ left: box.left, top: box.top, right: box.right, bottom: box.bottom, text }]
      : [],
  );

// Each run of words under `root`, with the box it paints (`box`) and the box it would
// paint with every scroller holding it at its end (`end`), read as `coveredWords`'s
// header says. Either is null where nothing of the run shows; a run is kept where one
// shows.
/** @param {Element | null} root */
function paintedRuns(root, { holdFloating = true, holdHidden = true } = {}) {
  /** @type {{el: Element, label: Element | null, text: string, box: DOMRect | null, end: DOMRect | null}[]} */
  const runs = [];
  const outOfFlow = (/** @type {CSSStyleDeclaration} */ style) =>
    style.position === "absolute" || style.position === "fixed";
  const floating = (/** @type {Element} */ el) => {
    // The offer may be only one contribution inside a shared positioned host. Walk
    // its actual ancestry rather than jumping from offer to offer, so the geometry
    // owner can remain a generated container without making its children's words
    // look like ordinary in-flow prose.
    for (let ancestor = el.closest("[data-lf-offer]"); ancestor;) {
      if (outOfFlow(getComputedStyle(ancestor))) return true;
      ancestor = ancestor.parentElement;
    }
    return false;
  };
  // What a run paints, which is not the whole of its rect. A box that clips its overflow
  // shows only the part inside it, so a name ellipsised in a narrow column reads as
  // covering whatever stands beside it while the user sees the ellipsis and nothing
  // else. Every content ancestor is intersected in, so the reading is the one the
  // user is given. The document scrollport is the page's route to the rest of those
  // words, not a content clip; stop before body just as the control reachability probe
  // does. The walk below stays in the light DOM, so the climb does too.
  //
  // A scroll moves the contents of its box by the distance scrolled and changes nothing
  // else. So with every scroller at its end, a run stands higher by the scroll each
  // scroller on the climb has left (`toGo`), plus the page's own unless a fixed box
  // ends the climb, and each box that clips the run stands higher by what the
  // scrollers above that box have left. The page scrolls as the document, and as
  // `body` where the page gives `body` an overflow that scrolls, which the root's own
  // `overflow-y` (base.css) keeps on `body` rather than passing to the window. A box
  // the user can't scroll (`overflow: hidden`) stays where it is. A box the page sticks
  // is lifted with the flow around it, which is where it stands at the end, except one
  // stuck to the window's foot before the page scrolls: it is lifted from where it
  // sticks rather than from its place in the flow, so words in it go unreported. The
  // climb is read once for each element, however many lines it lays out.
  /** @param {DOMRect} rect @param {number} rise */
  const lift = (rect, rise) =>
    rise ? new DOMRect(rect.x, rect.y - rise, rect.width, rect.height) : rect;
  /** @param {DOMRect | null} box @param {DOMRect} bounds */
  const within = (box, bounds) => {
    if (!box) return null;
    const left = Math.max(box.left, bounds.left);
    const right = Math.min(box.right, bounds.right);
    const top = Math.max(box.top, bounds.top);
    const bottom = Math.min(box.bottom, bounds.bottom);
    return right > left && bottom > top
      ? new DOMRect(left, top, right - left, bottom - top)
      : null;
  };
  /** @param {Element} box @param {CSSStyleDeclaration} style */
  const toGo = (box, style) =>
    userScrollport(style.overflowY) ? Math.max(0, scrollLimit(box) - box.scrollTop) : 0;
  const pageToGo = [...new Set([pageScroller, document.body])].reduce(
    (sum, box) => sum + toGo(box, getComputedStyle(box)),
    0,
  );
  /** @typedef {{bounds: DOMRect | null, toGo: number}} Step */
  /** @type {Map<Element, {steps: Step[], fixed: boolean} | null>} */
  const climbs = new Map();
  /** @param {Element} el */
  const climb = (el) => {
    /** @type {Step[]} */
    const steps = [];
    /** @type {Element | null} */
    let ancestor = el;
    for (; ancestor && ancestor !== document.body;) {
      const style = getComputedStyle(ancestor);
      // SVG text ranges retain geometry below display:none groups, and Chromium's
      // checkVisibility still returns true for them. Their ancestry paints no words.
      if (style.display === "none") return null;
      steps.push({
        bounds:
          style.overflowX !== "visible" || style.overflowY !== "visible"
            ? ancestor.getBoundingClientRect()
            : null,
        toGo: toGo(ancestor, style),
      });
      // An out-of-flow box is laid out against its containing block rather than against
      // the ancestry: an overflow between the two does not clip it, and one at or above
      // the containing block does, so the climb goes on from there. A board column's
      // count hangs absolutely in its column, and the board that scrolls the column out
      // of view hides the count with it. `offsetParent` is the containing block only
      // when it is positioned: a static table or cell it may name instead stands below
      // the real one, so there the climb stops and keeps the rect whole, over-reporting
      // a cover being this reading's safe direction. A fixed box answers to the
      // viewport alone.
      if (style.position === "fixed") return { steps, fixed: true };
      if (style.position === "absolute") {
        /** @type {Element | null} */
        const holder = ancestor instanceof HTMLElement ? ancestor.offsetParent : null;
        if (!holder || getComputedStyle(holder).position === "static") break;
        ancestor = holder;
        continue;
      }
      ancestor = ancestor.parentElement;
    }
    return { steps, fixed: false };
  };
  /** @param {Element} el @param {DOMRect} drawn */
  const painted = (el, drawn) => {
    if (!climbs.has(el)) climbs.set(el, climb(el));
    const path = climbs.get(el);
    if (!path) return { box: null, end: null };
    let rise = path.steps.reduce(
      (sum, step) => sum + step.toGo,
      path.fixed ? 0 : pageToGo,
    );
    /** @type {DOMRect | null} */
    let box = drawn;
    /** @type {DOMRect | null} */
    let end = lift(drawn, rise);
    for (const step of path.steps) {
      rise -= step.toGo;
      if (!step.bounds) continue;
      box = within(box, step.bounds);
      end = within(end, lift(step.bounds, rise));
      if (!box && !end) break;
    }
    return { box, end };
  };
  // The part of a run's rect its letters can reach. A text range's rect spans its font's
  // ascent to descent, taller than any letter, so display type set solid overlaps the
  // next line's rect with no letter near another. The font's own metrics place the
  // baseline and the tallest ascender and deepest descender among the node's letters,
  // measured in every case text-transform may draw. Only untransformed horizontal HTML
  // text, whose rect is the font's own span, is trimmed; SVG, a transform or vertical
  // writing can lay the text's length along the rect's height, and an untrimmed rect
  // over-reports, the safe side.
  const metrics = canvas2D(document.createElement("canvas"));
  /** @param {Element} el @param {string} data @param {DOMRect} drawn */
  const ink = (el, data, drawn) => {
    if (el.closest("svg")) return drawn;
    const style = getComputedStyle(el);
    if (!style.writingMode.startsWith("horizontal")) return drawn;
    /** @type {Element | null} */
    let at = el;
    for (; at; at = at.parentElement) {
      const { transform, rotate, scale } = getComputedStyle(at);
      if (transform !== "none" || rotate !== "none" || scale !== "none") return drawn;
    }
    const text = data.replace(/\s+/g, " ").trim();
    metrics.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    const m = metrics.measureText(`${text}${text.toUpperCase()}${text.toLowerCase()}`);
    const span = m.fontBoundingBoxAscent + m.fontBoundingBoxDescent;
    // A fallback font's span differs from the first family's; keep that rect whole.
    if (!(span > 0) || Math.abs(drawn.height / span - 1) > 0.2) return drawn;
    const baseline = drawn.top + m.fontBoundingBoxAscent;
    const top = Math.max(drawn.top, baseline - m.actualBoundingBoxAscent);
    const bottom = Math.min(drawn.bottom, baseline + m.actualBoundingBoxDescent);
    return bottom > top
      ? new DOMRect(drawn.left, top, drawn.width, bottom - top)
      : drawn;
  };
  if (!root) throw new Error("The text reading has no document element");
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  // A text walk visits text nodes.
  for (
    let node = /** @type {Text} */ (walk.nextNode());
    node;
    node = /** @type {Text} */ (walk.nextNode())
  ) {
    const el = node.parentElement;
    if (
      !node.data.trim() ||
      !el ||
      el.closest(".lf-chrome, .lf-quiet") ||
      (holdHidden && el.closest("[hidden]"))
    )
      continue;
    if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
      continue;
    if (holdFloating && floating(el)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const label = el.closest("text");
    const text = node.data.trim().slice(0, 40);
    /** @param {DOMRect | null} box */
    const shows = (box) => (box && box.width > 1 && box.height > 1 ? box : null);
    for (const drawn of range.getClientRects()) {
      const { box, end } = painted(el, ink(el, node.data, drawn));
      const run = { el, label, text, box: shows(box), end: shows(end) };
      if (run.box || run.end) runs.push(run);
    }
  }
  return runs;
}

// Inspect the theme's actual token paint, including declared widget shadow roots.
// Shiki supplies styles; page CSS resolves their variables. A theme may intentionally
// give a token the surrounding ink, so the suite checks legibility rather than requiring
// every syntax category to look different. Group identical styles by painted surface.
//
// What a colour is comes back from the browser painting it, not from a parse of how it
// wrote it down — getComputedStyle serializes a hex as rgb() in 0–255 and a color-mix as
// color(srgb …) in 0–1, and a probe reading one as the other reports a ratio against a
// colour nothing on the page is. Painting the backgrounds in order composites the
// translucent ones the way the page does, over the white the browser paints under
// everything, so a tint over a tint is the colour the user actually has behind the
// glyphs. A marked passage is not among them: the highlight registry styles glyphs and
// not boxes, so a mark is no element's background, and it is the user's own paint over a
// page that had to be legible before they put it there.
//
// 4.5:1 is WCAG AA for body text, and body text is the threshold that applies — code is
// 13px. Axe runs over this corpus too and passes it, which is not the same guarantee:
// asked for colour-contrast alone on the example carrying the beige comment, it returned
// 44 passing elements, no violation, and not one of the spans among them.
//
// Which shadow roots it crosses into is OPEN_ROOTS' answer (that module says why it
// crosses at all), which is the choice everything else here makes — colour is
// asked of what the browser painted, so where it painted is too, and a root a widget
// attached without declaring one still holds code the user has to read.
export function unreadSyntax() {
  const cx = canvas2D(document.createElement("canvas"), { willReadFrequently: true });
  /** @param {...string} layers @returns {[number, number, number]} */
  const paint = (...layers) => {
    cx.clearRect(0, 0, 1, 1);
    for (const c of ["white", ...layers]) {
      cx.fillStyle = c;
      cx.fillRect(0, 0, 1, 1);
    }
    const data = cx.getImageData(0, 0, 1, 1).data;
    const pixel = new DataView(data.buffer, data.byteOffset, data.byteLength);
    return [pixel.getUint8(0), pixel.getUint8(1), pixel.getUint8(2)];
  };
  const chan = (/** @type {number} */ v) =>
    (v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  const lum = (/** @type {[number, number, number]} */ [r, g, b]) =>
    0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b);
  /** @param {[number, number, number]} a @param {[number, number, number]} b */
  const ratio = (a, b) => {
    const left = lum(a),
      right = lum(b);
    return (Math.max(left, right) + 0.05) / (Math.min(left, right) + 0.05);
  };
  const under = (/** @type {Element} */ el) => {
    const layers = [];
    /** @type {Element | null} */
    let a = el;
    for (; a; a = upFrom(a)) layers.unshift(getComputedStyle(a).backgroundColor);
    return layers;
  };
  const seen = new Set(),
    found = new Map();
  for (const span of openRoots(document).flatMap((r) => {
    /** @type {NodeListOf<HTMLElement>} */
    const tokens = r.querySelectorAll("[data-lf-syn]");
    return [...tokens];
  })) {
    const style = span.style.cssText;
    if (found.has(style) || !span.textContent.trim()) continue;
    if (!span.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
      continue;
    const layers = under(span);
    const on = paint(...layers);
    const ink = paint(...layers, getComputedStyle(span).color);
    const surface = `${style} ink ${ink} on ${on}`;
    if (seen.has(surface)) continue;
    seen.add(surface);
    const read = ratio(ink, on);
    if (read < 4.5)
      found.set(style, {
        code: "unread-syntax",
        style,
        ratio: Math.round(read * 10) / 10,
      });
  }
  return [...found.values()];
}

// The page's own code blocks that declare a language Leaf colours and go uncoloured,
// since no reading face reaches them (syntax.js), as on a page that takes no theme.
// Nothing else says so: the block reads as text, and its author learns only from the
// render, while a reader can take the plain block for a broken one. It is advice,
// since a page of its own design may leave its code the colour of its ink. A widget's
// own tree is held out, since its sheet decides how its code reads.
export function uncolouredCode() {
  return [...document.querySelectorAll("pre > code[class]")]
    .filter((code) => inPage(code) && colourableAs(code) && !colouredAs(code))
    .map((code) => ({
      code: "uncoloured-code",
      at: at(code),
      language: colourableAs(code),
    }));
}

// Words a declaration promised and the page never got. Every other reading here works
// from what the browser drew, and that is exactly what cannot see this one: a word that
// never arrived looks the same as an attribute with nothing to say. The registry is what
// knows the difference — x-says names the attributes whose values are words at the
// element's edge — so the declaration is what this asks against.
//
// The pass runs once at the upgrade, before an async widget's own render lands, so a
// module that rebuilds its body from a settle() promise takes the words out with it and
// nothing on the page says so.
//
// It reads every open root (OPEN_ROOTS) where the word pass stops at the boundary on
// purpose: which widgets the page holds is the document's question, and settling a
// staged widget's nesting in a sweep would be writing that contract where nobody would
// look for it (the layer's AGENTS.md). So a staged element keeps its declarations and
// gets no pass, which is exactly where a promised word reaches nobody in silence —
// reported here, to the module's author, at handover.
//
// It asks the *rendered* page rather than the markup, and a shadow host is why: an
// element that stages a tree keeps its light DOM in the document and out of every box,
// so the pass finds the host, writes there, and leaves `textContent` and `querySelector`
// reporting words the user will never get. Words are `says()`, the layer's one answer to
// what an element says rather than a second reading spelled here — asked of the host's
// root where there is one, since the walk behind it substitutes a declared root for a
// *child* and never for the element it was handed.
/** @param {Readonly<Record<string, import("../../../browser/types/contract.js").WidgetDeclaration>>} declarations */
export function silentWords(declarations) {
  const found = [];
  const all = openRoots(document);
  const every = (/** @type {string} */ tag) =>
    all.flatMap((r) => [...r.querySelectorAll(tag)]);
  for (const [tag, entry] of Object.entries(declarations))
    for (const attr of Object.keys(entry["x-says"] ?? {}))
      for (const el of every(tag)) {
        const value = el.getAttribute(attr);
        if (value !== null && !says(el.shadowRoot ?? el).includes(value))
          found.push({ code: "silent-word", at: at(el), attr, value });
      }
  return found;
}

// The smallest size the drawing idiom sets its labels at, in viewBox units
// (`--drawing-small-size`). Both the live reading and the gate use this heuristic, and a
// reading carries the threshold so its consumer can distinguish it from a failure.
const SHRUNK_LABEL_THRESHOLD_PX = 10;

/** @param {Element[]} [drawn] what the browser draws of the page (`drawnPage`) */
export function shrunkLabelReading(drawn = drawnPage()) {
  return {
    threshold_px: SHRUNK_LABEL_THRESHOLD_PX,
    drawings: shrunkLabels(SHRUNK_LABEL_THRESHOLD_PX, drawn),
  };
}

// Labels a drawing shrank past reading. An inline <svg> states its size in its own units
// and the theme fits it to its box (`svg.drawing` takes the figure's width), so what the
// author wrote as an 11px label is drawn at 11px times whatever the box made of the
// viewBox. Nothing in the source says what that is: the page is correct, the labels are
// all there, and every other reading passes it — an eval's dashboard went out with its
// rollout graphic's labels a few pixels high at 900px and on a phone, and the gate said
// nothing. So the size is asked of the drawing as drawn: the font-size each run of words
// was set at, times the vertical scale of the transform from its element to the screen,
// which is the viewBox fit and any transform inside or around it.
//
// A label counts when the drawing made it smaller than it was set and smaller than
// `floor`. Drawn size is what decides, since halving a 28px heading leaves it legible
// and a fifth off an 11px label does not. The first half is what makes it the drawing's
// finding: a label set small and drawn at that size is a choice the source states (a
// page's own step glyph at 9px, bold on its dot), and a widget that keeps its
// renderer's natural size — a diagram scrolls rather than shrink, a chart draws at the
// width it measured — never scales one at all.
//
// One entry per drawing, the outermost <svg>, because the fix is the drawing's: its
// labels, its layout, or the room it is given. Every open root, since a drawing a module
// makes on a project's page is that page's too; the runtime's own layer is skipped. Only
// a drawing the browser draws (`drawnPage`): one in a tab not chosen or an
// off-screen `content-visibility: auto` box is skipped content, which asking about would
// make the browser lay out.
//
// A run of words counts only where it is painted, which is asked of the element holding
// it — the <text>, or the <tspan> inside one — since that is what the browser lays out
// and paints, and a visible <text> can hold runs that are not. The element needs a box
// and must be visible. Nothing in <defs> or another unrendered subtree has a box, nor
// does a run under display: none, though the page's own checkVisibility passes one in
// <defs>; a run laid out under visibility or opacity has a box and paints nothing. The
// `hidden` attribute is no separate case: on an HTML ancestor it is display: none, and on
// an SVG element Chrome draws the words anyway.
/** @param {number} floor @param {Element[]} drawn */
function shrunkLabels(floor, drawn) {
  const chrome = (/** @type {Element} */ el) => {
    /** @type {Element | null} */
    let node = el;
    for (; node;) {
      if (node.closest(".lf-chrome")) return true;
      const root = node.getRootNode();
      node = root instanceof ShadowRoot ? root.host : null;
    }
    return false;
  };
  /** @typedef {{at: string, place: import("./locate.js").Place, labels: number, drawn?: number, set?: number, words?: string}} ShrunkDrawing */
  /** @type {Map<SVGSVGElement, ShrunkDrawing>} */
  const drawings = new Map();
  for (const svg of drawn) {
    if (!(svg instanceof SVGSVGElement) || svg.ownerSVGElement) continue;
    for (const text of svg.querySelectorAll("text")) {
      // A local-name selector also matches HTML templates mounted inside SVG.
      // Only native SVG text has the geometry this reading measures.
      if (!(text instanceof SVGTextElement) || chrome(text)) continue;
      const walk = document.createTreeWalker(text, NodeFilter.SHOW_TEXT);
      for (
        let node = /** @type {Text} */ (walk.nextNode());
        node;
        node = /** @type {Text} */ (walk.nextNode())
      ) {
        const words = node.data.trim();
        // Inside an SVG `text`, so an SVG element.
        const holder = node.parentElement;
        // Visibility first: it answers for a run in skipped content, such as a tab not
        // chosen, without making the browser lay that content out to find its box.
        if (
          !words ||
          !(holder instanceof SVGGraphicsElement) ||
          !holder.checkVisibility({
            visibilityProperty: true,
            opacityProperty: true,
          }) ||
          !holder.getClientRects().length
        )
          continue;
        const ctm = holder.getScreenCTM();
        if (!ctm) continue;
        const set = parseFloat(getComputedStyle(holder).fontSize);
        const drawn = set * Math.hypot(ctm.c, ctm.d);
        if (drawn >= floor || drawn >= set - 0.05) continue;
        /** @type {ShrunkDrawing} */
        const found = drawings.get(svg) ?? {
          at: at(svg),
          place: place(svg),
          labels: 0,
        };
        found.labels += 1;
        if (found.drawn === undefined || !(found.drawn <= drawn))
          Object.assign(found, {
            drawn: Math.round(drawn * 10) / 10,
            set: Math.round(set * 10) / 10,
            words: words.slice(0, 40),
          });
        drawings.set(svg, found);
      }
    }
  }
  return [...drawings.values()];
}
