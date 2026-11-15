/* CSS anchors for boxes Leaf positions against page content: margin rows, floating
 * surfaces, Copy and target paint.
 *
 * A box that follows scrolled content is anchored, through a carrier, inside frames
 * anchored to each scroller and cut at its edge. The box, or a carrier holding a run of
 * such boxes, is `position: fixed` and anchored to an element every scroll around its
 * target moves with it: what the innermost scroller's scroll carries beside the target
 * (`carriedAnchor`), or the target's own box where a sticky, fixed or absolute box stands
 * between the two (`scrollsWith`). The browser then moves it in the frame that scrolls
 * the target, and no script answers the scroll. Where the box must be cut at a scroller's
 * edge it stands in one frame per such scroller (`cutFrames`), outermost first, each
 * `position: fixed`, anchored to its scroller, which the scrolls around that scroller
 * carry and its own does not, and cut to the scroller's band with `clip-path`. A clip
 * path does not make a frame the containing block of the fixed boxes inside it, as a
 * transform would, so their anchors still position them. Every length is written as an
 * inset from where its anchor stood when it was measured (`anchorAt`), which no scroll
 * changes. Anchors stay grouped: one carrier anchors a run of rows, since an anchor per
 * row made every layout pass revisit every target.
 *
 * A box that follows scrolled content also passes under the sticky headers and footers
 * a page declares over its target, as the target's own words do, through frames cut
 * where they stand, all read by one clip walk (geometry.js, `headerCuts` and the
 * `paintClips` bands target paint is cut by): a margin row and Copy through
 * `headerLevels`, a key chip that no scroller's edge cuts through the same cuts in its
 * paint stand. So a pin whose target scrolls under a stuck toolbar takes none of the
 * toolbar's presses. The comment box and the thread card stay over them (floating.js),
 * since they are where the user is writing.
 *
 * Rejected: a layer a scroll-driven animation translates, which Chrome can paint a frame
 * before or after the content it carries (a pin landed 40 px off in 6 of 20 CI runs,
 * #1935) and Firefox cannot run; and a script that measures and places the box again
 * after each scroll, which paints a frame behind it. Two browser gaps are accepted rather
 * than answered by either (notes/browser-support.md, "A stuck sticky anchor in
 * Firefox" and "An anchor under a fixed box in WebKit"): Firefox ignores a sticky
 * anchor's stuck offset, and WebKit adds the root scroll to a box anchored under a
 * fixed ancestor. A third is answered where every inset is measured (`anchorBox`):
 * Firefox leaves an anchor's transforms out. A fourth gets the measuring script rejected
 * above, once per scroll: inside a scaled box, Firefox 157 and WebKit 27.2 carry an
 * anchored box by the scroll's layout pixels, not the smaller or larger distance the
 * words move on screen (Firefox bug 2055371, which its own transform support still has).
 * So the margin measures and places the rows that scroll carried again at that box's
 * `scrollend` (`scrollMisplacesAnchors`, margin-layout.js), and they stand on their words
 * a frame after it ends. While the scroll runs, the margin's once-a-frame reading of it
 * finds a row whose words have left it and places it again (`subjectMoved`), which in
 * Firefox, whose anchors `anchorBox` measures without their transforms, keeps the row a
 * few pixels from its words; in WebKit the measured anchor moves with the words, so its
 * rows drift until `scrollend`. Chromium 156 follows the words, so there the pass writes
 * the insets the scroll left.
 *
 * A source keeps one name across those uses. Retained controls can observe whether its
 * source renders near the viewport before entering layout. That reading starts
 * synchronously, including ancestor clips, and observers maintain it; keyboard intent can
 * refresh it before an observer task. Control departure releases its observation through
 * the same arrivals door as the other chrome owners; its weakly retained binding restores
 * that observation when the control returns. */
import {
  headerCuts,
  nearObserver,
  nearWindow,
  scrollContainer,
  scrollsContent,
  shownParts,
} from "./geometry.js";
import { hostIn, renderedParent, shadowHost } from "./shadow.js";
import { isElement, isHTML, isText, nativeLayerHolding } from "./shadow-tree.js";
import { watchArrivals } from "./arrivals.js";
import { inlineStyle, keeps, layoutPx } from "./keeps.js";
import { move } from "./dom-move.js";
import { chromeRoot } from "./chrome.js";

