/* CSS anchors for boxes Leaf positions against page content: margin rows, floating
 * surfaces and Copy. A source keeps one name across those uses. Retained controls can
 * observe whether its source renders near the viewport before entering layout. That
 * reading starts synchronously, including ancestor clips, and observers maintain it;
 * keyboard intent can refresh it before an observer task. Control departure releases
 * its observation through the same arrivals door as the other chrome owners; its
 * weakly retained binding restores that observation when the control returns. */
import { pagePlaneRect, shownParts } from "./geometry.js";
import { hostIn } from "./shadow.js";
import { watchArrivals } from "./arrivals.js";

// Anchor names are global to their tree, so one per target element, merged with whatever
// name the author gave the same box. The name stays for the element's life: rows come and
// go on the heartbeat and a name written each time would restyle the target each time.
// The pass reads what a box is named before it writes any name (`anchorReading`), since
// reading the author's name is a style read.
const anchorNames = new WeakMap();
let anchorOrdinal = 0;
export function anchorReading(
  el,
  name = anchorNames.get(el) ?? `--lf-a${++anchorOrdinal}`,
) {
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
