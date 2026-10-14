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
 * where they stand: a margin row and Copy through `headerLevels`, target paint through
 * the bands its clip walk reads (geometry.js, `paintClips`), both from the headers each
 * target says stand over it (`--lf-top`). So a pin whose target scrolls under a stuck
 * toolbar takes none of the toolbar's presses. The comment box and the thread card stay
 * over them (floating.js), since they are where the user is writing.
 *
 * Rejected: a layer a scroll-driven animation translates, which Chrome can paint a frame
 * before or after the content it carries (a pin landed 40 px off in 6 of 20 CI runs,
 * #1935) and Firefox cannot run; and a script that measures and places the box again
 * after each scroll, which paints a frame behind it. Two browser gaps are accepted rather
 * than answered by either (notes/browser-support.md, "A stuck sticky anchor in
 * Firefox" and "An anchor under a fixed box in WebKit"): Firefox ignores a sticky
 * anchor's stuck offset, and WebKit adds the root scroll to a box anchored under a
 * fixed ancestor.
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
import { nativeLayerHolding } from "./shadow-tree.js";
import { watchArrivals } from "./arrivals.js";
import { keeps, layoutPx } from "./keeps.js";
import { move } from "./dom-move.js";
import { chromeRoot } from "./chrome.js";

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
const anchorNames = new WeakMap();
let anchorOrdinal = 0;
const nextName = () => `--lf-a${++anchorOrdinal}`;
const partOf = (name) => name.slice(2);
const partNamed = (el) => el.part.contains(partOf(anchorNames.get(el)));
let partRules = null;
const declared = new Set();
const given = new WeakMap(); // element → the anchor parts it was given
const watchedTrees = new WeakSet();
const restoreParts = (el) => {
  for (const part of given.get(el) ?? [])
    if (!el.part.contains(part)) el.part.add(part);
};
function keepParts(root) {
  if (watchedTrees.has(root)) return;
  watchedTrees.add(root);
  new MutationObserver((records) => {
    for (const { target } of records) restoreParts(target);
  }).observe(root, { subtree: true, attributes: true, attributeFilter: ["part"] });
}
// Names `el`, or its `::before` where `pseudo` says so, through the part `name` spells.
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
/** @returns {{el: any, name: string, write?: string, part?: boolean}} */
export function anchorReading(el, name = anchorNames.get(el) ?? nextName()) {
  // A content start is named where it is made (`contentStart`).
  const start = contentStarts.get(el);
  if (start) return { el, name: start.name };
  anchorNames.set(el, name);
  if (el.getRootNode() !== document)
    return partNamed(el) ? { el, name } : { el, name, write: name, part: true };
  const written = el.style.anchorName;
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
  } else if (write) el.style.anchorName = write;
  return name;
}

// Whether the document can name `el` (`anchorReading`): it stands in the document, or in
// the first shadow tree in, where nothing names it already.
function nameable(el) {
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
// drawing; a `display: contents` target through its first shown part. Wherever it
// anchors, what stands against it is written as insets from the anchor's box.
const SCOPES = CSS.supports("anchor-scope", "all");
function outsideScopes(target) {
  let el = target;
  if (SCOPES)
    for (let at = target; at instanceof Element; at = renderedParent(at))
      if (
        at.getRootNode() === document &&
        !at.contains(chromeRoot) &&
        getComputedStyle(at).anchorScope === "all"
      )
        el = renderedParent(at) ?? at;
  return el;
}
export function anchorElement(target) {
  let el = outsideScopes(target);
  for (let host; !nameable(el) && (host = shadowHost(el.getRootNode()));) el = host;
  while (el instanceof SVGElement && el.ownerSVGElement) el = el.ownerSVGElement;
  if (el !== target) return el;
  const [part] = shownParts(target);
  return part && part !== target ? part : target;
}

// Whether an anchor on `anchor`, or on the scroller holding a content start, positions a
// fixed box at `box`: the browser lays it out before that box. An anchor in the document
// reaches into the top layer, laid out after it; within one native layer, or the
// document, the anchor comes earlier in the tree; an anchor in another native layer is
// read as out of reach, since which layer opened first is the browser's.
export function anchorReaches(anchor, box) {
  const holder = anchorHolder(anchor);
  const layer = nativeLayerHolding(holder);
  if (layer !== nativeLayerHolding(box)) return !layer;
  const order = hostIn(holder, document).compareDocumentPosition(box);
  return (
    Boolean(order & Node.DOCUMENT_POSITION_FOLLOWING) &&
    !(order & Node.DOCUMENT_POSITION_CONTAINED_BY)
  );
}

// Whether every scroll that moves `node` moves what `box` holds with it, so an anchor
// on `box`, or on a box `box` holds still (`carriedAnchor`), carries `node` through each:
// `box` holds `node`, and nothing from `node` up to `box` is sticky, fixed or absolute,
// whose spot is not the scrolls' alone, or scrolls what it holds past `node`.
export function scrollsWith(node, box) {
  for (let at = node; at !== box; at = renderedParent(at)) {
    if (!at) return false;
    if (
      at instanceof Element &&
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
export function carriedAnchor(scroller, near = null) {
  if (anchorElement(scroller) !== scroller || nativeLayerHolding(scroller)) return null;
  const carried = (node) =>
    node instanceof Element &&
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
    before = before?.previousSibling, after = after?.nextSibling
  )
    for (const node of [before, after]) if (carried(node)) return node;
  return contentStart(scroller);
}

// The box paint anchors to for `context`, an element or a node of words: its anchor box
// (`anchorElement`). Words standing directly in a box that scrolls them move with that
// scroll, which an anchor on the box itself does not follow, so they anchor to what the
// scroll carries beside them (`carriedAnchor`), and to the box only where nothing does.
export function anchorFor(context) {
  const physical = context instanceof Element ? context : context?.parentElement;
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
// in the float, and where the browser reads a name from an attribute. Its handle answers
// `getBoundingClientRect` as an element anchor does, and naming it names the `::before`:
// through the scroller's `data-lf-content-start` (marks.css) in the document, and in a
// shadow tree through a part, as a box there is named (`namePart`), each written where it
// is made and again where a revision rewrote it.
const contentStarts = new WeakMap(); // handle → { scroller, name }
const starts = new WeakMap(); // scroller → handle
const START = "data-lf-content-start";
function contentStart(scroller) {
  const first = scroller.firstChild;
  if (
    !first ||
    [...scroller.childNodes].some(
      (node) =>
        node.nodeType !== Node.TEXT_NODE &&
        !(node instanceof Element && /^(br|wbr)$/.test(node.localName)),
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
      // The first node that paints: white space collapsed away paints nothing, and
      // the start stands where what follows it does.
      getBoundingClientRect() {
        const range = document.createRange();
        for (const lead of scroller.childNodes) {
          if (lead.nodeType === Node.TEXT_NODE) {
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
    contentStarts.set(handle, { scroller, name: nextName() });
  }
  const { name } = contentStarts.get(handle);
  if (scroller.getRootNode() === document) keeps(scroller, START, name);
  else namePart(scroller, name, "::before");
  return handle;
}

// The box whose scrolls carry `anchor`: the scroller a content start stands in, whose
// own scroll carries it too, or the anchor itself.
const anchorHolder = (anchor) => contentStarts.get(anchor)?.scroller ?? anchor;

// The name `el` answers to as an anchor, given it first where it has none.
export const anchorName = (el) => nameAnchor(anchorReading(el));

// Writes `node` fixed over `box`, a client rectangle, or a point where `box` gives no
// right edge and the node keeps its own size, as insets from where `anchor` stood (`at`)
// as `box` was measured, so the browser carries it through every scroll that moves the
// anchor. With no anchor it stands where the window holds it. `visibility` is its
// `position-visibility`: a cut box stays drawn while its anchor scrolls out of view, so
// the frames cutting it decide what shows.
export function anchorAt(
  node,
  anchor,
  box,
  at = anchor?.getBoundingClientRect(),
  visibility = "always",
) {
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

// A frame's cut on the axes its box clips, and none on the others.
const cutPath = ({ x, y }) => {
  const open = (clips) => (clips ? "0" : "-100000px");
  return `inset(${open(y)} ${open(x)})`;
};

// The levels a box following `item` is cut at so that it passes under the sticky headers
// and footers a page declares over `item` (geometry.js, `headerCuts`), as `item` itself
// does: one per scroller they stand in, cut on the block axis alone, the document's in
// the window's frame and each other's anchored to its scroller, with where that anchor
// stood (`at`) and its name (`reading`) read now, before the frames are written. Every box that
// follows scrolled content stands in these, so whether it passes under a header is
// decided here once.
const nowhere = { left: 0, top: 0, right: 0, bottom: 0 };
export function headerLevels(item) {
  return headerCuts(item).map(({ box, band }) => {
    const anchor = box === box.ownerDocument.scrollingElement ? null : anchorElement(box);
    return {
      anchor,
      reading: anchor && anchorReading(anchor),
      at: anchor?.getBoundingClientRect(),
      band: band ?? nowhere,
      axes: { x: false, y: true },
    };
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
// the frames; the caller places the outermost and stands what is cut in the last.
export function cutFrames(levels, frames, make) {
  const kept = frames.slice(Math.max(0, frames.length - levels.length));
  const chain = [...Array.from({ length: levels.length - kept.length }, make), ...kept];
  const was = frames[0];
  if (chain[0] && was && chain[0] !== was && was.parentNode)
    move(was.parentNode, chain[0], was);
  for (let i = 1; i < chain.length; i++)
    if (chain[i].parentNode !== chain[i - 1]) move(chain[i - 1], chain[i], null);
  for (const dropped of frames.slice(0, frames.length - kept.length)) dropped.remove();
  levels.forEach(({ anchor, band, axes, at, reading }, i) => {
    if (reading) nameAnchor(reading);
    anchorAt(chain[i], anchor, band, at);
    chain[i].style.clipPath = cutPath(axes);
  });
  return chain;
}

// Anchored controls cost layout even when their source is hidden or far down the page.
// Observe the source once, shared by every control standing against it, for whether it
// is near (geometry.js, `nearWindow`); continuous positioning remains the browser's,
// rather than a scroll callback's.
const views = new Map();
const viewedNodes = new WeakMap();
let viewObserver;

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

function releaseAnchorView(node) {
  const binding = viewedNodes.get(node);
  const view = binding?.view;
  if (!view) return;
  binding.view = null;
  view.nodes.delete(node);
  if (!view.nodes.size) {
    viewObserver.unobserve(view.target);
    views.delete(view.target);
  }
}

function resumeAnchorView(node) {
  const binding = viewedNodes.get(node);
  if (!binding || binding.view || !node.isConnected || !binding.target.isConnected)
    return;
  anchorView(node, binding.target, binding.changed);
  binding.changed();
}

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
    view = { target, near: nearWindow(target), nodes: new Map() };
    views.set(target, view);
    viewObserver.observe(target);
  }
  view.nodes.set(node, changed);
  viewedNodes.set(node, { target, changed, view });
  if (!node.classList.contains("lf-anchor-view")) node.classList.add("lf-anchor-view");
  return view.near;
}