/** @typedef {import("./rect.js").Box} Box
 * @typedef {{scroller: Element, name: string, getBoundingClientRect(): DOMRect}} ContentStart
 * @typedef {Element | ContentStart} Anchor
 * @typedef {{el: Element, name: string, write?: string, part?: boolean} | {el?: never, name: string, write?: never, part?: never}} AnchorReading
 * @typedef {{left: number, top: number} & ({right: number, bottom: number} | {right?: never, bottom?: never})} PaintBox
 * @typedef {{x: boolean, y: boolean}} Axes
 * @typedef {{anchor: Anchor | null, band: Box, axes: Axes, at?: Box | null, reading?: AnchorReading | null}} CutLevel
 * @typedef {{target: Element, near: boolean, nodes: Map<Element, () => void>, observer: IntersectionObserver}} AnchorView */

// Anchor names are global to their tree, so one per target element, merged with whatever
// name the author gave the same box. The name stays for the element's life: rows come and
// go on the heartbeat and a name written each time would restyle the target each time.
// The pass reads what a box is named before it writes any name (`anchorReading`), since
// reading the author's name is a style read.
//
// A name reaches only the tree whose style declares it, and a widget's shadow tree is not
// the chrome's. A box in a shadow tree whose host stands in the document is named from the
// document instead: the runtime adds a part spelled as its name, `lf-a7` for `--lf-a7`, as
// it adds focus parts (focus.js), and a document sheet of its own declares
// `::part(lf-a7) { anchor-name: --lf-a7 }`, so no widget declares anything. One rule per
// name, since WebKit resolves no `attr()` in a `::part()` rule. A document's `::part()`
// reaches one tree deep, and Firefox drops a part re-exported through `exportparts`, so a
// box deeper than that anchors through the host holding its tree in the first one
// (`anchorElement`). A box its own tree already names keeps that name and anchors through
// its host too: declared again from the document, the name would leave the tree using it.
// A widget that renders its part attribute again takes the part away, and the tree's
// watch gives it back in the same mutation checkpoint (`keepParts`).
/** @type {WeakMap<Element, string>} */
const anchorNames = new WeakMap();
// Each name back to the anchor Leaf gave it, forgotten once that anchor is collected, so
// the map holds only anchors still alive.
/** @type {Map<string, WeakRef<Anchor>>} */
const named = new Map();
const collected = new FinalizationRegistry((/** @type {string} */ name) => {
  if (!named.get(name)?.deref()) named.delete(name);
});
/** @param {string} name @param {Anchor} anchor */
const holdName = (name, anchor) => {
  if (named.get(name)?.deref() === anchor) return;
  named.set(name, new WeakRef(anchor));
  collected.register(anchor, name);
};
let anchorOrdinal = 0;
const nextName = () => `--lf-a${++anchorOrdinal}`;
/** @param {string} name */
const partOf = (name) => name.slice(2);
/** @param {Element} el */
const partNamed = (el) => {
  const name = anchorNames.get(el);
  return name !== undefined && el.part.contains(partOf(name));
};
/** @type {CSSStyleSheet | null} */
let partRules = null;
/** @type {Set<string>} */
const declared = new Set();
/** @type {WeakMap<Element, Set<string>>} */
const given = new WeakMap(); // element → the anchor parts it was given
/** @type {WeakSet<Node>} */
const watchedTrees = new WeakSet();
/** @param {Node} el */
const restoreParts = (el) => {
  if (!isElement(el)) return;
  for (const part of given.get(el) ?? [])
    if (!el.part.contains(part)) el.part.add(part);
};
/** @param {Node} root */
function keepParts(root) {
  if (watchedTrees.has(root)) return;
  watchedTrees.add(root);
  new MutationObserver((records) => {
    for (const { target } of records) restoreParts(target);
  }).observe(root, { subtree: true, attributes: true, attributeFilter: ["part"] });
}
// Names `el`, or its `::before` where `pseudo` says so, through the part `name` spells.
/** @param {Element} el @param {string} name @param {string} [pseudo] */
function namePart(el, name, pseudo = "") {
  if (!partRules) {
    partRules = new CSSStyleSheet();
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, partRules];
  }
  if (!declared.has(name)) {
    const content = pseudo ? 'content: "";' : "";
    partRules.insertRule(
      `::part(${partOf(name)})${pseudo} { ${content} anchor-name: ${name}; }`,
      partRules.cssRules.length,
    );
    declared.add(name);
  }
  given.set(el, new Set([...(given.get(el) ?? []), partOf(name)]));
  keepParts(el.getRootNode());
  restoreParts(el);
}
/** @param {Anchor} el @param {string} [name] @returns {AnchorReading} */
export function anchorReading(el, name) {
  // A content start is named where it is made (`contentStart`).
  if (!isElement(el)) return { name: el.name };
  name ??= anchorNames.get(el) ?? nextName();
  anchorNames.set(el, name);
  holdName(name, el);
  if (el.getRootNode() !== document)
    return partNamed(el) ? { el, name } : { el, name, write: name, part: true };
  const written = inlineStyle(el).anchorName;
  if (written.split(",").some((part) => part.trim() === name)) return { el, name };
  // What the author's stylesheet names this box, read only where this pass has not already
  // written: a revision patch that rewrote the style attribute has taken the name away.
  const authored = written || getComputedStyle(el).anchorName;
  return {
    el,
    name,
    write: !authored || authored === "none" ? name : `${authored}, ${name}`,
  };
}
/** @param {ReturnType<typeof anchorReading>} reading */
export function nameAnchor({ el, name, write, part }) {
  // Two readings of one box can both find it unnamed before either names it.
  if (write && part) {
    if (!partNamed(el)) namePart(el, name);
  } else if (write) inlineStyle(el).anchorName = write;
  return name;
}

