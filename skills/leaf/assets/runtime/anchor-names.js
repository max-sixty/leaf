/* CSS anchors for boxes Leaf positions against page content: margin rows, floating
 * surfaces and Copy. A source keeps one name across those uses. Retained controls can
 * observe whether its source renders near the viewport before entering layout. That
 * reading starts synchronously, including ancestor clips, and observers maintain it;
 * keyboard intent can refresh it before an observer task. Control departure releases
 * its observation through the same arrivals door as the other chrome owners; its
 * weakly retained binding restores that observation when the control returns. */
import { pagePlaneRect, shownParts } from "./geometry.js";
import { hostIn, renderedParent } from "./shadow.js";
import { scrollContainer, scrollsContent } from "./scroll-motion.js";
import { watchArrivals } from "./arrivals.js";

// Anchor names are global to their tree, so one per target element, merged with whatever
// name the author gave the same box. The name stays for the element's life: rows come and
// go on the heartbeat and a name written each time would restyle the target each time.
// The pass reads what a box is named before it writes any name (`anchorReading`), since
// reading the author's name is a style read.
const anchorNames = new WeakMap();
let anchorOrdinal = 0;
const nextName = () => `--lf-a${++anchorOrdinal}`;
export function anchorReading(el, name = anchorNames.get(el) ?? nextName()) {
  // A content start is named where it is made (`contentStart`).
  const start = contentStarts.get(el);
  if (start) return { el, name: start.name };
  anchorNames.set(el, name);
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
export function nameAnchor({ el, name, write }) {
  if (write) el.style.anchorName = write;
  return name;
}

// The box a row or a float anchors to. An anchor name reaches only its own tree, so a
// target inside a shadow tree anchors through its host; a shape inside an SVG drawing has
// no CSS box of its own, so it anchors through the drawing; a `display: contents` target
// through its first shown part. Wherever it anchors, what stands against it is written as
// insets from the anchor's box.
export function anchorElement(target) {
  let el = hostIn(target, document);
  while (el instanceof SVGElement && el.ownerSVGElement) el = el.ownerSVGElement;
  if (el !== target) return el;
  const [part] = shownParts(target);
  return part && part !== target ? part : target;
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

// Whether `node` stands in the top layer as rendered, where no anchor it holds reaches a
// box outside it: a box slotted into a popover is in it.
export function inTopLayer(node) {
  for (let at = node; at; at = renderedParent(at))
    if (at instanceof Element && at.matches(":popover-open, dialog:modal")) return true;
  return false;
}

// What `scroller`'s own scroll carries as it carries what the scroller holds, for a box
// anchored to it to move with that scroll in the frame that scrolls: a child with a box
// of its own, in flow, where that scroll moves it, the one nearest `near`, one of the
// scroller's child nodes, where one is given. A line break renders as a break in the
// words rather than a box, so it anchors nothing. Words with no such child beside them
// anchor to the start of what the scroller holds (`contentStart`). Null where none of
// these is, or where the scroller lies inside a shadow tree or the top layer, whose
// anchors a box in the chrome cannot reach.
export function carriedAnchor(scroller, near = null) {
  if (scroller.getRootNode() !== document || inTopLayer(scroller)) return null;
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
// in the float, and where the browser reads a name from an attribute. Its handle answers `getBoundingClientRect` as an element anchor does,
// and naming it names the `::before`, through the scroller's `data-lf-content-start`,
// written where it is made and again where a revision rewrote it.
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
  if (scroller.getAttribute(START) !== name) scroller.setAttribute(START, name);
  return handle;
}

// The box whose scrolls carry `anchor`: the scroller a content start stands in, whose
// own scroll carries it too, or the anchor itself.
export const anchorHolder = (anchor) => contentStarts.get(anchor)?.scroller ?? anchor;

// The name `el` answers to as an anchor, given it first where it has none.
export const anchorName = (el) => nameAnchor(anchorReading(el));

// Anchored controls cost layout even when their source is hidden or far down the page.
// Observe the source once, shared by every control standing against it. The extra room
// brings controls into layout before ordinary scrolling carries their source on screen;
// continuous positioning remains the browser's, rather than a scroll callback's.
const views = new Map();
const viewedNodes = new WeakMap();
let viewObserver;

function nearWindow(target) {
  if (!target.checkVisibility()) return false;
  const box = pagePlaneRect(target.getBoundingClientRect(), target, new Map());
  if (!box) return false;
  return (
    box.bottom >= -600 &&
    box.top <= innerHeight + 600 &&
    box.right >= -600 &&
    box.left <= innerWidth + 600
  );
}

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
    viewObserver = new IntersectionObserver(
      (entries) => {
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
      },
      { rootMargin: "600px" },
    );
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