// Whether the document can name `el` (`anchorReading`): it stands in the document, or in
// the first shadow tree in, where nothing names it already.
/** @param {Element} el */
export function nameable(el) {
  const root = el.getRootNode();
  if (root === document) return true;
  if (shadowHost(root)?.getRootNode() !== document) return false;
  if (anchorNames.has(el) && partNamed(el)) return true;
  const authored = getComputedStyle(el).anchorName;
  return !authored || authored === "none";
}

// The box a row or a float anchors to. A target inside an author's `anchor-scope: all`
// in the document that does not also hold the chrome anchors through the box holding the
// outermost such scope, since a name declared inside one reaches nothing outside it. That
// box does not follow a sticky or fixed box inside the scope, which the author's scope
// keeps from every box outside it. A scope in a shadow tree limits that tree's names, not
// the document's. A target in a shadow tree anchors as itself where the
// document can name it (`nameable`), and otherwise through the host holding its tree; a
// shape inside an SVG drawing has no CSS box of its own, so it anchors through the
// drawing, and so does the drawing's HTML in a `foreignObject`, which Chromium anchors
// nothing to (notes/browser-support.md, "An anchor inside an SVG foreignObject in
// Chromium"); a `display: contents` target through its first shown part. Wherever it
// anchors, what stands against it is written as insets from the anchor's box.
/** @param {Element} target */
function outsideScopes(target) {
  let el = target;
  /** @type {Node | null} */
  let at = target;
  for (; isElement(at); at = renderedParent(at))
    if (
      at.getRootNode() === document &&
      !at.contains(chromeRoot) &&
      getComputedStyle(at).anchorScope === "all"
    )
      el = renderedParent(at) ?? at;
  return el;
}
/** @param {Element} target */
export function anchorElement(target) {
  let el = outsideScopes(target);
  for (let at = /** @type {Node | null} */ (el); isElement(at); at = renderedParent(at))
    if (at.localName === "foreignObject") el = at;
  while (el instanceof SVGElement && el.ownerSVGElement) el = el.ownerSVGElement;
  for (let host; !nameable(el) && (host = shadowHost(el.getRootNode()));) el = host;
  if (el !== target) return el;
  const [part] = shownParts(target);
  return part && part !== target ? part : target;
}

// Whether an anchor on `anchor`, or on the scroller holding a content start, positions a
// fixed box at `box`: the browser lays it out before that box. An anchor in the document
// reaches into the top layer, laid out after it; within one native layer, or the
// document, the anchor comes earlier in the tree; an anchor in another native layer is
// read as out of reach, since which layer opened first is the browser's.
/** @param {Anchor} anchor @param {Element} box */
export function anchorReaches(anchor, box) {
  const holder = anchorHolder(anchor);
  const host = hostIn(holder, document);
  if (!host) return false;
  const layer = nativeLayerHolding(holder);
  if (layer !== nativeLayerHolding(box)) return !layer;
  const order = host.compareDocumentPosition(box);
  return (
    Boolean(order & Node.DOCUMENT_POSITION_FOLLOWING) &&
    !(order & Node.DOCUMENT_POSITION_CONTAINED_BY)
  );
}

// Whether every scroll that moves `node` moves what `box` holds with it, so an anchor
// on `box`, or on a box `box` holds still (`carriedAnchor`), carries `node` through each:
// `box` holds `node`, and nothing from `node` up to `box` is sticky, fixed or absolute,
// whose spot is not the scrolls' alone, or scrolls what it holds past `node`.
/** @param {Node} node @param {Node} box */
export function scrollsWith(node, box) {
  /** @type {Node | null} */
  let at = node;
  for (; at !== box; at = renderedParent(at)) {
    if (!at) return false;
    if (
      isElement(at) &&
      (!/^(static|relative)$/.test(getComputedStyle(at).position) ||
        (at !== node && scrollsContent(at)))
    )
      return false;
  }
  return true;
}

// What `scroller`'s own scroll carries as it carries what the scroller holds, for a box
// anchored to it to move with that scroll in the frame that scrolls: a child with a box
// of its own, in flow, where that scroll moves it, the one nearest `near`, one of the
// scroller's child nodes, where one is given. A line break renders as a break in the
// words rather than a box, so it anchors nothing. Words with no such child beside them
// anchor to the start of what the scroller holds (`contentStart`). Null where none of
// these is, or where the scroller lies in the top layer or a shadow tree the document
// cannot name it in (`anchorElement`), whose anchors a box in the chrome cannot reach.
/** @param {Element} scroller @param {Node | null} [near] */
export function carriedAnchor(scroller, near = null) {
  if (anchorElement(scroller) !== scroller || nativeLayerHolding(scroller)) return null;
  /** @param {Node | null | undefined} node @returns {node is Element} */
  const carried = (node) =>
    isElement(node) &&
    !/^(br|wbr)$/.test(node.localName) &&
    anchorElement(node) === node &&
    node.getClientRects().length > 0 &&
    /^(static|relative)$/.test(getComputedStyle(node).position);
  if (!near) {
    for (const child of scroller.children) if (carried(child)) return child;
    return contentStart(scroller);
  }
  for (
    let before = near.previousSibling, after = near.nextSibling;
    before || after;
    before = before?.previousSibling ?? null, after = after?.nextSibling ?? null
  )
    for (const node of [before, after]) if (carried(node)) return node;
  return contentStart(scroller);
}

// The box paint anchors to for `context`, an element or a node of words: its anchor box
// (`anchorElement`). Words standing directly in a box that scrolls them move with that
// scroll, which an anchor on the box itself does not follow, so they anchor to what the
// scroll carries beside them (`carriedAnchor`), and to the box only where nothing does.
/** @param {Node | null} context */
export function anchorFor(context) {
  const physical = isElement(context) ? context : context?.parentElement;
  if (!physical) return null;
  const anchor = anchorElement(physical);
  if (context === physical || anchor !== physical || !scrollContainer(physical))
    return anchor;
  return carriedAnchor(physical, context) ?? anchor;
}

// The start of what `scroller` holds, as a box an anchor names, for words standing in it
// with no element beside them: an empty `::before` (marks.css), inline at the start of
// the first line, where it lays out and paints nothing and moves with every scroll that
// moves the words. A pseudo-element has no rectangle a script can read, and a box
// anchored to one reads where the last frame drew it, not where a script's scroll has
// since moved it; but the empty box stands where the first line's first character or
// break does, which a range reads as layout has it. So a start is offered where the
// scroller holds only words and breaks, and where it is a
// block container, a flex or grid box making its `::before` an item, with no `::before`
// of its own and no first letter floated out of the line, which would stand the range
// in the float, and where the browser reads a name from an attribute (typed `attr()`,
// which WebKit lacks). Its handle answers `getBoundingClientRect` as an element anchor
// does, and naming it names the `::before`: through the scroller's
// `data-lf-content-start` (marks.css) in the document, and in a shadow tree through a
// part, as a box there is named (`namePart`), each written where it is made and again
// where a revision rewrote it.
/** @type {WeakMap<Element, ContentStart>} */
const starts = new WeakMap(); // scroller → handle
const START = "data-lf-content-start";
/** @param {Element} scroller */
function contentStart(scroller) {
  const first = scroller.firstChild;
  if (
    !first ||
    [...scroller.childNodes].some(
      (node) =>
        node.nodeType !== Node.TEXT_NODE &&
        !(isElement(node) && /^(br|wbr)$/.test(node.localName)),
    )
  )
    return null;
  let handle = starts.get(scroller);
  if (!handle) {
    if (
      !CSS.supports(
        "anchor-name",
        "attr(data-lf-content-start type(<custom-ident>))",
      ) ||
      !/^(block|inline-block|flow-root|list-item)$/.test(
        getComputedStyle(scroller).display,
      ) ||
      !/^(none|normal)$/.test(getComputedStyle(scroller, "::before").content) ||
      getComputedStyle(scroller, "::first-letter").float !== "none"
    )
      return null;
    handle = {
      scroller,
      name: nextName(),
      // The first node that paints: white space collapsed away paints nothing, and
      // the start stands where what follows it does.
      getBoundingClientRect() {
        const range = document.createRange();
        for (const lead of scroller.childNodes) {
          if (isText(lead)) {
            range.setStart(lead, 0);
            range.setEnd(lead, Math.min(1, lead.length));
          } else range.selectNode(lead);
          const [rect] = range.getClientRects();
          if (rect) return rect;
        }
        return range.getBoundingClientRect();
      },
    };
    starts.set(scroller, handle);
    holdName(handle.name, handle);
  }
  const { name } = handle;
  if (scroller.getRootNode() === document) keeps(scroller, START, name);
  else namePart(scroller, name, "::before");
  return handle;
}

// The box whose scrolls carry `anchor`: the scroller a content start stands in, whose
// own scroll carries it too, or the anchor itself.
/** @param {Anchor} anchor */
export const anchorHolder = (anchor) => (isElement(anchor) ? anchor : anchor.scroller);

// The anchor Leaf gave `name`, while it stands in the document; null for a name Leaf
// didn't give.
/** @param {string} name @returns {Anchor | null} */
export const anchorNamed = (name) => {
  const anchor = named.get(name)?.deref();
  return anchor && anchorHolder(anchor).isConnected ? anchor : null;
};

// The name `el` answers to as an anchor, given it first where it has none.
/** @param {Anchor} el */
export const anchorName = (el) => nameAnchor(anchorReading(el));

// Where `anchor()` reads `anchor`'s box, in client coordinates, which every inset written
// against it is measured from: its border box as a script reads it, transforms included,
// as the spec has it. Firefox (157) leaves out every transform on the anchor and its
// ancestors, and reads the box where layout put it, so a box written from the script's
// reading of a transformed anchor lands off by the transform: a table granted room is
// translated into place (layouts.css), and at 1728 px every pin, chip and comment box
// against one stood 300 px left of what it marked; a deck such as reveal.js translates
// and scales its slides, and they stood hundreds of pixels below and right of the words
// (notes/browser-support.md, "An anchor's transforms in Firefox"). There the reading is
// that laid-out box (`laidOut`), whose size is what `anchor-size()` reads there too. A
// zoom is layout, which Firefox's `anchor()` keeps.
//
// Rejected: a probe anchored to the same name, read for the corner `anchor()` resolves.
// Firefox resolves it from where scrolls stood at its last anchor snapshot, so a probe
// read straight after a scroll between it and the anchor, the widened table's own
// included, returned where the anchor stood before; and a probe in the chrome reaches
// no anchor in a native layer.
/** @type {boolean | undefined} */
let dropsTransforms;
// Firefox lacks transforms in `anchor()`; read once whether this engine does. The probe
// stands in a box with layout containment, which holds its anchor and the box anchored
// to it: in the window's containing block, Chromium restyled every anchored element on
// the page when they left, 200 ms on a page of 512 asks.
function anchorDropsTransforms() {
  if (dropsTransforms !== undefined) return dropsTransforms;
  const probe = document.createElement("div");
  const moved = document.createElement("div");
  const anchored = document.createElement("div");
  probe.style.cssText = "position: fixed; left: 0; top: 0; contain: layout";
  moved.style.cssText =
    "position: fixed; left: 0; top: 0; translate: 8px 0; anchor-name: --lf-moved";
  anchored.style.cssText =
    "position: fixed; top: 0; position-anchor: --lf-moved; left: anchor(left, 8px)";
  probe.append(moved, anchored);
  chromeRoot.append(probe);
  dropsTransforms = anchored.getBoundingClientRect().left < 4;
  probe.remove();
  return dropsTransforms;
}
// Whether `style` moves its box from where layout put it.
/** @param {CSSStyleDeclaration} style */
const moves = (style) =>
  style.transform !== "none" ||
  style.translate !== "none" ||
  style.rotate !== "none" ||
  style.scale !== "none" ||
  style.offsetPath !== "none";
// Where layout put `el`'s border box, in client coordinates, leaving out every transform
// on it and its ancestors. `moved` holds the boxes a transform moves: the anchor and its
// ancestors up to the outermost one with a transform. Any other box stands where a
// script reads it. A moved box stands at its offset from its offset parent's laid-out
// box, less the scrolls between, which offsets leave out. Offsets are whole pixels, so
// each step can stray half a pixel. A static body's offsets count from the document's
// corner, and a fixed box's from the window's. Null where a box on the way has no offset
// to read, or a zoom scales its offsets.
/** @param {Element} el @param {Set<Element>} moved @returns {DOMRect | null} */
function laidOut(el, moved) {
  if (!moved.has(el)) return el.getBoundingClientRect();
  if (!isHTML(el) || el.currentCSSZoom !== 1) return null;
  const parent = el.offsetParent;
  let left = el.offsetLeft;
  let top = el.offsetTop;
  const box = () => new DOMRect(left, top, el.offsetWidth, el.offsetHeight);
  if (!parent) return getComputedStyle(el).position === "fixed" ? box() : null;
  if (parent === document.body && getComputedStyle(parent).position === "static") {
    left -= scrollX;
    top -= scrollY;
  } else {
    const from = laidOut(parent, moved);
    if (!from) return null;
    left += from.left + parent.clientLeft - parent.scrollLeft;
    top += from.top + parent.clientTop - parent.scrollTop;
  }
  for (let at = renderedParent(el); at !== parent; at = renderedParent(at)) {
    if (!isElement(at)) return null;
    left -= at.scrollLeft;
    top -= at.scrollTop;
  }
  return box();
}
// Whether a scroll of `box` can carry what is anchored inside it away from what it marks:
// where a layout pixel of `box` shows as more or less than a pixel on screen, as under a
// scale on it or a box around it. A CSS zoom resizes layout itself, which anchors
// follow, so its width counts the zoom. WebKit's Linux build (27.2) has no
// `currentCSSZoom`, so there a zoomed box reads as scaled: it costs one pass at the
// scroll's end, which leaves the rows where they stood. Offsets are whole pixels, so a
// pixel's difference is rounding.
/** @param {Element} box */
export function scrollMisplacesAnchors(box) {
  if (!isHTML(box) || !box.offsetWidth) return false;
  const laid = box.offsetWidth * (box.currentCSSZoom ?? 1);
  return Math.abs(box.getBoundingClientRect().width - laid) > 1;
}
/** @param {Anchor} anchor */
export function anchorBox(anchor) {
  const box = anchor.getBoundingClientRect();
  if (!anchorDropsTransforms()) return box;
  /** @type {Element[]} */
  const around = [];
  let under = 0;
  /** @type {Node | null} */
  let at = anchorHolder(anchor);
  for (; isElement(at); at = renderedParent(at)) {
    around.push(at);
    if (moves(getComputedStyle(at))) under = around.length;
  }
  if (!under) return box;
  // A content start, or an anchor with no offsets such as a drawing, stands where the
  // nearest HTML box around it would carry it: in proportion to that box, which holds
  // for a translation or a scale.
  const html = around.find((el) => isHTML(el));
  const laid = html && laidOut(html, new Set(around.slice(0, under)));
  if (!laid) return box;
  if (html === anchor) return laid;
  const shown = html.getBoundingClientRect();
  /** @param {number} to @param {number} from */
  const ratio = (to, from) => (to && from ? to / from : 1);
  const x = ratio(laid.width, shown.width);
  const y = ratio(laid.height, shown.height);
  return new DOMRect(
    laid.left + (box.left - shown.left) * x,
    laid.top + (box.top - shown.top) * y,
    box.width * x,
    box.height * y,
  );
}
// Writes `node` fixed over `box`, a client rectangle, or a point where `box` gives no
// right edge and the node keeps its own size, as insets from where `anchor` stood (`at`,
// `anchorBox`) as `box` was measured, so the browser carries it through every scroll
// that moves the anchor. With no anchor it stands where the window holds it.
// `visibility` is its `position-visibility`: a cut box stays drawn while its anchor
// scrolls out of view, so the frames cutting it decide what shows.
/** @param {Pick<ElementCSSInlineStyle, "style">} node @param {Anchor | null} anchor @param {PaintBox} box @param {Box | null} [at] @param {string} [visibility] */
export function anchorAt(
  node,
  anchor,
  box,
  at = anchor && anchorBox(anchor),
  visibility = "always",
) {
  /** @param {string} side @param {number} length */
  const from = (side, length) =>
    anchor ? `calc(anchor(${side}, -9999px) + ${layoutPx(length)})` : layoutPx(length);
  Object.assign(node.style, {
    position: "fixed",
    positionAnchor: anchor ? anchorName(anchor) : "",
    positionVisibility: anchor ? visibility : "",
    left: from("left", box.left - (at?.left ?? 0)),
    top: from("top", box.top - (at?.top ?? 0)),
    ...(box.right === undefined
      ? {}
      : {
          width: layoutPx(box.right - box.left),
          height: layoutPx(box.bottom - box.top),
        }),
  });
}

// The frame itself has no painted box. Extend its zero-size clip to the measured band
// (and beyond an uncut axis), so only its descendants stand over page text. A huge
// transparent frame hid those words from contrast readers even though it took no press.
/** @param {Axes} axes @param {Box} band */
const cutPath = ({ x, y }, band) => {
  const open = 100000;
  const width = band.right - band.left;
  const height = band.bottom - band.top;
  return `inset(${layoutPx(y ? 0 : -open)} ${layoutPx(-width - (x ? 0 : open))} ${layoutPx(-height - (y ? 0 : open))} ${layoutPx(x ? 0 : -open)})`;
};

// The levels a box following `item` is cut at so that it passes under the sticky headers
// and footers a page declares over `item` (geometry.js, `headerCuts`), as `item` itself
// does: one per scroller they stand in, cut on the block axis alone, the document's in
// the window's frame and each other's anchored to its scroller, with where that anchor
// stood (`at`) and its name (`reading`) read now, before the frames are written. Every box that
// follows scrolled content stands in these, so whether it passes under a header is
// decided here once.
const nowhere = { left: 0, top: 0, right: 0, bottom: 0 };
/** @param {Element} item @param {import("./geometry.js").ClipCache} [clips] */
export function headerLevels(item, clips = new Map()) {
  return headerCuts(item, clips).map(({ box, band }) => {
    const anchor =
      box === box.ownerDocument.scrollingElement ? null : anchorElement(box);
    const cut = { band: band ?? nowhere, axes: { x: false, y: true } };
    return anchor
      ? { ...cut, anchor, reading: anchorReading(anchor), at: anchorBox(anchor) }
      : { ...cut, anchor: null, reading: null, at: null };
  });
}

// The frames that cut a box at the edges of what holds it, one per level of `levels`,
// outermost first, each nested in the one before: `{anchor, band, axes, at}`, the box the
// frame is anchored to, null for the window's frame, its band in client coordinates, the
// axes it cuts, where the anchor stood as the band was measured, read here where it is
// not given, and the anchor's name as read before any write (`anchorReading`), given
// here where it is. `frames` are the ones the levels stood in before, kept from the innermost
// out, so what stands in the last keeps its frame while the frames around it change, and
// `make` makes a missing one. A new outermost frame takes the old one's place. Answers
// each level paired with its frame; the caller places the outermost and stands what
// is cut in the last.
/** @template {CutLevel} L @overload @param {[L, ...L[]]} levels @param {HTMLElement[]} frames @param {() => HTMLElement} make @returns {[{level: L, frame: HTMLElement}, ...{level: L, frame: HTMLElement}[]]} */
/** @template {CutLevel} L @overload @param {L[]} levels @param {HTMLElement[]} frames @param {() => HTMLElement} make @returns {{level: L, frame: HTMLElement}[]} */
/** @template {CutLevel} L @param {L[]} levels @param {HTMLElement[]} frames @param {() => HTMLElement} make */
export function cutFrames(levels, frames, make) {
  const remaining = [...frames];
  const placed = levels
    .toReversed()
    .map((level) => ({
      level,
      frame: remaining.pop() ?? make(),
    }))
    .reverse();
  const chain = placed.map(({ frame }) => frame);
  const first = chain[0];
  const was = frames[0];
  if (first && was && first !== was && was.parentNode) move(was.parentNode, first, was);
  /** @type {HTMLElement | null} */
  let parent = null;
  for (const frame of chain) {
    if (parent && frame.parentNode !== parent) move(parent, frame, null);
    parent = frame;
  }
  for (const dropped of remaining) dropped.remove();
  for (const {
    level: { anchor, band, axes, at, reading },
    frame,
  } of placed) {
    if (reading) nameAnchor(reading);
    anchorAt(
      frame,
      anchor,
      { left: band.left, top: band.top, right: band.left, bottom: band.top },
      at,
    );
    frame.style.clipPath = cutPath(axes, band);
  }
  return placed;
}

// Anchored controls cost layout even when their source is hidden or far down the page.
// Observe the source once, shared by every control standing against it, for whether it
// is near (geometry.js, `nearWindow`); continuous positioning remains the browser's,
// rather than a scroll callback's.
/** @type {Map<Element, AnchorView>} */
const views = new Map();
/** @type {WeakMap<Element, {target: Element, changed: () => void, view: AnchorView | null}>} */
const viewedNodes = new WeakMap();
/** @type {IntersectionObserver | undefined} */
let viewObserver;

/** @param {Element} node */
export function refreshAnchorView(node) {
  const binding = viewedNodes.get(node);
  if (!binding) return;
  if (!binding.view) {
    resumeAnchorView(node);
    return;
  }
  const view = binding.view;
  const near = nearWindow(view.target);
  if (view.near === near) return;
  view.near = near;
  for (const notify of view.nodes.values()) notify();
}

/** @param {Element} node */
function releaseAnchorView(node) {
  const binding = viewedNodes.get(node);
  const view = binding?.view;
  if (!view) return;
  binding.view = null;
  view.nodes.delete(node);
  if (!view.nodes.size) {
    view.observer.unobserve(view.target);
    views.delete(view.target);
  }
}

/** @param {Element} node */
function resumeAnchorView(node) {
  const binding = viewedNodes.get(node);
  if (!binding || binding.view || !node.isConnected || !binding.target.isConnected)
    return;
  anchorView(node, binding.target, binding.changed);
  binding.changed();
}

/** @param {Element} node @param {Element | null} target @param {() => void} changed */
export function anchorView(node, target, changed) {
  const binding = viewedNodes.get(node);
  let view = binding?.view;
  if (view?.target === target) return view.near;
  releaseAnchorView(node);
  if (!target) return false;
  if (!viewObserver) {
    // Controls can leave while their source stays. Use the same node lifetime door as
    // the other chrome owners, rather than retaining them until another intersection.
    watchArrivals(".lf-anchor-view", ["class"], {
      arrive: resumeAnchorView,
      leave: releaseAnchorView,
    });
    viewObserver = nearObserver((entries) => {
      for (const entry of entries) {
        const view = views.get(entry.target);
        if (!view) continue;
        const near = entry.isIntersecting && entry.target.checkVisibility();
        const changed = view.near !== near;
        view.near = near;
        for (const [node, notify] of view.nodes) {
          if (!node.isConnected || !entry.target.isConnected) {
            releaseAnchorView(node);
            continue;
          }
          if (changed) notify();
        }
      }
    });
  }
  view = views.get(target);
  if (!view) {
    // The first presentation cannot wait for an observer task after its paint. Seed
    // from the source before the caller writes positioning; observations maintain it.
    view = {
      target,
      near: nearWindow(target),
      nodes: new Map(),
      observer: viewObserver,
    };
    views.set(target, view);
    viewObserver.observe(target);
  }
  view.nodes.set(node, changed);
  viewedNodes.set(node, { target, changed, view });
  if (!node.classList.contains("lf-anchor-view")) node.classList.add("lf-anchor-view");
  return view.near;
}
